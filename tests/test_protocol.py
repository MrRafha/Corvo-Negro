"""Testes do protocolo TCP: framing + integracao servidor/cliente (Dia 2)."""

import socket
import struct
import threading
import time

import pytest

from shared import protocol
from server.main import CorvoServer
from client.network.client_socket import CorvoClient


# --- Framing (sem rede) -------------------------------------------------------

def test_pack_message_tem_prefixo_de_tamanho():
    frame = protocol.pack_message({"cmd": "PING"})
    # 4 bytes de tamanho + payload; o prefixo deve bater com o resto.
    (length,) = struct.unpack(">I", frame[:4])
    assert length == len(frame) - 4


def test_pack_unpack_round_trip_via_socketpair():
    a, b = socket.socketpair()
    try:
        original = {"cmd": "ECHO", "data": {"texto": "corvo voa alto"}}
        a.sendall(protocol.pack_message(original))
        recebido = protocol.unpack_message(b)
        assert recebido == original
    finally:
        a.close()
        b.close()


def test_unpack_retorna_none_quando_conexao_fecha():
    a, b = socket.socketpair()
    a.close()  # fecha antes de enviar qualquer coisa
    try:
        assert protocol.unpack_message(b) is None
    finally:
        b.close()


def test_pack_message_rejeita_payload_nao_serializavel():
    with pytest.raises(protocol.ProtocolError):
        protocol.pack_message({"cmd": "X", "data": {"obj": object()}})


def test_unpack_message_multiplas_mensagens_em_sequencia():
    a, b = socket.socketpair()
    try:
        a.sendall(protocol.pack_message({"n": 1}))
        a.sendall(protocol.pack_message({"n": 2}))
        assert protocol.unpack_message(b) == {"n": 1}
        assert protocol.unpack_message(b) == {"n": 2}
    finally:
        a.close()
        b.close()


# --- Integracao servidor <-> cliente -----------------------------------------

@pytest.fixture
def servidor():
    """Sobe um CorvoServer em porta efemera e o encerra ao fim do teste."""
    server = CorvoServer(host="127.0.0.1", port=0, db_path=":memory:")
    # bind manual em porta 0 para descobrir a porta atribuida pelo SO.
    server._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server._server_sock.bind((server.host, 0))
    server.port = server._server_sock.getsockname()[1]
    server._server_sock.listen()
    server._running.set()

    thread = threading.Thread(target=_accept_loop, args=(server,), daemon=True)
    thread.start()
    yield server
    server.stop()


def _accept_loop(server: CorvoServer) -> None:
    while server._running.is_set():
        try:
            client_sock, addr = server._server_sock.accept()
        except OSError:
            break
        t = threading.Thread(target=server._handle_client, args=(client_sock, addr), daemon=True)
        t.start()


def _esperar_resposta(client: CorvoClient, timeout: float = 2.0) -> dict:
    return client.inbox.get(timeout=timeout)


def test_ping_pong(servidor):
    client = CorvoClient(host="127.0.0.1", port=servidor.port)
    client.connect()
    try:
        client.request("PING")
        resp = _esperar_resposta(client)
        assert resp["cmd"] == "PONG"
        assert resp["status"] == protocol.STATUS_OK
    finally:
        client.close()


def test_echo_devolve_data(servidor):
    client = CorvoClient(host="127.0.0.1", port=servidor.port)
    client.connect()
    try:
        client.request("ECHO", {"texto": "olá corvo"})
        resp = _esperar_resposta(client)
        assert resp["cmd"] == "ECHO_RESPONSE"
        assert resp["data"] == {"texto": "olá corvo"}
    finally:
        client.close()


def test_comando_desconhecido_retorna_erro(servidor):
    client = CorvoClient(host="127.0.0.1", port=servidor.port)
    client.connect()
    try:
        client.request("NAO_EXISTE")
        resp = _esperar_resposta(client)
        assert resp["status"] == protocol.STATUS_ERROR
    finally:
        client.close()


def test_tres_clientes_simultaneos(servidor):
    """3 clientes conectam ao mesmo tempo e cada um recebe seu proprio echo."""
    clients = [CorvoClient(host="127.0.0.1", port=servidor.port) for _ in range(3)]
    for c in clients:
        c.connect()
    try:
        for i, c in enumerate(clients):
            c.request("ECHO", {"id": i})
        # cada cliente deve receber de volta o SEU id (roteamento por socket).
        for i, c in enumerate(clients):
            resp = _esperar_resposta(c)
            assert resp["data"] == {"id": i}
        # os 3 devem estar registrados no session manager.
        time.sleep(0.1)
        assert len(servidor.sessions._sessions) == 3
    finally:
        for c in clients:
            c.close()
