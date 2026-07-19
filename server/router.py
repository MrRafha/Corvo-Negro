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
        self._register_forum()
        self._register_role()

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
        from server.handlers.key_exchange import (
            handle_update_pubkey,
            handle_get_pubkey,
            handle_distribute_key,
            handle_request_forum_key,
        )
        self.register(protocol.CMD_UPDATE_PUBKEY, handle_update_pubkey)
        self.register(protocol.CMD_GET_PUBKEY, handle_get_pubkey)
        self.register(protocol.CMD_DISTRIBUTE_KEY, handle_distribute_key)
        self.register(protocol.CMD_REQUEST_FORUM_KEY, handle_request_forum_key)

    def _register_message(self) -> None:
        from server.handlers.message import (
            handle_msg_1v1,
            handle_send_to_forum,
            handle_get_history,
            handle_pin_message,
            handle_delete_message,
            handle_sync_messages,
        )
        self.register(protocol.CMD_MSG_1V1, handle_msg_1v1)
        self.register(protocol.CMD_SEND_TO_FORUM, handle_send_to_forum)
        self.register(protocol.CMD_GET_HISTORY, handle_get_history)
        self.register(protocol.CMD_PIN_MESSAGE, handle_pin_message)
        self.register(protocol.CMD_DELETE_MESSAGE, handle_delete_message)
        self.register(protocol.CMD_SYNC_MESSAGES, handle_sync_messages)

    def _register_forum(self) -> None:
        from server.handlers.forum import (
            handle_create_forum,
            handle_join_forum,
            handle_leave_forum,
            handle_list_my_forums,
            handle_get_forum_members,
            handle_regenerate_invite,
            handle_update_forum,
            handle_delete_forum,
            handle_kick_member,
            handle_ban_member,
        )
        self.register(protocol.CMD_CREATE_FORUM, handle_create_forum)
        self.register(protocol.CMD_JOIN_FORUM, handle_join_forum)
        self.register(protocol.CMD_LEAVE_FORUM, handle_leave_forum)
        self.register(protocol.CMD_LIST_MY_FORUMS, handle_list_my_forums)
        self.register(protocol.CMD_GET_FORUM_MEMBERS, handle_get_forum_members)
        self.register(protocol.CMD_REGENERATE_INVITE, handle_regenerate_invite)
        self.register(protocol.CMD_UPDATE_FORUM, handle_update_forum)
        self.register(protocol.CMD_DELETE_FORUM, handle_delete_forum)
        self.register(protocol.CMD_KICK_MEMBER, handle_kick_member)
        self.register(protocol.CMD_BAN_MEMBER, handle_ban_member)

    def _register_role(self) -> None:
        from server.handlers.role import (
            handle_list_roles,
            handle_create_role,
            handle_update_role,
            handle_delete_role,
            handle_assign_role,
        )
        self.register(protocol.CMD_LIST_ROLES, handle_list_roles)
        self.register(protocol.CMD_CREATE_ROLE, handle_create_role)
        self.register(protocol.CMD_UPDATE_ROLE, handle_update_role)
        self.register(protocol.CMD_DELETE_ROLE, handle_delete_role)
        self.register(protocol.CMD_ASSIGN_ROLE, handle_assign_role)

    @staticmethod
    def _handle_ping(_data: dict, _ctx: HandlerContext) -> dict:
        return protocol.make_response("PONG", protocol.STATUS_OK, message="pong")

    @staticmethod
    def _handle_echo(data: dict, _ctx: HandlerContext) -> dict:
        return protocol.make_response("ECHO_RESPONSE", protocol.STATUS_OK, data=data)
