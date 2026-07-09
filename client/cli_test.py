"""CLI de teste do cliente Corvo Negro (Sprint 1, Dias 2-6).

Conecta ao servidor e permite enviar comandos crus para exercitar o protocolo
antes da GUI existir. Imprime tudo que chega na inbox, decifra mensagens
diretas (NEW_DM) e de forum (NEW_MESSAGE) automaticamente, e cuida da
distribuicao/rotacao de chave AES de forum quando o usuario logado e o dono.

Uso:
    python -m client.cli_test

Comandos interativos:
    /ping                     -> envia PING (espera PONG)
    /echo <texto>             -> envia ECHO com {"texto": ...}
    /register <user> <senha>  -> cadastra e gera/salva par RSA local
    /login <user> <senha>     -> login e envia a public key ao servidor
    /dm <user> <mensagem>     -> envia mensagem 1:1 cifrada (RSA+AES hibrido)
    /create <nome>            -> cria um forum, mostra o codigo de convite
    /join <codigo>            -> entra num forum via codigo CORVO-XXXX-XXXX
    /leave <forum_id>         -> sai de um forum
    /list                     -> lista os foruns do usuario logado
    /send <forum_id> <msg>    -> envia mensagem cifrada com a AES do forum
    /history <forum_id>       -> busca e decifra o historico do forum
    /createrole <forum_id> <nome> <mascara> -> cria role (requer MANAGE_ROLES)
    /assignrole <forum_id> <user> <role_id> -> atribui role (requer MANAGE_ROLES)
    /pin <uuid>               -> fixa a mensagem (requer PIN_MESSAGE)
    /delete <uuid>            -> apaga a mensagem (autor ou DELETE_MESSAGE)
    /raw <CMD> <json_data>    -> envia um request cru: cmd + data (JSON)
    /quit                     -> encerra

Nota sobre E2E em grupo: quem controla a distribuicao/rotacao da chave AES
de cada forum e sempre o dono (ver server/handlers/key_exchange.py). Este
CLI faz isso automaticamente ao detectar MEMBER_JOINED/MEMBER_LEFT de um
forum que o usuario logado possui.
"""

from __future__ import annotations

import base64
import json
import threading
import time

from shared import crypto_utils, protocol
from client.network.client_socket import CorvoClient
from client.storage import key_vault

# Estado de sessao (preenchido por /register e /login).
_state = {
    "username": None,
    "user_id": None,
    "private_key_pem": None,
    # {(forum_id, key_version): aes_key} — chaves de forum decifradas em memoria.
    "forum_keys": {},
    # {forum_id} — foruns onde este usuario e o dono (sabido via owner_id nas responses/eventos).
    "owned_forums": set(),
}


def _note_ownership(forum_id: int, owner_id: int) -> None:
    if owner_id is not None and _state.get("user_id") == owner_id:
        _state["owned_forums"].add(forum_id)


def _current_key_version(forum_id: int) -> int:
    versions = [v for (fid, v) in _state["forum_keys"] if fid == forum_id]
    return max(versions) if versions else 0


def _distribute_key_to(client: CorvoClient, forum_id: int, recipient: str, aes_key: bytes, key_version: int) -> None:
    """Pede a pubkey do destinatario, cifra a AES key do forum e distribui."""
    client.request(protocol.CMD_GET_PUBKEY, {"username": recipient})
    try:
        resp = client.inbox.get(timeout=2.0)
    except Exception:
        print(f"[!] sem resposta ao pedir pubkey de {recipient} p/ distribuir chave")
        return
    if resp.get("status") != protocol.STATUS_OK:
        print(f"[!] nao foi possivel obter a chave de {recipient}: {resp.get('message')}")
        return

    recipient_pub_pem = resp["data"]["public_key"].encode("utf-8")
    encrypted_aes_key = crypto_utils.rsa_encrypt(aes_key, recipient_pub_pem)
    client.request(
        protocol.CMD_DISTRIBUTE_KEY,
        {
            "forum_id": forum_id,
            "recipient": recipient,
            "encrypted_aes_key": base64.b64encode(encrypted_aes_key).decode("ascii"),
            "key_version": key_version,
        },
    )


def _print_inbox(client: CorvoClient, stop: threading.Event) -> None:
    """Drena a inbox, decifra eventos conhecidos e imprime o resto."""
    while not stop.is_set():
        try:
            msg = client.inbox.get(timeout=0.2)
        except Exception:
            continue
        cmd = msg.get("cmd")
        if cmd == "_DISCONNECTED":
            print("\n[!] desconectado do servidor")
            stop.set()
            break
        elif cmd == protocol.EVT_NEW_DM:
            _handle_incoming_dm(msg["data"])
        elif cmd == protocol.EVT_KEY_ROTATED:
            _handle_key_rotated(msg["data"])
        elif cmd == protocol.EVT_NEW_MESSAGE:
            _handle_incoming_forum_message(msg["data"])
        elif cmd == protocol.EVT_MEMBER_JOINED:
            _handle_member_joined(client, msg["data"])
        elif cmd == protocol.EVT_MEMBER_LEFT:
            _handle_member_left(client, msg["data"])
        else:
            print(f"\n<< {json.dumps(msg, ensure_ascii=False)}")
        print("> ", end="", flush=True)


