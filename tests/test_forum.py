"""Testes de foruns: create / join / leave / list (Sprint 1, Dia 5).

Cobre:
    - criacao de forum gera codigo de convite e o dono ja e membro
    - join com codigo valido adiciona o membro e notifica os demais
    - join com codigo invalido falha
    - join duplicado (ja e membro) falha
    - leave remove o membro e notifica os que restaram
    - leave de forum que o usuario nao pertence falha
    - list_my_forums lista so os foruns do usuario autenticado
    - todos os handlers exigem autenticacao
"""

import socket
import threading

import pytest

from shared import protocol
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


def _registrar_e_logar(client: CorvoClient, username: str, password: str) -> None:
    client.request(protocol.CMD_REGISTER, {"username": username, "password": password})
    _resp(client)
    client.request(protocol.CMD_LOGIN, {"username": username, "password": password})
    _resp(client)


# --- create_forum --------------------------------------------------------------

def test_create_forum_sucesso(servidor):
    c = _cliente(servidor)
    _registrar_e_logar(c, "corvo", "s3nh4!")

    c.request(protocol.CMD_CREATE_FORUM, {"name": "Corvos da Noite"})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_OK
    assert r["data"]["name"] == "Corvos da Noite"
    assert r["data"]["invite_code"].startswith("CORVO-")
    assert len(r["data"]["invite_code"]) == len("CORVO-XXXX-XXXX")
    c.close()


def test_create_forum_sem_nome(servidor):
    c = _cliente(servidor)
    _registrar_e_logar(c, "corvo", "s3nh4!")
    c.request(protocol.CMD_CREATE_FORUM, {"name": ""})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    c.close()


def test_create_forum_sem_autenticacao(servidor):
    c = _cliente(servidor)
    c.request(protocol.CMD_CREATE_FORUM, {"name": "Corvos da Noite"})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao autenticado" in r["message"]
    c.close()


def test_dono_ja_e_membro_apos_criar(servidor):
    c = _cliente(servidor)
    _registrar_e_logar(c, "corvo", "s3nh4!")
    c.request(protocol.CMD_CREATE_FORUM, {"name": "Corvos da Noite"})
    r = _resp(c)
    forum_id = r["data"]["forum_id"]

    c.request(protocol.CMD_LIST_MY_FORUMS, {})
    r = _resp(c)
    assert any(f["forum_id"] == forum_id for f in r["data"]["forums"])
    c.close()


# --- join_forum ------------------------------------------------------------------

def test_join_forum_sucesso(servidor):
    dono = _cliente(servidor)
    _registrar_e_logar(dono, "alice", "s3nh4A!")
    dono.request(protocol.CMD_CREATE_FORUM, {"name": "Corvos da Noite"})
    r = _resp(dono)
    invite_code = r["data"]["invite_code"]
    forum_id = r["data"]["forum_id"]

    membro = _cliente(servidor)
    _registrar_e_logar(membro, "bob", "s3nh4B!")
    membro.request(protocol.CMD_JOIN_FORUM, {"invite_code": invite_code})
    r = _resp(membro)
    assert r["status"] == protocol.STATUS_OK
    assert r["data"]["forum_id"] == forum_id

    # o dono, que ficou online, recebe a notificacao de novo membro
    evt = _resp(dono)
    assert evt["cmd"] == protocol.EVT_MEMBER_JOINED
    assert evt["data"]["username"] == "bob"

    dono.close()
    membro.close()


def test_join_forum_codigo_invalido(servidor):
    c = _cliente(servidor)
    _registrar_e_logar(c, "corvo", "s3nh4!")
    c.request(protocol.CMD_JOIN_FORUM, {"invite_code": "CORVO-0000-0000"})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    assert "invalido" in r["message"]
    c.close()


def test_join_forum_ja_e_membro(servidor):
    dono = _cliente(servidor)
    _registrar_e_logar(dono, "alice", "s3nh4A!")
    dono.request(protocol.CMD_CREATE_FORUM, {"name": "Corvos da Noite"})
    r = _resp(dono)
    invite_code = r["data"]["invite_code"]

    # o proprio dono tenta entrar de novo no forum que ja pertence
    dono.request(protocol.CMD_JOIN_FORUM, {"invite_code": invite_code})
    r = _resp(dono)
    assert r["status"] == protocol.STATUS_ERROR
    assert "ja e membro" in r["message"]
    dono.close()


def test_join_forum_sem_autenticacao(servidor):
    c = _cliente(servidor)
    c.request(protocol.CMD_JOIN_FORUM, {"invite_code": "CORVO-0000-0000"})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao autenticado" in r["message"]
    c.close()


# --- leave_forum -----------------------------------------------------------------

def test_leave_forum_sucesso(servidor):
    dono = _cliente(servidor)
    _registrar_e_logar(dono, "alice", "s3nh4A!")
    dono.request(protocol.CMD_CREATE_FORUM, {"name": "Corvos da Noite"})
    r = _resp(dono)
    invite_code = r["data"]["invite_code"]
    forum_id = r["data"]["forum_id"]

    membro = _cliente(servidor)
    _registrar_e_logar(membro, "bob", "s3nh4B!")
    membro.request(protocol.CMD_JOIN_FORUM, {"invite_code": invite_code})
    _resp(membro)
    _resp(dono)  # descarta o MEMBER_JOINED

    membro.request(protocol.CMD_LEAVE_FORUM, {"forum_id": forum_id})
    r = _resp(membro)
    assert r["status"] == protocol.STATUS_OK

    # o dono, que continua no forum, recebe a notificacao de saida
    evt = _resp(dono)
    assert evt["cmd"] == protocol.EVT_MEMBER_LEFT
    assert evt["data"]["username"] == "bob"

    dono.close()
    membro.close()


def test_leave_forum_nao_e_membro(servidor):
    dono = _cliente(servidor)
    _registrar_e_logar(dono, "alice", "s3nh4A!")
    dono.request(protocol.CMD_CREATE_FORUM, {"name": "Corvos da Noite"})
    r = _resp(dono)
    forum_id = r["data"]["forum_id"]

    outro = _cliente(servidor)
    _registrar_e_logar(outro, "bob", "s3nh4B!")
    outro.request(protocol.CMD_LEAVE_FORUM, {"forum_id": forum_id})
    r = _resp(outro)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao e membro" in r["message"]

    dono.close()
    outro.close()


def test_leave_forum_inexistente(servidor):
    c = _cliente(servidor)
    _registrar_e_logar(c, "corvo", "s3nh4!")
    c.request(protocol.CMD_LEAVE_FORUM, {"forum_id": 999})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao encontrado" in r["message"]
    c.close()


# --- list_my_forums --------------------------------------------------------------

def test_list_my_forums_isola_por_usuario(servidor):
    alice = _cliente(servidor)
    _registrar_e_logar(alice, "alice", "s3nh4A!")
    alice.request(protocol.CMD_CREATE_FORUM, {"name": "Forum da Alice"})
    _resp(alice)

    bob = _cliente(servidor)
    _registrar_e_logar(bob, "bob", "s3nh4B!")
    bob.request(protocol.CMD_LIST_MY_FORUMS, {})
    r = _resp(bob)
    assert r["data"]["forums"] == []

    alice.close()
    bob.close()


def test_list_my_forums_sem_autenticacao(servidor):
    c = _cliente(servidor)
    c.request(protocol.CMD_LIST_MY_FORUMS, {})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao autenticado" in r["message"]
    c.close()
