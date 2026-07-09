"""Testes do ClientBridge: dispatcher de inbox response-vs-evento (Sprint 2, Dia 8).

Cobre:
    - call() com sucesso invoca on_ok com os dados da resposta
    - call() com erro invoca on_error com a mensagem
    - eventos de broadcast (nao atrelados a nenhum request pendente) disparam
      os listeners registrados via on()
    - um evento chegando ENTRE um request e sua resposta nao e confundido com
      a resposta (o problema que o cli_test.py tinha e que o bridge resolve)
    - PING/PONG (comando sem sufixo _RESPONSE) tambem correlaciona corretamente
    - _DISCONNECTED dispara o listener registrado para ele
"""

import socket
import threading

import pytest

from shared import protocol
from server.main import CorvoServer
from client.network.client_socket import CorvoClient
from client.network.gui_bridge import ClientBridge


class _FakeTkRoot:
    """Substitui o Tk real: `after` so guarda o callback, roda quando `pump()` e chamado."""

    def __init__(self):
        self._scheduled: list = []

    def after(self, _delay_ms, callback):
        self._scheduled.append(callback)

    def pump(self, rounds: int = 1) -> None:
        for _ in range(rounds):
            if not self._scheduled:
                return
            callback = self._scheduled.pop(0)
            callback()


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


def _bridge(servidor) -> tuple[ClientBridge, _FakeTkRoot]:
    root = _FakeTkRoot()
    bridge = ClientBridge(root, CorvoClient(host="127.0.0.1", port=servidor.port))
    bridge.connect()
    bridge.start_polling()
    return bridge, root


def _wait_until(root: _FakeTkRoot, predicate, tries: int = 50) -> None:
    """Bombeia o poll loop ate `predicate()` ser verdadeiro ou esgotar tentativas."""
    import time

    for _ in range(tries):
        root.pump()
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("predicate nunca ficou verdadeiro")


# --- call() basico -----------------------------------------------------------

def test_call_sucesso_invoca_on_ok(servidor):
    bridge, root = _bridge(servidor)
    resultado = {}

    bridge.call("PING", {}, on_ok=lambda data: resultado.update(ok=True, data=data))
    _wait_until(root, lambda: resultado.get("ok"))

    assert resultado["ok"] is True
    bridge.close()


def test_call_erro_invoca_on_error(servidor):
    bridge, root = _bridge(servidor)
    resultado = {}

    bridge.call(
        protocol.CMD_LOGIN,
        {"username": "fantasma", "password": "x"},
        on_ok=lambda data: resultado.update(ok=True),
        on_error=lambda msg: resultado.update(erro=msg),
    )
    _wait_until(root, lambda: "erro" in resultado)

    assert "erro" in resultado
    assert "credenciais invalidas" in resultado["erro"]
    assert "ok" not in resultado
    bridge.close()


def test_register_e_login_via_bridge(servidor):
    bridge, root = _bridge(servidor)
    resultado = {}

    bridge.call(
        protocol.CMD_REGISTER,
        {"username": "alice", "password": "s3nh4!"},
        on_ok=lambda data: resultado.update(registrado=True),
    )
    _wait_until(root, lambda: resultado.get("registrado"))

    bridge.call(
        protocol.CMD_LOGIN,
        {"username": "alice", "password": "s3nh4!"},
        on_ok=lambda data: resultado.update(logado=True, user_id=data["user_id"]),
    )
    _wait_until(root, lambda: resultado.get("logado"))

    assert resultado["user_id"] is not None
    bridge.close()


# --- eventos de broadcast ------------------------------------------------------

def test_evento_broadcast_dispara_listener(servidor):
    dono_bridge, dono_root = _bridge(servidor)
    membro_bridge, membro_root = _bridge(servidor)

    _registrar_e_logar(dono_bridge, dono_root, "alice", "s3nh4A!")
    _registrar_e_logar(membro_bridge, membro_root, "bob", "s3nh4B!")

    forum_info = {}
    dono_bridge.call(
        protocol.CMD_CREATE_FORUM,
        {"name": "Corvos da Noite"},
        on_ok=lambda data: forum_info.update(data),
    )
    _wait_until(dono_root, lambda: "invite_code" in forum_info)

    eventos_recebidos = []
    dono_bridge.on(protocol.EVT_MEMBER_JOINED, lambda data: eventos_recebidos.append(data))

    membro_bridge.call(
        protocol.CMD_JOIN_FORUM, {"invite_code": forum_info["invite_code"]}
    )
    _wait_until(dono_root, lambda: len(eventos_recebidos) == 1)

    assert eventos_recebidos[0]["username"] == "bob"
    dono_bridge.close()
    membro_bridge.close()


def test_evento_entre_request_e_resposta_nao_confunde(servidor):
    """O bug que o cli_test.py tinha: um evento chegando antes da resposta do
    request atual nao deve ser tratado como se fosse aquela resposta."""
    dono_bridge, dono_root = _bridge(servidor)
    membro_bridge, membro_root = _bridge(servidor)

    _registrar_e_logar(dono_bridge, dono_root, "alice", "s3nh4A!")
    _registrar_e_logar(membro_bridge, membro_root, "bob", "s3nh4B!")

    forum_info = {}
    dono_bridge.call(
        protocol.CMD_CREATE_FORUM,
        {"name": "Corvos da Noite"},
        on_ok=lambda data: forum_info.update(data),
    )
    _wait_until(dono_root, lambda: "invite_code" in forum_info)

    membro_bridge.call(protocol.CMD_JOIN_FORUM, {"invite_code": forum_info["invite_code"]})
    _wait_until(membro_root, lambda: True)  # deixa o join acontecer

    # Agora o dono dispara outro request (LIST_MY_FORUMS) logo depois de um
    # MEMBER_JOINED ja ter sido enfileirado pelo join do bob. O bridge precisa
    # associar a resposta certa ao LIST_MY_FORUMS, nao ao evento.
    list_result = {}
    dono_bridge.call(
        protocol.CMD_LIST_MY_FORUMS, {}, on_ok=lambda data: list_result.update(data)
    )
    _wait_until(dono_root, lambda: "forums" in list_result)

    assert isinstance(list_result["forums"], list)
    assert len(list_result["forums"]) == 1

    dono_bridge.close()
    membro_bridge.close()


def test_disconnected_dispara_listener(servidor):
    bridge, root = _bridge(servidor)
    disconnected = {}
    bridge.on("_DISCONNECTED", lambda data: disconnected.update(fired=True))

    bridge.client.close()
    _wait_until(root, lambda: disconnected.get("fired"))

    assert disconnected["fired"] is True


def _registrar_e_logar(bridge: ClientBridge, root: _FakeTkRoot, username: str, password: str) -> None:
    done = {}
    bridge.call(
        protocol.CMD_REGISTER, {"username": username, "password": password},
        on_ok=lambda data: done.update(registrado=True),
    )
    _wait_until(root, lambda: done.get("registrado"))
    bridge.call(
        protocol.CMD_LOGIN, {"username": username, "password": password},
        on_ok=lambda data: done.update(logado=True),
    )
    _wait_until(root, lambda: done.get("logado"))
