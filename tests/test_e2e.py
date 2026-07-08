"""Testes: E2E 1:1 - troca de chaves e mensagens diretas hibridas (Sprint 1, Dia 4).

Cobre:
    - update_pubkey grava a chave publica do usuario autenticado
    - get_pubkey devolve a chave publica de outro usuario
    - get_pubkey falha para usuario inexistente / sem chave / sem autenticacao
    - MSG_1V1 fim-a-fim: A cifra com a pubkey de B, servidor roteia sem decifrar,
      B decifra com sua chave privada e recupera o texto original
    - MSG_1V1 falha sem destinatario/autenticacao
"""

import base64
import socket
import threading

import pytest

from shared import crypto_utils, protocol
from server.main import CorvoServer
from client.network.client_socket import CorvoClient


# --- fixture -----------------------------------------------------------------

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
    """Registra, loga e envia a public key. Retorna a private key PEM gerada."""
    client.request(protocol.CMD_REGISTER, {"username": username, "password": password})
    _resp(client)
    client.request(protocol.CMD_LOGIN, {"username": username, "password": password})
    _resp(client)

    priv_pem, pub_pem = crypto_utils.generate_rsa_keypair()
    client.request(protocol.CMD_UPDATE_PUBKEY, {"public_key": pub_pem.decode("utf-8")})
    r = _resp(client)
    assert r["status"] == protocol.STATUS_OK
    return priv_pem


# --- update / get pubkey ------------------------------------------------------

def test_update_pubkey_sucesso(servidor):
    c = _cliente(servidor)
    _registrar_e_logar(c, "corvo", "s3nh4!")
    c.close()


def test_update_pubkey_sem_autenticacao(servidor):
    c = _cliente(servidor)
    c.request(protocol.CMD_UPDATE_PUBKEY, {"public_key": "qualquer"})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao autenticado" in r["message"]
    c.close()


def test_get_pubkey_sucesso(servidor):
    c1 = _cliente(servidor)
    _registrar_e_logar(c1, "corvo", "s3nh4!")

    c2 = _cliente(servidor)
    _registrar_e_logar(c2, "morcego", "outra!")

    c2.request(protocol.CMD_GET_PUBKEY, {"username": "corvo"})
    r = _resp(c2)
    assert r["status"] == protocol.STATUS_OK
    assert r["data"]["username"] == "corvo"
    assert "BEGIN PUBLIC KEY" in r["data"]["public_key"]
    c1.close()
    c2.close()


def test_get_pubkey_usuario_inexistente(servidor):
    c = _cliente(servidor)
    _registrar_e_logar(c, "corvo", "s3nh4!")
    c.request(protocol.CMD_GET_PUBKEY, {"username": "fantasma"})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao encontrado" in r["message"]
    c.close()


def test_get_pubkey_sem_chave_registrada(servidor):
    c1 = _cliente(servidor)
    c1.request(protocol.CMD_REGISTER, {"username": "semchave", "password": "s3nh4!"})
    _resp(c1)
    c1.request(protocol.CMD_LOGIN, {"username": "semchave", "password": "s3nh4!"})
    _resp(c1)  # nunca chama UPDATE_PUBKEY

    c2 = _cliente(servidor)
    _registrar_e_logar(c2, "corvo", "s3nh4!")
    c2.request(protocol.CMD_GET_PUBKEY, {"username": "semchave"})
    r = _resp(c2)
    assert r["status"] == protocol.STATUS_ERROR
    assert "sem chave publica" in r["message"]
    c1.close()
    c2.close()


def test_get_pubkey_sem_autenticacao(servidor):
    c = _cliente(servidor)
    c.request(protocol.CMD_GET_PUBKEY, {"username": "corvo"})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao autenticado" in r["message"]
    c.close()


# --- MSG_1V1 (E2E hibrido RSA+AES) --------------------------------------------

