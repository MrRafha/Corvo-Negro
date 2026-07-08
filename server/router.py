"""Despachador de mensagens: mapeia cmd -> handler.

Recebe o dict ja desempacotado (protocol.unpack_message) e a sessao do cliente,
e chama o handler registrado para aquele `cmd`. Os handlers de dominio (auth,
forum, message, role, key_exchange) sao registrados aqui conforme sao
implementados nos dias seguintes da Sprint 1.

Assinatura de um handler:
    handler(data: dict, ctx: HandlerContext) -> dict | None

Retornar um dict => o router o envia de volta como response para o cliente.
Retornar None  => o handler ja cuidou do envio (ex.: broadcast) ou nada a
responder.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Callable

from shared import protocol
from server.session_manager import SessionManager
from server.database import Database

Handler = Callable[[dict, "HandlerContext"], "dict | None"]


@dataclass
class HandlerContext:
    """Contexto passado a cada handler."""
    sock: socket.socket
    sessions: SessionManager
    db: Database


class Router:
    def __init__(self, sessions: SessionManager, db: Database) -> None:
        self.sessions = sessions
        self.db = db
        self._handlers: dict[str, Handler] = {}
        self._register_builtin()
        self._register_auth()
        self._register_key_exchange()
        self._register_message()

    def register(self, cmd: str, handler: Handler) -> None:
        """Registra o handler de um comando."""
        self._handlers[cmd] = handler

    def dispatch(self, message: dict, sock: socket.socket) -> dict | None:
        """Roteia uma mensagem recebida para o handler correspondente."""
        cmd = message.get("cmd")
        data = message.get("data", {}) or {}
        handler = self._handlers.get(cmd)
        if handler is None:
            return protocol.make_response(
                f"{cmd}_RESPONSE" if cmd else "UNKNOWN_RESPONSE",
                protocol.STATUS_ERROR,
                message=f"comando desconhecido: {cmd!r}",
            )
        ctx = HandlerContext(sock=sock, sessions=self.sessions, db=self.db)
        return handler(data, ctx)

    # --- handlers embutidos (uteis antes dos handlers de dominio existirem) ---

    def _register_builtin(self) -> None:
        self.register("PING", self._handle_ping)
        self.register("ECHO", self._handle_echo)

    def _register_auth(self) -> None:
        from server.handlers.auth import handle_register, handle_login, handle_logout
        self.register(protocol.CMD_REGISTER, handle_register)
        self.register(protocol.CMD_LOGIN, handle_login)
        self.register(protocol.CMD_LOGOUT, handle_logout)

    def _register_key_exchange(self) -> None:
        from server.handlers.key_exchange import handle_update_pubkey, handle_get_pubkey
        self.register(protocol.CMD_UPDATE_PUBKEY, handle_update_pubkey)
        self.register(protocol.CMD_GET_PUBKEY, handle_get_pubkey)

    def _register_message(self) -> None:
        from server.handlers.message import handle_msg_1v1
        self.register(protocol.CMD_MSG_1V1, handle_msg_1v1)

    @staticmethod
    def _handle_ping(_data: dict, _ctx: HandlerContext) -> dict:
        return protocol.make_response("PONG", protocol.STATUS_OK, message="pong")

    @staticmethod
    def _handle_echo(data: dict, _ctx: HandlerContext) -> dict:
        return protocol.make_response("ECHO_RESPONSE", protocol.STATUS_OK, data=data)