def _handle_incoming_dm(data: dict) -> None:
    """Decifra uma mensagem 1:1 recebida (AES key via RSA, msg via AES)."""
    priv_pem = _state["private_key_pem"]
    if priv_pem is None:
        print(f"\n<< DM de {data['sender']} (sem chave privada carregada p/ decifrar)")
        return
    try:
        encrypted_key = base64.b64decode(data["encrypted_key"])
        ciphertext = base64.b64decode(data["ciphertext"])
        iv = base64.b64decode(data["iv"])
        aes_key = crypto_utils.rsa_decrypt(encrypted_key, priv_pem)
        plaintext = crypto_utils.aes_decrypt(ciphertext, aes_key, iv)
        print(f"\n[DM] {data['sender']}: {plaintext.decode('utf-8')}")
    except Exception as exc:
        print(f"\n[!] falha ao decifrar DM de {data['sender']}: {exc}")


def _handle_key_rotated(data: dict) -> None:
    """Recebe a AES key de um forum (distribuida pelo dono), decifra e guarda."""
    priv_pem = _state["private_key_pem"]
    if priv_pem is None:
        print("\n<< KEY_ROTATED recebido, mas sem chave privada carregada")
        return
    try:
        encrypted_aes_key = base64.b64decode(data["encrypted_aes_key"])
        aes_key = crypto_utils.rsa_decrypt(encrypted_aes_key, priv_pem)
        forum_id, key_version = data["forum_id"], data["key_version"]
        _state["forum_keys"][(forum_id, key_version)] = aes_key
        print(f"\n[*] chave do forum {forum_id} atualizada (versao {key_version})")
    except Exception as exc:
        print(f"\n[!] falha ao decifrar a chave do forum: {exc}")


def _handle_incoming_forum_message(data: dict) -> None:
    """Decifra uma mensagem de forum recebida com a AES da key_version indicada."""
    forum_id, key_version = data["forum_id"], data["key_version"]
    aes_key = _state["forum_keys"].get((forum_id, key_version))
    if aes_key is None:
        print(f"\n<< forum {forum_id}: {data['sender']} enviou uma mensagem (sem a chave p/ decifrar)")
        return
    try:
        ciphertext = base64.b64decode(data["ciphertext"])
        iv = base64.b64decode(data["iv"])
        plaintext = crypto_utils.aes_decrypt(ciphertext, aes_key, iv)
        print(f"\n[forum {forum_id}] {data['sender']}: {plaintext.decode('utf-8')}")
    except Exception as exc:
        print(f"\n[!] falha ao decifrar mensagem do forum {forum_id}: {exc}")


def _handle_member_joined(client: CorvoClient, data: dict) -> None:
    """Se este usuario e o dono do forum, distribui a chave atual ao novo membro."""
    forum_id = data["forum_id"]
    _note_ownership(forum_id, data.get("owner_id"))
    if forum_id not in _state["owned_forums"]:
        return
    key_version = _current_key_version(forum_id)
    aes_key = _state["forum_keys"].get((forum_id, key_version))
    if aes_key is None:
        return
    _distribute_key_to(client, forum_id, data["username"], aes_key, key_version)


def _handle_member_left(client: CorvoClient, data: dict) -> None:
    """Se este usuario e o dono do forum, rotaciona a chave AES da sala.

    Gera uma nova AES key, incrementa a key_version e redistribui para todos
    os membros que restaram (a lista vem pronta no proprio evento).
    """
    forum_id = data["forum_id"]
    _note_ownership(forum_id, data.get("owner_id"))
    if forum_id not in _state["owned_forums"]:
        return

    new_version = _current_key_version(forum_id) + 1
    aes_key = crypto_utils.generate_aes_key()
    _state["forum_keys"][(forum_id, new_version)] = aes_key
    for member in data.get("remaining_members", []):
        if member == _state["username"]:
            continue
        _distribute_key_to(client, forum_id, member, aes_key, new_version)
    print(f"\n[*] {data['username']} saiu do forum {forum_id} — chave rotacionada p/ versao {new_version}")


def _cmd_register(client: CorvoClient, username: str, password: str) -> None:
    client.request(protocol.CMD_REGISTER, {"username": username, "password": password})
    print("[*] aguardando resposta do registro...")
    if not key_vault.has_vault(username):
        priv_pem, _pub_pem = crypto_utils.generate_rsa_keypair()
        key_vault.save_private_key(username, priv_pem, password)
        print(f"[*] par RSA gerado e salvo localmente para '{username}'")


