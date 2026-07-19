"""Testes: handle_sync_messages, sync de historico LAN <-> online (Sprint 3, Dia 12).

Cobre:
    - pending com uuid novo: aceito, persistido e devolvido em accepted_uuids
    - pending com uuid ja existente: ignorado (nao duplica, nao entra em accepted_uuids)
    - pending de quem nao e membro do forum: ignorado
    - last_seen: get_messages_since retorna so o que falta (id > last_seen)
    - broadcast: mensagens aceitas em pending chegam via EVT_NEW_MESSAGE a
      outro cliente que ficou conectado o tempo todo (simula LAN -> online)
    - sync sem autenticacao falha
"""

import base64
import socket
import threading

import pytest

from shared import crypto_utils, protocol
from server.main import CorvoServer
from client.network.client_socket import CorvoClient


# --- fixture (identica ao padrao de test_group_e2e.py) ------------------------

@pytest.fixture
def servidor():
    server = CorvoServer(host="127.0.0.1", port=0, db_path=":memory:")
    server._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server._server_sock.bind(("127.0.0.1", 0))
    server.port = server._server_sock.getsockname()[1]
    server._server_sock.listen()
    server._running.set()

    def _accept():
        while server._running.is_set():
            try:
                sock, addr = server._server_sock.accept()
            except OSError:
                break
            threading.Thread(target=server._handle_client, args=(sock, addr), daemon=True).start()

    threading.Thread(target=_accept, daemon=True).start()
    yield server
    server.stop()


def _cliente(servidor) -> CorvoClient:
    c = CorvoClient(host="127.0.0.1", port=servidor.port)
    c.connect()
    return c


def _resp(client: CorvoClient, timeout: float = 2.0) -> dict:
    return client.inbox.get(timeout=timeout)


def _registrar_e_logar(client: CorvoClient, username: str, password: str) -> bytes:
    client.request(protocol.CMD_REGISTER, {"username": username, "password": password})
    _resp(client)
    client.request(protocol.CMD_LOGIN, {"username": username, "password": password})
    _resp(client)

    priv_pem, pub_pem = crypto_utils.generate_rsa_keypair()
    client.request(protocol.CMD_UPDATE_PUBKEY, {"public_key": pub_pem.decode("utf-8")})
    r = _resp(client)
    assert r["status"] == protocol.STATUS_OK
    return priv_pem


def _criar_forum_com_membro(dono: CorvoClient, membro: CorvoClient) -> int:
    dono.request(protocol.CMD_CREATE_FORUM, {"name": "Corvos da Noite"})
    r = _resp(dono)
    forum_id, invite_code = r["data"]["forum_id"], r["data"]["invite_code"]

    membro.request(protocol.CMD_JOIN_FORUM, {"invite_code": invite_code})
    _resp(membro)
    _resp(dono)  # dono recebe EVT_MEMBER_JOINED
    return forum_id


def _pending_item(forum_id: int, aes_key: bytes, texto: str, uuid: str,
                   origin_timestamp: str = "2026-07-13T10:00:00") -> dict:
    ciphertext, iv = crypto_utils.aes_encrypt(texto.encode("utf-8"), aes_key)
    return {
        "forum_id": forum_id,
        "uuid": uuid,
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "iv": base64.b64encode(iv).decode("ascii"),
        "key_version": 1,
        "origin_timestamp": origin_timestamp,
    }


# --- pending / accepted_uuids ---------------------------------------------------

def test_sync_aceita_pending_novo(servidor):
    dono = _cliente(servidor)
    _registrar_e_logar(dono, "alice", "s3nh4A!")
    membro = _cliente(servidor)
    _registrar_e_logar(membro, "bob", "s3nh4B!")
    forum_id = _criar_forum_com_membro(dono, membro)

    aes_key = crypto_utils.generate_aes_key()
    item = _pending_item(forum_id, aes_key, "mensagem gerada offline", "uuid-lan-1")

    dono.request(protocol.CMD_SYNC_MESSAGES, {"last_seen": {}, "pending": [item]})
    r = _resp(dono)
    assert r["status"] == protocol.STATUS_OK
    assert r["data"]["accepted_uuids"] == ["uuid-lan-1"]

    dono.close()
    membro.close()


def test_sync_ignora_uuid_duplicado(servidor):
    dono = _cliente(servidor)
    _registrar_e_logar(dono, "alice", "s3nh4A!")
    membro = _cliente(servidor)
    _registrar_e_logar(membro, "bob", "s3nh4B!")
    forum_id = _criar_forum_com_membro(dono, membro)

    aes_key = crypto_utils.generate_aes_key()
    item = _pending_item(forum_id, aes_key, "mensagem unica", "uuid-repetido")

    dono.request(protocol.CMD_SYNC_MESSAGES, {"last_seen": {}, "pending": [item]})
    r1 = _resp(dono)
    assert r1["data"]["accepted_uuids"] == ["uuid-repetido"]

    # reenvia a MESMA sync (ex.: cliente reconecta de novo antes de confirmar) —
    # nao deve duplicar nem aparecer de novo em accepted_uuids.
    dono.request(protocol.CMD_SYNC_MESSAGES, {"last_seen": {}, "pending": [item]})
    r2 = _resp(dono)
    assert r2["data"]["accepted_uuids"] == []

    dono.request(protocol.CMD_GET_HISTORY, {"forum_id": forum_id})
    r3 = _resp(dono)
    uuids = [m["uuid"] for m in r3["data"]["messages"]]
    assert uuids.count("uuid-repetido") == 1

    dono.close()
    membro.close()


