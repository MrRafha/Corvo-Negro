"""CLI de teste do cliente Corvo Negro (Sprint 1, Dias 2-4).

Conecta ao servidor e permite enviar comandos crus para exercitar o protocolo
antes da GUI existir. Imprime tudo que chega na inbox, e decifra mensagens
diretas (NEW_DM) automaticamente com a chave privada em memoria.

Uso:
    python -m client.cli_test

Comandos interativos:
    /ping                     -> envia PING (espera PONG)
    /echo <texto>             -> envia ECHO com {"texto": ...}
    /register <user> <senha>  -> cadastra e gera/salva par RSA local
    /login <user> <senha>     -> login e envia a public key ao servidor
    /dm <user> <mensagem>     -> envia mensagem 1:1 cifrada (RSA+AES hibrido)
    /raw <CMD> <json_data>    -> envia um request cru: cmd + data (JSON)
    /quit                     -> encerra
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
_state = {"username": None, "private_key_pem": None}


def _print_inbox(client: CorvoClient, stop: threading.Event) -> None:
    """Drena a inbox, decifra NEW_DM quando possivel e imprime o resto."""
    while not stop.is_set():
        try:
            msg = client.inbox.get(timeout=0.2)
        except Exception:
            continue
        if msg.get("cmd") == "_DISCONNECTED":
            print("\n[!] desconectado do servidor")
            stop.set()
            break
        if msg.get("cmd") == protocol.EVT_NEW_DM:
            _handle_incoming_dm(msg["data"])
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


def _cmd_register(client: CorvoClient, username: str, password: str) -> None:
    client.request(protocol.CMD_REGISTER, {"username": username, "password": password})
    print("[*] aguardando resposta do registro...")
    if not key_vault.has_vault(username):
        priv_pem, _pub_pem = crypto_utils.generate_rsa_keypair()
        key_vault.save_private_key(username, priv_pem, password)
        print(f"[*] par RSA gerado e salvo localmente para '{username}'")


def _cmd_login(client: CorvoClient, username: str, password: str) -> None:
    client.request(protocol.CMD_LOGIN, {"username": username, "password": password})
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


def main() -> None:
    client = CorvoClient()
    try:
        client.connect()
    except OSError as exc:
        print(f"[!] nao conectou: {exc}")
        return
    print("[Corvo Negro] conectado. Comandos: /register /login /dm /ping /echo /raw /quit")

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
            elif line.startswith("/raw "):
                _, cmd, *rest = line.split(" ", 2)
                data = json.loads(rest[0]) if rest else {}
                client.request(cmd, data)
            else:
                print("comandos: /register /login /dm /ping /echo /raw /quit")
            time.sleep(0.05)
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        stop.set()
        client.close()
        print("\nate a proxima, corvo.")


if __name__ == "__main__":
    main()
