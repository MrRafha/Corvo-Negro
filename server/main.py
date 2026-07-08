"""Entry point do servidor Corvo Negro.

Socket TCP threaded: bind, listen, uma thread por cliente, loop recv que
despacha para o Router. O servidor apenas ROTEIA mensagens (cifradas) - jamais
tem acesso ao conteudo em claro.

Uso:
    python -m server.main
Sobe em HOST:PORT definidos em server/config.py (0.0.0.0:9999 por padrao).
"""

from __future__ import annotations

import socket
import threading

from shared import protocol
from server import config
from server.database import Database
from server.router import Router
from server.session_manager import SessionManager


class CorvoServer:
    def __init__(self, host: str = config.HOST, port: int = config.PORT, db_path: str = config.DB_PATH) -> None:
        self.host = host
        self.port = port
        self.db = Database(db_path)
        self.db.init_schema()
        self.sessions = SessionManager()
        self.router = Router(self.sessions, self.db)
        self._server_sock: socket.socket | None = None
        self._running = threading.Event()

    def start(self) -> None:
        """Sobe o servidor e aceita conexoes ate stop() ser chamado."""
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen()
        self._running.set()
        print(f"[Corvo Negro] servidor ouvindo em {self.host}:{self.port}")

        try:
            while self._running.is_set():
                try:
                    client_sock, addr = self._server_sock.accept()
                except OSError:
                    break  # socket fechado por stop()
                thread = threading.Thread(
                    target=self._handle_client, args=(client_sock, addr), daemon=True
                )
                thread.start()
        finally:
            self.stop()

    def stop(self) -> None:
        """Encerra o servidor e fecha o socket de escuta."""
        if not self._running.is_set():
            return
        self._running.clear()
        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except OSError:
                pass
            self._server_sock = None
        print("[Corvo Negro] servidor encerrado")

    def _handle_client(self, sock: socket.socket, addr) -> None:
        """Loop de atendimento de um cliente (roda em thread propria)."""
        print(f"[Corvo Negro] conexao de {addr}")
        self.sessions.add(sock)
        try:
            while self._running.is_set():
                try:
                    message = protocol.unpack_message(sock)
                except protocol.ProtocolError as exc:
                    self.sessions.unicast(
                        sock,
                        protocol.make_response(
                            "ERROR", protocol.STATUS_ERROR, message=str(exc)
                        ),
                    )
                    continue
                if message is None:
                    break  # cliente desconectou
                response = self.router.dispatch(message, sock)
                if response is not None:
                    self.sessions.unicast(sock, response)
        except OSError:
            pass
        finally:
            self.sessions.remove(sock)
            try:
                sock.close()
            except OSError:
                pass
            print(f"[Corvo Negro] {addr} desconectou")


def main() -> None:
    server = CorvoServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
