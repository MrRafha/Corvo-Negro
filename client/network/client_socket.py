"""Cliente TCP com framing (Sprint 1, Dia 2).

class CorvoClient: connect, send, close.
Uma thread de recebimento le mensagens do servidor e as empurra numa
queue.Queue, para o consumer (CLI de teste hoje, GUI na Sprint 2) processar
sem bloquear a UI nem a thread de rede.
"""

from __future__ import annotations

import queue
import socket
import threading

from shared import protocol
from client import config


class CorvoClient:
    def __init__(self, host: str = config.SERVER_HOST, port: int = config.SERVER_PORT) -> None:
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None
        self._recv_thread: threading.Thread | None = None
        self._running = threading.Event()
        # Mensagens recebidas do servidor ficam aqui para o consumer puxar.
        self.inbox: "queue.Queue[dict]" = queue.Queue()

    # --- conexao --------------------------------------------------------------

    def connect(self, timeout: float = config.CONNECT_TIMEOUT) -> None:
        """Conecta ao servidor e inicia a thread de recebimento.

        Levanta OSError se nao conseguir conectar (usado para decidir
        ONLINE vs LAN na Sprint 3).
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((self.host, self.port))
        sock.settimeout(None)  # blocking apos conectar (a thread cuida do recv)
        self._sock = sock
        self._running.set()
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()

    def is_connected(self) -> bool:
        return self._running.is_set() and self._sock is not None

    # --- envio ----------------------------------------------------------------

    def send(self, message: dict) -> None:
        """Envia um dict ja montado (use protocol.make_request para montar)."""
        if self._sock is None:
            raise ConnectionError("cliente nao esta conectado")
        self._sock.sendall(protocol.pack_message(message))

    def request(self, cmd: str, data: dict | None = None, session_token: str | None = None) -> None:
        """Atalho: monta e envia um request C->S."""
        self.send(protocol.make_request(cmd, data, session_token))

    # --- recebimento ----------------------------------------------------------

    def _recv_loop(self) -> None:
        """Le mensagens do servidor e as coloca na inbox ate a conexao cair."""
        try:
            while self._running.is_set():
                try:
                    message = protocol.unpack_message(self._sock)
                except protocol.ProtocolError:
                    continue  # frame corrompido: ignora e segue
                except OSError:
                    break
                if message is None:
                    break  # servidor fechou
                self.inbox.put(message)
        finally:
            self._running.clear()
            # Sentinela para o consumer saber que a conexao encerrou.
            self.inbox.put({"cmd": "_DISCONNECTED"})

    # --- encerramento ---------------------------------------------------------

    def close(self) -> None:
        """Fecha a conexao e para a thread de recebimento."""
        self._running.clear()
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