def _cmd_login(client: CorvoClient, username: str, password: str) -> None:
    client.request(protocol.CMD_LOGIN, {"username": username, "password": password})
    try:
        resp = client.inbox.get(timeout=2.0)
        if resp.get("status") == protocol.STATUS_OK:
            _state["user_id"] = resp["data"]["user_id"]
    except Exception:
        pass
    _state["username"] = username
    try:
        priv_pem = key_vault.load_private_key(username, password)
    except FileNotFoundError:
        priv_pem, pub_pem = crypto_utils.generate_rsa_keypair()
        key_vault.save_private_key(username, priv_pem, password)
        print("[*] nenhuma chave local encontrada — par RSA novo gerado e salvo")
    else:
        pub_pem = crypto_utils.public_key_from_private(priv_pem)
    _state["private_key_pem"] = priv_pem
    client.request(protocol.CMD_UPDATE_PUBKEY, {"public_key": pub_pem.decode("utf-8")})


def _cmd_dm(client: CorvoClient, recipient: str, texto: str) -> None:
    client.request(protocol.CMD_GET_PUBKEY, {"username": recipient})
    try:
        resp = client.inbox.get(timeout=2.0)
    except Exception:
        print("[!] sem resposta do servidor ao pedir a chave publica")
        return
    if resp.get("status") != protocol.STATUS_OK:
        print(f"[!] nao foi possivel obter a chave de {recipient}: {resp.get('message')}")
        return

    recipient_pub_pem = resp["data"]["public_key"].encode("utf-8")
    aes_key = crypto_utils.generate_aes_key()
    ciphertext, iv = crypto_utils.aes_encrypt(texto.encode("utf-8"), aes_key)
    encrypted_key = crypto_utils.rsa_encrypt(aes_key, recipient_pub_pem)

    client.request(
        protocol.CMD_MSG_1V1,
        {
            "recipient": recipient,
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "encrypted_key": base64.b64encode(encrypted_key).decode("ascii"),
            "iv": base64.b64encode(iv).decode("ascii"),
        },
    )


def _cmd_create_forum(client: CorvoClient, name: str) -> None:
    """Cria o forum e ja gera+distribui a primeira versao (1) da AES da sala."""
    client.request(protocol.CMD_CREATE_FORUM, {"name": name})
    try:
        resp = client.inbox.get(timeout=2.0)
    except Exception:
        print("[!] sem resposta do servidor ao criar o forum")
        return
    if resp.get("status") != protocol.STATUS_OK:
        print(f"[!] erro ao criar forum: {resp.get('message')}")
        return

    forum_id = resp["data"]["forum_id"]
    _note_ownership(forum_id, resp["data"]["owner_id"])
    aes_key = crypto_utils.generate_aes_key()
    _state["forum_keys"][(forum_id, 1)] = aes_key
    _distribute_key_to(client, forum_id, _state["username"], aes_key, 1)
    print(f"[*] forum '{name}' criado (id={forum_id}). Convite: {resp['data']['invite_code']}")


def _cmd_join_forum(client: CorvoClient, invite_code: str) -> None:
    client.request(protocol.CMD_JOIN_FORUM, {"invite_code": invite_code})
    try:
        resp = client.inbox.get(timeout=2.0)
    except Exception:
        print("[!] sem resposta do servidor ao entrar no forum")
        return
    if resp.get("status") == protocol.STATUS_OK:
        _note_ownership(resp["data"]["forum_id"], resp["data"]["owner_id"])
    print(json.dumps(resp, ensure_ascii=False))


def _cmd_leave_forum(client: CorvoClient, forum_id: str) -> None:
    client.request(protocol.CMD_LEAVE_FORUM, {"forum_id": int(forum_id)})


def _cmd_list_forums(client: CorvoClient) -> None:
    client.request(protocol.CMD_LIST_MY_FORUMS, {})


def _cmd_send_to_forum(client: CorvoClient, forum_id: int, texto: str) -> None:
    key_version = _current_key_version(forum_id)
    aes_key = _state["forum_keys"].get((forum_id, key_version))
    if aes_key is None:
        print(f"[!] sem chave AES do forum {forum_id} em memoria — entre/crie o forum primeiro")
        return
    ciphertext, iv = crypto_utils.aes_encrypt(texto.encode("utf-8"), aes_key)
    client.request(
        protocol.CMD_SEND_TO_FORUM,
        {
            "forum_id": forum_id,
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "iv": base64.b64encode(iv).decode("ascii"),
            "key_version": key_version,
        },
    )