def test_sync_ignora_pending_de_forum_sem_ser_membro(servidor):
    dono = _cliente(servidor)
    _registrar_e_logar(dono, "alice", "s3nh4A!")
    dono.request(protocol.CMD_CREATE_FORUM, {"name": "Conclave Fechado"})
    r = _resp(dono)
    forum_id = r["data"]["forum_id"]

    fora = _cliente(servidor)
    _registrar_e_logar(fora, "fantasma", "s3nh4F!")

    aes_key = crypto_utils.generate_aes_key()
    item = _pending_item(forum_id, aes_key, "nao deveria entrar", "uuid-intruso")

    fora.request(protocol.CMD_SYNC_MESSAGES, {"last_seen": {}, "pending": [item]})
    r2 = _resp(fora)
    assert r2["status"] == protocol.STATUS_OK
    assert r2["data"]["accepted_uuids"] == []  # ignorado silenciosamente, nao autorizado

    dono.close()
    fora.close()


# --- last_seen / get_messages_since ---------------------------------------------

def test_sync_last_seen_retorna_so_mensagens_novas(servidor):
    dono = _cliente(servidor)
    _registrar_e_logar(dono, "alice", "s3nh4A!")
    membro = _cliente(servidor)
    _registrar_e_logar(membro, "bob", "s3nh4B!")
    forum_id = _criar_forum_com_membro(dono, membro)

    aes_key = crypto_utils.generate_aes_key()
    for i, texto in enumerate(["primeira", "segunda", "terceira"]):
        ciphertext, iv = crypto_utils.aes_encrypt(texto.encode("utf-8"), aes_key)
        dono.request(protocol.CMD_SEND_TO_FORUM, {
            "forum_id": forum_id,
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "iv": base64.b64encode(iv).decode("ascii"),
            "key_version": 1,
        })
        _resp(dono)
        _resp(membro)  # EVT_NEW_MESSAGE

    dono.request(protocol.CMD_GET_HISTORY, {"forum_id": forum_id})
    historico = _resp(dono)["data"]["messages"]
    assert len(historico) == 3

    # simula que o membro so viu a primeira mensagem: pede sync desde o id=1
    # (nao sabemos o id exato aqui, entao usamos 0 pra pegar tudo e confirmar
    # o filtro central via um segundo request com since = id da 1a mensagem).
    membro.request(protocol.CMD_SYNC_MESSAGES, {"last_seen": {str(forum_id): 0}, "pending": []})
    r_tudo = _resp(membro)
    assert len(r_tudo["data"]["new_messages"][str(forum_id)]) == 3

    primeiro_id = r_tudo["data"]["new_messages"][str(forum_id)][0]["id"]
    membro.request(protocol.CMD_SYNC_MESSAGES, {"last_seen": {str(forum_id): primeiro_id}, "pending": []})
    r_parcial = _resp(membro)
    restantes = r_parcial["data"]["new_messages"][str(forum_id)]
    assert len(restantes) == 2
    assert all(m["id"] > primeiro_id for m in restantes)

    dono.close()
    membro.close()


# --- broadcast das mensagens vindas de pending -----------------------------------

def test_sync_pending_aceito_dispara_broadcast_para_outro_membro(servidor):
    dono = _cliente(servidor)
    _registrar_e_logar(dono, "alice", "s3nh4A!")
    membro = _cliente(servidor)
    _registrar_e_logar(membro, "bob", "s3nh4B!")
    forum_id = _criar_forum_com_membro(dono, membro)

    aes_key = crypto_utils.generate_aes_key()
    item = _pending_item(forum_id, aes_key, "mensagem trazida da LAN", "uuid-broadcast-1")

    dono.request(protocol.CMD_SYNC_MESSAGES, {"last_seen": {}, "pending": [item]})
    r = _resp(dono)
    assert r["data"]["accepted_uuids"] == ["uuid-broadcast-1"]

    evt = _resp(membro)
    assert evt["cmd"] == protocol.EVT_NEW_MESSAGE
    plaintext = crypto_utils.aes_decrypt(
        base64.b64decode(evt["data"]["ciphertext"]), aes_key, base64.b64decode(evt["data"]["iv"])
    )
    assert plaintext.decode("utf-8") == "mensagem trazida da LAN"

    dono.close()
    membro.close()


def test_sync_sem_autenticacao_falha(servidor):
    c = _cliente(servidor)
    c.request(protocol.CMD_SYNC_MESSAGES, {"last_seen": {}, "pending": []})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao autenticado" in r["message"]
    c.close()