def test_msg_1v1_fim_a_fim(servidor):
    c_a = _cliente(servidor)
    priv_a = _registrar_e_logar(c_a, "alice", "s3nh4A!")

    c_b = _cliente(servidor)
    priv_b = _registrar_e_logar(c_b, "bob", "s3nh4B!")

    # Alice pede a pubkey do Bob.
    c_a.request(protocol.CMD_GET_PUBKEY, {"username": "bob"})
    r = _resp(c_a)
    bob_pub_pem = r["data"]["public_key"].encode("utf-8")

    # Alice cifra a mensagem com AES e a chave AES com a RSA publica do Bob.
    texto_original = "as palavras dos mortos viajam em asas negras"
    aes_key = crypto_utils.generate_aes_key()
    ciphertext, iv = crypto_utils.aes_encrypt(texto_original.encode("utf-8"), aes_key)
    encrypted_key = crypto_utils.rsa_encrypt(aes_key, bob_pub_pem)

    c_a.request(
        protocol.CMD_MSG_1V1,
        {
            "recipient": "bob",
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "encrypted_key": base64.b64encode(encrypted_key).decode("ascii"),
            "iv": base64.b64encode(iv).decode("ascii"),
        },
    )
    r = _resp(c_a)
    assert r["status"] == protocol.STATUS_OK
    assert "uuid" in r["data"]

    # Bob recebe o evento NEW_DM (o servidor nunca viu o texto claro).
    evt = _resp(c_b)
    assert evt["cmd"] == protocol.EVT_NEW_DM
    assert evt["data"]["sender"] == "alice"

    # Bob decifra com sua chave privada.
    recv_key = crypto_utils.rsa_decrypt(base64.b64decode(evt["data"]["encrypted_key"]), priv_b)
    recv_plain = crypto_utils.aes_decrypt(
        base64.b64decode(evt["data"]["ciphertext"]), recv_key, base64.b64decode(evt["data"]["iv"])
    )
    assert recv_plain.decode("utf-8") == texto_original

    c_a.close()
    c_b.close()


def test_msg_1v1_persistido_no_banco(servidor):
    c_a = _cliente(servidor)
    _registrar_e_logar(c_a, "alice", "s3nh4A!")
    c_b = _cliente(servidor)
    _registrar_e_logar(c_b, "bob", "s3nh4B!")

    c_a.request(protocol.CMD_GET_PUBKEY, {"username": "bob"})
    r = _resp(c_a)
    bob_pub_pem = r["data"]["public_key"].encode("utf-8")

    aes_key = crypto_utils.generate_aes_key()
    ciphertext, iv = crypto_utils.aes_encrypt(b"mensagem persistida", aes_key)
    encrypted_key = crypto_utils.rsa_encrypt(aes_key, bob_pub_pem)

    c_a.request(
        protocol.CMD_MSG_1V1,
        {
            "recipient": "bob",
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "encrypted_key": base64.b64encode(encrypted_key).decode("ascii"),
            "iv": base64.b64encode(iv).decode("ascii"),
        },
    )
    _resp(c_a)
    _resp(c_b)

    row = servidor.db._conn.execute("SELECT * FROM direct_messages").fetchone()
    assert row is not None
    assert bytes(row["ciphertext"]) == ciphertext
    # o banco jamais guarda o texto em claro
    assert b"mensagem persistida" not in bytes(row["ciphertext"])

    c_a.close()
    c_b.close()


def test_msg_1v1_destinatario_inexistente(servidor):
    c = _cliente(servidor)
    _registrar_e_logar(c, "alice", "s3nh4A!")
    c.request(
        protocol.CMD_MSG_1V1,
        {
            "recipient": "fantasma",
            "ciphertext": base64.b64encode(b"x").decode("ascii"),
            "encrypted_key": base64.b64encode(b"y").decode("ascii"),
            "iv": base64.b64encode(b"z").decode("ascii"),
        },
    )
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    assert "destinatario nao encontrado" in r["message"]
    c.close()


def test_msg_1v1_sem_autenticacao(servidor):
    c = _cliente(servidor)
    c.request(
        protocol.CMD_MSG_1V1,
        {"recipient": "bob", "ciphertext": "x", "encrypted_key": "y", "iv": "z"},
    )
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao autenticado" in r["message"]
    c.close()


def test_msg_1v1_campos_faltando(servidor):
    c = _cliente(servidor)
    _registrar_e_logar(c, "alice", "s3nh4A!")
    c.request(protocol.CMD_MSG_1V1, {"recipient": "bob"})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    assert "obrigatorios" in r["message"]
    c.close()
