"""Testes: E2E em grupo - chave AES por forum e mensagens roteadas (Sprint 1, Dia 6).

Cobre:
    - distribute_key: dono distribui a AES key para um membro, que decifra corretamente
    - distribute_key falha se quem chama nao e o dono
    - distribute_key falha se o destinatario nao e membro do forum
    - send_to_forum: persiste e roteia so para membros online (nao decifra)
    - send_to_forum falha se quem envia nao e membro
    - get_history: retorna as mensagens em ordem, cliente decifra com a key_version certa
    - get_history falha para quem nao e membro
    - fluxo completo: 3 membros, mensagens circulando, um sai e o dono rotaciona a chave
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


def _get_pubkey(client: CorvoClient, username: str) -> bytes:
    client.request(protocol.CMD_GET_PUBKEY, {"username": username})
    r = _resp(client)
    assert r["status"] == protocol.STATUS_OK
    return r["data"]["public_key"].encode("utf-8")


def _distribuir_chave(client, forum_id, recipient_username, recipient_pub_pem, aes_key, key_version):
    encrypted_aes_key = crypto_utils.rsa_encrypt(aes_key, recipient_pub_pem)
    client.request(
        protocol.CMD_DISTRIBUTE_KEY,
        {
            "forum_id": forum_id,
            "recipient": recipient_username,
            "encrypted_aes_key": base64.b64encode(encrypted_aes_key).decode("ascii"),
            "key_version": key_version,
        },
    )
    return _resp(client)


# --- distribute_key ------------------------------------------------------------

def test_distribute_key_sucesso(servidor):
    dono = _cliente(servidor)
    priv_dono = _registrar_e_logar(dono, "alice", "s3nh4A!")
    dono.request(protocol.CMD_CREATE_FORUM, {"name": "Corvos da Noite"})
    r = _resp(dono)
    forum_id = r["data"]["forum_id"]

    membro = _cliente(servidor)
    priv_membro = _registrar_e_logar(membro, "bob", "s3nh4B!")
    membro_pub_pem = _get_pubkey(dono, "bob")

    membro.request(protocol.CMD_JOIN_FORUM, {"invite_code": r["data"]["invite_code"]})
    _resp(membro)
    _resp(dono)  # descarta MEMBER_JOINED

    aes_key = crypto_utils.generate_aes_key()
    r = _distribuir_chave(dono, forum_id, "bob", membro_pub_pem, aes_key, 1)
    assert r["status"] == protocol.STATUS_OK

    evt = _resp(membro)
    assert evt["cmd"] == protocol.EVT_KEY_ROTATED
    recv_key = crypto_utils.rsa_decrypt(base64.b64decode(evt["data"]["encrypted_aes_key"]), priv_membro)
    assert recv_key == aes_key

    dono.close()
    membro.close()


def test_distribute_key_apenas_dono(servidor):
    dono = _cliente(servidor)
    _registrar_e_logar(dono, "alice", "s3nh4A!")
    dono.request(protocol.CMD_CREATE_FORUM, {"name": "Corvos da Noite"})
    r = _resp(dono)
    forum_id = r["data"]["forum_id"]
    invite_code = r["data"]["invite_code"]

    membro = _cliente(servidor)
    _registrar_e_logar(membro, "bob", "s3nh4B!")
    membro.request(protocol.CMD_JOIN_FORUM, {"invite_code": invite_code})
    _resp(membro)
    _resp(dono)

    aes_key = crypto_utils.generate_aes_key()
    encrypted = crypto_utils.rsa_encrypt(aes_key, _get_pubkey(dono, "alice"))
    membro.request(
        protocol.CMD_DISTRIBUTE_KEY,
        {
            "forum_id": forum_id,
            "recipient": "alice",
            "encrypted_aes_key": base64.b64encode(encrypted).decode("ascii"),
            "key_version": 1,
        },
    )
    r = _resp(membro)
    assert r["status"] == protocol.STATUS_ERROR
    assert "apenas o dono" in r["message"]

    dono.close()
    membro.close()


def test_distribute_key_destinatario_nao_e_membro(servidor):
    dono = _cliente(servidor)
    _registrar_e_logar(dono, "alice", "s3nh4A!")
    dono.request(protocol.CMD_CREATE_FORUM, {"name": "Corvos da Noite"})
    r = _resp(dono)
    forum_id = r["data"]["forum_id"]

    fora = _cliente(servidor)
    _registrar_e_logar(fora, "fantasma", "s3nh4F!")
    fora_pub_pem = _get_pubkey(dono, "fantasma")

    aes_key = crypto_utils.generate_aes_key()
    r = _distribuir_chave(dono, forum_id, "fantasma", fora_pub_pem, aes_key, 1)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao e membro" in r["message"]

    dono.close()
    fora.close()


# --- send_to_forum ---------------------------------------------------------------

def test_send_to_forum_fim_a_fim(servidor):
    dono = _cliente(servidor)
    _registrar_e_logar(dono, "alice", "s3nh4A!")
    dono.request(protocol.CMD_CREATE_FORUM, {"name": "Corvos da Noite"})
    r = _resp(dono)
    forum_id, invite_code = r["data"]["forum_id"], r["data"]["invite_code"]

    membro = _cliente(servidor)
    _registrar_e_logar(membro, "bob", "s3nh4B!")
    membro.request(protocol.CMD_JOIN_FORUM, {"invite_code": invite_code})
    _resp(membro)
    _resp(dono)

    aes_key = crypto_utils.generate_aes_key()
    texto = "as palavras dos mortos viajam em asas negras"
    ciphertext, iv = crypto_utils.aes_encrypt(texto.encode("utf-8"), aes_key)

    dono.request(
        protocol.CMD_SEND_TO_FORUM,
        {
            "forum_id": forum_id,
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "iv": base64.b64encode(iv).decode("ascii"),
            "key_version": 1,
        },
    )
    r = _resp(dono)
    assert r["status"] == protocol.STATUS_OK

    evt = _resp(membro)
    assert evt["cmd"] == protocol.EVT_NEW_MESSAGE
    assert evt["data"]["sender"] == "alice"
    recv_plain = crypto_utils.aes_decrypt(
        base64.b64decode(evt["data"]["ciphertext"]), aes_key, base64.b64decode(evt["data"]["iv"])
    )
    assert recv_plain.decode("utf-8") == texto

    dono.close()
    membro.close()


def test_send_to_forum_nao_membro(servidor):
    dono = _cliente(servidor)
    _registrar_e_logar(dono, "alice", "s3nh4A!")
    dono.request(protocol.CMD_CREATE_FORUM, {"name": "Corvos da Noite"})
    r = _resp(dono)
    forum_id = r["data"]["forum_id"]

    fora = _cliente(servidor)
    _registrar_e_logar(fora, "fantasma", "s3nh4F!")
    fora.request(
        protocol.CMD_SEND_TO_FORUM,
        {"forum_id": forum_id, "ciphertext": "eA==", "iv": "eQ==", "key_version": 1},
    )
    r = _resp(fora)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao e membro" in r["message"]

    dono.close()
    fora.close()


def test_send_to_forum_sem_autenticacao(servidor):
    c = _cliente(servidor)
    c.request(
        protocol.CMD_SEND_TO_FORUM,
        {"forum_id": 1, "ciphertext": "eA==", "iv": "eQ==", "key_version": 1},
    )
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao autenticado" in r["message"]
    c.close()


# --- get_history -----------------------------------------------------------------

def test_get_history_retorna_em_ordem(servidor):
    dono = _cliente(servidor)
    _registrar_e_logar(dono, "alice", "s3nh4A!")
    dono.request(protocol.CMD_CREATE_FORUM, {"name": "Corvos da Noite"})
    r = _resp(dono)
    forum_id = r["data"]["forum_id"]

    aes_key = crypto_utils.generate_aes_key()
    for texto in ["primeira", "segunda", "terceira"]:
        ciphertext, iv = crypto_utils.aes_encrypt(texto.encode("utf-8"), aes_key)
        dono.request(
            protocol.CMD_SEND_TO_FORUM,
            {
                "forum_id": forum_id,
                "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
                "iv": base64.b64encode(iv).decode("ascii"),
                "key_version": 1,
            },
        )
        _resp(dono)

    dono.request(protocol.CMD_GET_HISTORY, {"forum_id": forum_id})
    r = _resp(dono)
    assert r["status"] == protocol.STATUS_OK
    mensagens = r["data"]["messages"]
    assert len(mensagens) == 3

    textos_decifrados = [
        crypto_utils.aes_decrypt(
            base64.b64decode(m["ciphertext"]), aes_key, base64.b64decode(m["iv"])
        ).decode("utf-8")
        for m in mensagens
    ]
    assert textos_decifrados == ["primeira", "segunda", "terceira"]

    dono.close()


def test_get_history_nao_membro(servidor):
    dono = _cliente(servidor)
    _registrar_e_logar(dono, "alice", "s3nh4A!")
    dono.request(protocol.CMD_CREATE_FORUM, {"name": "Corvos da Noite"})
    r = _resp(dono)
    forum_id = r["data"]["forum_id"]

    fora = _cliente(servidor)
    _registrar_e_logar(fora, "fantasma", "s3nh4F!")
    fora.request(protocol.CMD_GET_HISTORY, {"forum_id": forum_id})
    r = _resp(fora)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao e membro" in r["message"]

    dono.close()
    fora.close()


# --- fluxo completo: 3 membros, alguem sai, chave rotaciona -----------------------

def test_fluxo_completo_grupo_com_rotacao(servidor):
    alice = _cliente(servidor)
    priv_alice = _registrar_e_logar(alice, "alice", "s3nh4A!")
    alice.request(protocol.CMD_CREATE_FORUM, {"name": "Corvos da Noite"})
    r = _resp(alice)
    forum_id, invite_code = r["data"]["forum_id"], r["data"]["invite_code"]

    bob = _cliente(servidor)
    priv_bob = _registrar_e_logar(bob, "bob", "s3nh4B!")
    carol = _cliente(servidor)
    priv_carol = _registrar_e_logar(carol, "carol", "s3nh4C!")

    # bob e carol entram; alice (dona, online) recebe os MEMBER_JOINED e distribui a v1.
    bob.request(protocol.CMD_JOIN_FORUM, {"invite_code": invite_code})
    _resp(bob)
    _resp(alice)  # MEMBER_JOINED (bob)

    carol.request(protocol.CMD_JOIN_FORUM, {"invite_code": invite_code})
    _resp(carol)
    _resp(alice)  # MEMBER_JOINED (carol)
    _resp(bob)  # bob ja era membro, tambem recebe o MEMBER_JOINED (carol)

    aes_v1 = crypto_utils.generate_aes_key()
    _distribuir_chave(alice, forum_id, "bob", _get_pubkey(alice, "bob"), aes_v1, 1)
    evt_bob = _resp(bob)
    assert evt_bob["data"]["key_version"] == 1

    _distribuir_chave(alice, forum_id, "carol", _get_pubkey(alice, "carol"), aes_v1, 1)
    evt_carol = _resp(carol)
    assert evt_carol["data"]["key_version"] == 1

    # mensagem circula entre os 3 com a v1
    texto = "reuniao ao anoitecer"
    ciphertext, iv = crypto_utils.aes_encrypt(texto.encode("utf-8"), aes_v1)
    alice.request(
        protocol.CMD_SEND_TO_FORUM,
        {
            "forum_id": forum_id,
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "iv": base64.b64encode(iv).decode("ascii"),
            "key_version": 1,
        },
    )
    _resp(alice)
    msg_bob = _resp(bob)
    msg_carol = _resp(carol)
    assert crypto_utils.aes_decrypt(
        base64.b64decode(msg_bob["data"]["ciphertext"]), aes_v1, base64.b64decode(msg_bob["data"]["iv"])
    ).decode("utf-8") == texto
    assert crypto_utils.aes_decrypt(
        base64.b64decode(msg_carol["data"]["ciphertext"]), aes_v1, base64.b64decode(msg_carol["data"]["iv"])
    ).decode("utf-8") == texto

    # bob sai: alice (dona) e carol (que ficou) sao notificadas
    bob.request(protocol.CMD_LEAVE_FORUM, {"forum_id": forum_id})
    _resp(bob)
    evt_left = _resp(alice)
    assert evt_left["cmd"] == protocol.EVT_MEMBER_LEFT
    assert evt_left["data"]["username"] == "bob"
    assert set(evt_left["data"]["remaining_members"]) == {"alice", "carol"}
    _resp(carol)  # carol tambem recebe o MEMBER_LEFT (continua no forum)

    aes_v2 = crypto_utils.generate_aes_key()
    _distribuir_chave(alice, forum_id, "carol", _get_pubkey(alice, "carol"), aes_v2, 2)
    evt_carol_v2 = _resp(carol)
    assert evt_carol_v2["data"]["key_version"] == 2
    recv_v2 = crypto_utils.rsa_decrypt(
        base64.b64decode(evt_carol_v2["data"]["encrypted_aes_key"]), priv_carol
    )
    assert recv_v2 == aes_v2

    # nova mensagem com a v2: carol decifra, bob (fora do forum) nunca recebe nada
    texto2 = "chave rotacionada, sigam em frente"
    ciphertext2, iv2 = crypto_utils.aes_encrypt(texto2.encode("utf-8"), aes_v2)
    alice.request(
        protocol.CMD_SEND_TO_FORUM,
        {
            "forum_id": forum_id,
            "ciphertext": base64.b64encode(ciphertext2).decode("ascii"),
            "iv": base64.b64encode(iv2).decode("ascii"),
            "key_version": 2,
        },
    )
    _resp(alice)
    msg_carol_v2 = _resp(carol)
    assert crypto_utils.aes_decrypt(
        base64.b64decode(msg_carol_v2["data"]["ciphertext"]), aes_v2, base64.b64decode(msg_carol_v2["data"]["iv"])
    ).decode("utf-8") == texto2

    alice.close()
    bob.close()
    carol.close()
