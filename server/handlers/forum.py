"""Handlers de foruns (Sprint 1, Dia 5).

create_forum   -> gera codigo de convite CORVO-XXXX-XXXX, armazena SHA-256
join_forum     -> compara hash do codigo, adiciona a forum_members
leave_forum    -> remove membro (dispara rotacao de chave)
list_my_forums -> lista foruns do usuario
"""

from __future__ import annotations

import hashlib
import secrets
import string

from shared import protocol
from server.router import HandlerContext

_INVITE_ALPHABET = string.ascii_uppercase + string.digits
_INVITE_GROUP_SIZE = 4


def _generate_invite_code() -> str:
    """Gera um codigo no formato CORVO-XXXX-XXXX (letras maiusculas + digitos)."""
    grupo1 = "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(_INVITE_GROUP_SIZE))
    grupo2 = "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(_INVITE_GROUP_SIZE))
    return f"CORVO-{grupo1}-{grupo2}"


def _hash_invite_code(code: str) -> bytes:
    """SHA-256 do codigo de convite (o que fica armazenado, nunca o codigo em claro)."""
    return hashlib.sha256(code.encode("utf-8")).digest()


def _require_auth(ctx: HandlerContext, response_cmd: str) -> tuple[dict | None, dict | None]:
    """Retorna (session, None) se autenticado, ou (None, response_de_erro) caso contrario."""
    session = ctx.sessions.get(ctx.sock)
    if session is None or session.get("user_id") is None:
        return None, protocol.make_response(
            response_cmd, protocol.STATUS_ERROR, message="nao autenticado"
        )
    return session, None


def handle_create_forum(data: dict, ctx: HandlerContext) -> dict:
    """Cria um forum novo. Espera data = {"name": str}.

    Gera o codigo de convite, guarda apenas o hash SHA-256 no banco e devolve
    o codigo em claro uma unica vez, para o dono compartilhar com os membros.
    """
    session, err = _require_auth(ctx, "CREATE_FORUM_RESPONSE")
    if err is not None:
        return err

    name = (data.get("name") or "").strip()
    if not name:
        return protocol.make_response(
            "CREATE_FORUM_RESPONSE", protocol.STATUS_ERROR, message="nome do forum obrigatorio"
        )
    if len(name) > 64:
        return protocol.make_response(
            "CREATE_FORUM_RESPONSE", protocol.STATUS_ERROR, message="nome muito longo (max 64)"
        )

    invite_code = _generate_invite_code()
    invite_hash = _hash_invite_code(invite_code)
    forum_id = ctx.db.create_forum(name, invite_hash, session["user_id"])

    return protocol.make_response(
        "CREATE_FORUM_RESPONSE",
        protocol.STATUS_OK,
        message="forum criado com sucesso",
        data={"forum_id": forum_id, "name": name, "invite_code": invite_code, "owner_id": session["user_id"]},
    )


def handle_join_forum(data: dict, ctx: HandlerContext) -> dict:
    """Entra num forum via codigo de convite. Espera data = {"invite_code": str}."""
    session, err = _require_auth(ctx, "JOIN_FORUM_RESPONSE")
    if err is not None:
        return err

    invite_code = (data.get("invite_code") or "").strip().upper()
    if not invite_code:
        return protocol.make_response(
            "JOIN_FORUM_RESPONSE", protocol.STATUS_ERROR, message="codigo de convite obrigatorio"
        )

    forum_row = ctx.db.get_forum_by_invite_hash(_hash_invite_code(invite_code))
    if forum_row is None:
        return protocol.make_response(
            "JOIN_FORUM_RESPONSE", protocol.STATUS_ERROR, message="codigo de convite invalido"
        )

    if ctx.db.is_member(forum_row["id"], session["user_id"]):
        return protocol.make_response(
            "JOIN_FORUM_RESPONSE", protocol.STATUS_ERROR, message="voce ja e membro deste forum"
        )

    ctx.db.add_member(forum_row["id"], session["user_id"])

    member_ids = {row["id"] for row in ctx.db.get_forum_members(forum_row["id"])}
    event = protocol.make_event(
        protocol.EVT_MEMBER_JOINED,
        data={
            "forum_id": forum_row["id"],
            "username": session["username"],
            "owner_id": forum_row["owner_id"],
        },
    )
    ctx.sessions.broadcast_to_users(member_ids, event, exclude=ctx.sock)

    return protocol.make_response(
        "JOIN_FORUM_RESPONSE",
        protocol.STATUS_OK,
        message="entrou no forum com sucesso",
        data={"forum_id": forum_row["id"], "name": forum_row["name"], "owner_id": forum_row["owner_id"]},
    )


def handle_leave_forum(data: dict, ctx: HandlerContext) -> dict:
    """Sai de um forum. Espera data = {"forum_id": int}."""
    session, err = _require_auth(ctx, "LEAVE_FORUM_RESPONSE")
    if err is not None:
        return err

    forum_id = data.get("forum_id")
    forum_row = ctx.db.get_forum_by_id(forum_id) if forum_id is not None else None
    if forum_row is None:
        return protocol.make_response(
            "LEAVE_FORUM_RESPONSE", protocol.STATUS_ERROR, message="forum nao encontrado"
        )
    if not ctx.db.is_member(forum_id, session["user_id"]):
        return protocol.make_response(
            "LEAVE_FORUM_RESPONSE", protocol.STATUS_ERROR, message="voce nao e membro deste forum"
        )

    ctx.db.remove_member(forum_id, session["user_id"])

    # A rotacao de chave e responsabilidade do CLIENTE do dono: ao receber o
    # MEMBER_LEFT abaixo (que ja inclui quem restou no forum), ele gera uma
    # nova AES key, incrementa key_version e redistribui via CMD_DISTRIBUTE_KEY
    # para cada membro restante. O servidor nunca gera nem ve a chave em claro.
    remaining_members = ctx.db.get_forum_members(forum_id)
    remaining_ids = {row["id"] for row in remaining_members}
    event = protocol.make_event(
        protocol.EVT_MEMBER_LEFT,
        data={
            "forum_id": forum_id,
            "username": session["username"],
            "owner_id": forum_row["owner_id"],
            "remaining_members": [row["username"] for row in remaining_members],
        },
    )
    ctx.sessions.broadcast_to_users(remaining_ids, event)

    return protocol.make_response(
        "LEAVE_FORUM_RESPONSE", protocol.STATUS_OK, message="saiu do forum com sucesso"
    )


def handle_list_my_forums(data: dict, ctx: HandlerContext) -> dict:
    """Lista os foruns dos quais o usuario autenticado e membro."""
    session, err = _require_auth(ctx, "LIST_MY_FORUMS_RESPONSE")
    if err is not None:
        return err

    forums = [
        {"forum_id": row["id"], "name": row["name"], "owner_id": row["owner_id"]}
        for row in ctx.db.get_forums_for_user(session["user_id"])
    ]
    return protocol.make_response(
        "LIST_MY_FORUMS_RESPONSE", protocol.STATUS_OK, data={"forums": forums}
    )
