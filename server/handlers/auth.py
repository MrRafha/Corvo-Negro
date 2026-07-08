"""Handlers de autenticacao (Sprint 1, Dia 3).

handle_register  -> valida, cria user, retorna sucesso/erro
handle_login     -> verifica hash PBKDF2, cria sessao, retorna session_token
handle_logout    -> limpa sessao
"""

from __future__ import annotations

import secrets

from shared import crypto_utils, protocol
from server.router import HandlerContext


def handle_register(data: dict, ctx: HandlerContext) -> dict:
    """Registra um novo usuario.

    Espera data = {"username": str, "password": str}.
    A senha nunca e armazenada em claro — apenas o hash PBKDF2.
    """
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username:
        return protocol.make_response(
            "REGISTER_RESPONSE", protocol.STATUS_ERROR, message="username obrigatorio"
        )
    if len(username) > 32:
        return protocol.make_response(
            "REGISTER_RESPONSE", protocol.STATUS_ERROR, message="username muito longo (max 32)"
        )
    if not password:
        return protocol.make_response(
            "REGISTER_RESPONSE", protocol.STATUS_ERROR, message="senha obrigatoria"
        )

    password_hash = crypto_utils.hash_password(password)
    try:
        user_id = ctx.db.create_user(username, password_hash)
    except ValueError:
        return protocol.make_response(
            "REGISTER_RESPONSE", protocol.STATUS_ERROR, message="username ja esta em uso"
        )

    return protocol.make_response(
        "REGISTER_RESPONSE",
        protocol.STATUS_OK,
        message="usuario criado com sucesso",
        data={"user_id": user_id, "username": username},
    )


def handle_login(data: dict, ctx: HandlerContext) -> dict:
    """Autentica um usuario e abre uma sessao.

    Espera data = {"username": str, "password": str}.
    Retorna um session_token opaco (32 bytes hex) que o cliente usa nos
    requests seguintes.
    """
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    row = ctx.db.get_user_by_username(username)
    if row is None:
        return protocol.make_response(
            "LOGIN_RESPONSE", protocol.STATUS_ERROR, message="credenciais invalidas"
        )

    if not crypto_utils.verify_password(password, bytes(row["password_hash"])):
        return protocol.make_response(
            "LOGIN_RESPONSE", protocol.STATUS_ERROR, message="credenciais invalidas"
        )

    token = secrets.token_hex(32)
    ctx.sessions.authenticate(ctx.sock, row["id"], row["username"], token)

    return protocol.make_response(
        "LOGIN_RESPONSE",
        protocol.STATUS_OK,
        message="login realizado",
        data={
            "user_id": row["id"],
            "username": row["username"],
            "session_token": token,
        },
    )


def handle_logout(data: dict, ctx: HandlerContext) -> dict:
    """Encerra a sessao autenticada do cliente."""
    ctx.sessions.remove(ctx.sock)
    ctx.sessions.add(ctx.sock)  # re-adiciona sem autenticacao
    return protocol.make_response("LOGOUT_RESPONSE", protocol.STATUS_OK, message="sessao encerrada")