def _cmd_history(client: CorvoClient, forum_id: int) -> None:
    client.request(protocol.CMD_GET_HISTORY, {"forum_id": forum_id})
    try:
        resp = client.inbox.get(timeout=2.0)
    except Exception:
        print("[!] sem resposta do servidor ao buscar o historico")
        return
    if resp.get("status") != protocol.STATUS_OK:
        print(f"[!] erro ao buscar historico: {resp.get('message')}")
        return

    for msg in resp["data"]["messages"]:
        aes_key = _state["forum_keys"].get((forum_id, msg["key_version"]))
        if aes_key is None:
            print(f"[{msg['timestamp']}] {msg['sender']}: <sem chave da versao {msg['key_version']}>")
            continue
        try:
            plaintext = crypto_utils.aes_decrypt(
                base64.b64decode(msg["ciphertext"]), aes_key, base64.b64decode(msg["iv"])
            )
            pin = " [FIXADA]" if msg["pinned"] else ""
            print(f"[{msg['timestamp']}] ({msg['uuid']}) {msg['sender']}: {plaintext.decode('utf-8')}{pin}")
        except Exception as exc:
            print(f"[{msg['timestamp']}] ({msg['uuid']}) {msg['sender']}: <falha ao decifrar: {exc}>")


def _cmd_create_role(client: CorvoClient, forum_id: int, name: str, mask: int) -> None:
    client.request(
        protocol.CMD_CREATE_ROLE, {"forum_id": forum_id, "name": name, "permissions": mask}
    )


def _cmd_assign_role(client: CorvoClient, forum_id: int, username: str, role_id: int) -> None:
    client.request(
        protocol.CMD_ASSIGN_ROLE, {"forum_id": forum_id, "username": username, "role_id": role_id}
    )


def _cmd_pin_message(client: CorvoClient, msg_uuid: str) -> None:
    client.request(protocol.CMD_PIN_MESSAGE, {"uuid": msg_uuid, "pinned": True})


def _cmd_delete_message(client: CorvoClient, msg_uuid: str) -> None:
    client.request(protocol.CMD_DELETE_MESSAGE, {"uuid": msg_uuid})


def main() -> None:
    client = CorvoClient()
    try:
        client.connect()
    except OSError as exc:
        print(f"[!] nao conectou: {exc}")
        return
    print(
        "[Corvo Negro] conectado. Comandos: /register /login /dm "
        "/create /join /leave /list /send /history /createrole /assignrole "
        "/pin /delete /ping /echo /raw /quit"
    )

    stop = threading.Event()
    printer = threading.Thread(target=_print_inbox, args=(client, stop), daemon=True)
    printer.start()

    try:
        while not stop.is_set():
            line = input("> ").strip()
            if not line:
                continue
            if line == "/quit":
                break
            elif line == "/ping":
                client.request("PING")
            elif line.startswith("/echo "):
                client.request("ECHO", {"texto": line[len("/echo "):]})
            elif line.startswith("/register "):
                _, user, senha = line.split(" ", 2)
                _cmd_register(client, user, senha)
            elif line.startswith("/login "):
                _, user, senha = line.split(" ", 2)
                _cmd_login(client, user, senha)
            elif line.startswith("/dm "):
                _, user, texto = line.split(" ", 2)
                _cmd_dm(client, user, texto)
            elif line.startswith("/create "):
                _cmd_create_forum(client, line[len("/create "):])
            elif line.startswith("/join "):
                _cmd_join_forum(client, line[len("/join "):].strip())
            elif line.startswith("/leave "):
                _cmd_leave_forum(client, line[len("/leave "):].strip())
            elif line == "/list":
                _cmd_list_forums(client)
            elif line.startswith("/send "):
                _, forum_id, texto = line.split(" ", 2)
                _cmd_send_to_forum(client, int(forum_id), texto)
            elif line.startswith("/history "):
                _cmd_history(client, int(line[len("/history "):].strip()))
            elif line.startswith("/createrole "):
                _, forum_id, name, mask = line.split(" ", 3)
                _cmd_create_role(client, int(forum_id), name, int(mask))
            elif line.startswith("/assignrole "):
                _, forum_id, user, role_id = line.split(" ", 3)
                _cmd_assign_role(client, int(forum_id), user, int(role_id))
            elif line.startswith("/pin "):
                _cmd_pin_message(client, line[len("/pin "):].strip())
            elif line.startswith("/delete "):
                _cmd_delete_message(client, line[len("/delete "):].strip())
            elif line.startswith("/raw "):
                _, cmd, *rest = line.split(" ", 2)
                data = json.loads(rest[0]) if rest else {}
                client.request(cmd, data)
            else:
                print(
                    "comandos: /register /login /dm /create /join /leave /list "
                    "/send /history /createrole /assignrole /pin /delete /ping /echo /raw /quit"
                )
            time.sleep(0.05)
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        stop.set()
        client.close()
        print("\nate a proxima, corvo.")


if __name__ == "__main__":
    main()
