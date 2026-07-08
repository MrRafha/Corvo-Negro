"""Testes de autenticacao: register / login / logout (Sprint 1, Dia 3).

Cobre:
    - registro com sucesso
    - username duplicado
    - login com senha correta e errada
    - login com usuario inexistente
    - logout limpa a sessao
    - campos obrigatorios ausentes
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
    server._server_sock = __import__("socket").socket(
        socket.AF_INET, socket.SOCK_STREAM
    )
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


# --- register ----------------------------------------------------------------

def test_register_sucesso(servidor):
    c = _cliente(servidor)
    c.request(protocol.CMD_REGISTER, {"username": "corvo", "password": "s3nh4!"})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_OK
    assert r["data"]["username"] == "corvo"
    c.close()


def test_register_username_duplicado(servidor):
    c = _cliente(servidor)
    c.request(protocol.CMD_REGISTER, {"username": "corvo", "password": "s3nh4!"})
    _resp(c)  # descarta o primeiro (ok)
    c.request(protocol.CMD_REGISTER, {"username": "corvo", "password": "outra"})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    assert "ja esta em uso" in r["message"]
    c.close()


def test_register_sem_username(servidor):
    c = _cliente(servidor)
    c.request(protocol.CMD_REGISTER, {"username": "", "password": "s3nh4!"})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    c.close()


def test_register_sem_senha(servidor):
    c = _cliente(servidor)
    c.request(protocol.CMD_REGISTER, {"username": "corvo", "password": ""})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    c.close()


# --- login -------------------------------------------------------------------

def test_login_senha_correta(servidor):
    c = _cliente(servidor)
    c.request(protocol.CMD_REGISTER, {"username": "corvo", "password": "s3nh4!"})
    _resp(c)
    c.request(protocol.CMD_LOGIN, {"username": "corvo", "password": "s3nh4!"})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_OK
    assert "session_token" in r["data"]
    assert len(r["data"]["session_token"]) == 64  # 32 bytes hex
    c.close()


def test_login_senha_errada(servidor):
    c = _cliente(servidor)
    c.request(protocol.CMD_REGISTER, {"username": "corvo", "password": "s3nh4!"})
    _resp(c)
    c.request(protocol.CMD_LOGIN, {"username": "corvo", "password": "errada"})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    assert "credenciais invalidas" in r["message"]
    c.close()


def test_login_usuario_inexistente(servidor):
    c = _cliente(servidor)
    c.request(protocol.CMD_LOGIN, {"username": "fantasma", "password": "x"})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    assert "credenciais invalidas" in r["message"]
    c.close()


def test_login_marca_sessao_autenticada(servidor):
    c = _cliente(servidor)
    c.request(protocol.CMD_REGISTER, {"username": "corvo", "password": "s3nh4!"})
    _resp(c)
    c.request(protocol.CMD_LOGIN, {"username": "corvo", "password": "s3nh4!"})
    _resp(c)
    # apos o login, o servidor deve reconhecer o socket como autenticado
    sock_entry = list(servidor.sessions._sessions.values())
    autenticados = [s for s in sock_entry if s.get("user_id") is not None]
    assert len(autenticados) == 1
    assert autenticados[0]["username"] == "corvo"
    c.close()


# --- logout ------------------------------------------------------------------

def test_logout_limpa_sessao(servidor):
    c = _cliente(servidor)
    c.request(protocol.CMD_REGISTER, {"username": "corvo", "password": "s3nh4!"})
    _resp(c)
    c.request(protocol.CMD_LOGIN, {"username": "corvo", "password": "s3nh4!"})
    _resp(c)
    c.request(protocol.CMD_LOGOUT, {})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_OK
    # sessao volta para nao-autenticada
    sock_entry = list(servidor.sessions._sessions.values())
    autenticados = [s for s in sock_entry if s.get("user_id") is not None]
    assert len(autenticados) == 0
    c.close()
