"""Handlers de foruns (Sprint 1, Dias 5 e 7; Sprint 2, Dia 8).

create_forum       -> gera codigo de convite CORVO-XXXX-XXXX, armazena SHA-256,
                       cria as roles padrao (Corvo-Mor/Escriba/Iniciado)
join_forum         -> compara hash do codigo, adiciona a forum_members,
                       atribui a role Iniciado ao novo membro
leave_forum        -> remove membro (dispara rotacao de chave)
list_my_forums     -> lista foruns do usuario
get_forum_members  -> lista membros de um forum com as roles de cada um (p/ GUI)
"""

from __future__ import annotations

import hashlib
import secrets
import string

from shared import permissions, protocol
from server.router import HandlerContext
from server.handlers.role import create_default_roles, assign_default_role_to_new_member

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


def _require_permission(
    ctx: HandlerContext, forum_id: int, user_id: int, flag: int, response_cmd: str
) -> dict | None:
    """Retorna None se o membro tem a permissao, ou uma response de erro."""
    mask = ctx.db.get_member_permission_mask(forum_id, user_id)
    if not permissions.has_permission(mask, flag):
        return protocol.make_response(
            response_cmd, protocol.STATUS_ERROR, message="permissao negada"
        )
    return None


def _require_owner(ctx: HandlerContext, forum_row, user_id: int, response_cmd: str) -> dict | None:
    """Retorna None se `user_id` e o dono do forum, ou uma response de erro."""
    if forum_row["owner_id"] != user_id:
        return protocol.make_response(
            response_cmd, protocol.STATUS_ERROR, message="apenas o dono do forum pode fazer isso"
        )
    return None


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

    icon = (data.get("icon") or "⚔").strip() or "⚔"

    invite_code = _generate_invite_code()
    invite_hash = _hash_invite_code(invite_code)
    forum_id = ctx.db.create_forum(name, invite_hash, session["user_id"], icon=icon)
    create_default_roles(ctx, forum_id, session["user_id"])

    return protocol.make_response(
        "CREATE_FORUM_RESPONSE",
        protocol.STATUS_OK,
        message="forum criado com sucesso",
        data={"forum_id": forum_id, "name": name, "icon": icon, "invite_code": invite_code, "owner_id": session["user_id"]},
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
    if ctx.db.is_banned(forum_row["id"], session["user_id"]):
        return protocol.make_response(
            "JOIN_FORUM_RESPONSE", protocol.STATUS_ERROR, message="voce foi banido deste forum"
        )

    ctx.db.add_member(forum_row["id"], session["user_id"])
    assign_default_role_to_new_member(ctx, forum_row["id"], session["user_id"])

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
        {"forum_id": row["id"], "name": row["name"], "icon": row["icon"], "owner_id": row["owner_id"]}
        for row in ctx.db.get_forums_for_user(session["user_id"])
    ]
    return protocol.make_response(
        "LIST_MY_FORUMS_RESPONSE", protocol.STATUS_OK, data={"forums": forums}
    )


def handle_get_forum_members(data: dict, ctx: HandlerContext) -> dict:
    """Lista os membros de um forum, cada um com as roles que possui.

    Espera data = {"forum_id": int}. Usado pela GUI para popular a sidebar de
    membros agrupada por role.
    """
    session, err = _require_auth(ctx, "GET_FORUM_MEMBERS_RESPONSE")
    if err is not None:
        return err

    forum_id = data.get("forum_id")
    if forum_id is None or not ctx.db.is_member(forum_id, session["user_id"]):
        return protocol.make_response(
            "GET_FORUM_MEMBERS_RESPONSE", protocol.STATUS_ERROR, message="voce nao e membro deste forum"
        )

    members = [
        {
            "user_id": row["id"],
            "username": row["username"],
            "roles": [
                {
                    "role_id": role["id"], "name": role["name"], "color": role["color"],
                    "priority": role["priority"], "permissions": role["permissions"],
                }
                for role in ctx.db.get_roles_for_member(forum_id, row["id"])
            ],
        }
        for row in ctx.db.get_forum_members(forum_id)
    ]
    return protocol.make_response(
        "GET_FORUM_MEMBERS_RESPONSE", protocol.STATUS_OK, data={"forum_id": forum_id, "members": members}
    )


def handle_regenerate_invite(data: dict, ctx: HandlerContext) -> dict:
    """Gera um novo codigo de convite para o forum, invalidando o anterior.

    Requer CREATE_INVITE no forum. Espera data = {"forum_id": int}. O novo
    codigo e devolvido a quem chamou E enviado via broadcast (EVT_INVITE_
    REGENERATED) para todo membro que tambem tenha CREATE_INVITE, para que
    ninguem precise regenerar de novo so para ver o convite atual.
    """
    session, err = _require_auth(ctx, "REGENERATE_INVITE_RESPONSE")
    if err is not None:
        return err

    forum_id = data.get("forum_id")
    forum_row = ctx.db.get_forum_by_id(forum_id) if forum_id is not None else None
    if forum_row is None or not ctx.db.is_member(forum_id, session["user_id"]):
        return protocol.make_response(
            "REGENERATE_INVITE_RESPONSE", protocol.STATUS_ERROR, message="forum nao encontrado"
        )

    perm_err = _require_permission(
        ctx, forum_id, session["user_id"], permissions.Permission.CREATE_INVITE, "REGENERATE_INVITE_RESPONSE"
    )
    if perm_err is not None:
        return perm_err

    invite_code = _generate_invite_code()
    ctx.db.update_invite_hash(forum_id, _hash_invite_code(invite_code))

    destinatarios = {
        row["id"] for row in ctx.db.get_forum_members(forum_id)
        if row["id"] != session["user_id"]
        and permissions.has_permission(
            ctx.db.get_member_permission_mask(forum_id, row["id"]), permissions.Permission.CREATE_INVITE
        )
    }
    if destinatarios:
        event = protocol.make_event(
            protocol.EVT_INVITE_REGENERATED,
            data={"forum_id": forum_id, "invite_code": invite_code, "regenerated_by": session["username"]},
        )
        ctx.sessions.broadcast_to_users(destinatarios, event)

    return protocol.make_response(
        "REGENERATE_INVITE_RESPONSE",
        protocol.STATUS_OK,
        message="convite regenerado com sucesso",
        data={"forum_id": forum_id, "invite_code": invite_code},
    )


def handle_update_forum(data: dict, ctx: HandlerContext) -> dict:
    """Edita nome e/ou icone do forum. So o dono pode. Espera data =
    {"forum_id": int, "name": str (opcional), "icon": str (opcional)}."""
    session, err = _require_auth(ctx, "UPDATE_FORUM_RESPONSE")
    if err is not None:
        return err

    forum_id = data.get("forum_id")
    forum_row = ctx.db.get_forum_by_id(forum_id) if forum_id is not None else None
    if forum_row is None:
        return protocol.make_response(
            "UPDATE_FORUM_RESPONSE", protocol.STATUS_ERROR, message="forum nao encontrado"
        )

    owner_err = _require_owner(ctx, forum_row, session["user_id"], "UPDATE_FORUM_RESPONSE")
    if owner_err is not None:
        return owner_err

    name = data.get("name")
    if name is not None:
        name = name.strip()
        if not name:
            return protocol.make_response(
                "UPDATE_FORUM_RESPONSE", protocol.STATUS_ERROR, message="nome do forum obrigatorio"
            )
        if len(name) > 64:
            return protocol.make_response(
                "UPDATE_FORUM_RESPONSE", protocol.STATUS_ERROR, message="nome muito longo (max 64)"
            )
    icon = data.get("icon")
    if icon is not None:
        icon = icon.strip() or None

    ctx.db.update_forum(forum_id, name=name, icon=icon)
    updated = ctx.db.get_forum_by_id(forum_id)

    member_ids = {row["id"] for row in ctx.db.get_forum_members(forum_id)}
    event = protocol.make_event(
        protocol.EVT_FORUM_UPDATED,
        data={"forum_id": forum_id, "name": updated["name"], "icon": updated["icon"]},
    )
    ctx.sessions.broadcast_to_users(member_ids, event, exclude=ctx.sock)

    return protocol.make_response(
        "UPDATE_FORUM_RESPONSE",
        protocol.STATUS_OK,
        message="forum atualizado com sucesso",
        data={"forum_id": forum_id, "name": updated["name"], "icon": updated["icon"]},
    )


def handle_delete_forum(data: dict, ctx: HandlerContext) -> dict:
    """Apaga o forum permanentemente. So o dono pode. Espera data = {"forum_id": int}."""
    session, err = _require_auth(ctx, "DELETE_FORUM_RESPONSE")
    if err is not None:
        return err

    forum_id = data.get("forum_id")
    forum_row = ctx.db.get_forum_by_id(forum_id) if forum_id is not None else None
    if forum_row is None:
        return protocol.make_response(
            "DELETE_FORUM_RESPONSE", protocol.STATUS_ERROR, message="forum nao encontrado"
        )

    owner_err = _require_owner(ctx, forum_row, session["user_id"], "DELETE_FORUM_RESPONSE")
    if owner_err is not None:
        return owner_err

    member_ids = {row["id"] for row in ctx.db.get_forum_members(forum_id)} - {session["user_id"]}
    ctx.db.delete_forum(forum_id)

    if member_ids:
        event = protocol.make_event(
            protocol.EVT_FORUM_DELETED,
            data={"forum_id": forum_id, "name": forum_row["name"]},
        )
        ctx.sessions.broadcast_to_users(member_ids, event)

    return protocol.make_response(
        "DELETE_FORUM_RESPONSE", protocol.STATUS_OK, message="forum apagado com sucesso"
    )


def handle_kick_member(data: dict, ctx: HandlerContext) -> dict:
    """Expulsa um membro do forum (ele pode reentrar com um convite valido).

    Requer KICK_MEMBER. Espera data = {"forum_id": int, "username": str}.
    """
    session, err = _require_auth(ctx, "KICK_MEMBER_RESPONSE")
    if err is not None:
        return err

    forum_id = data.get("forum_id")
    target_username = (data.get("username") or "").strip()
    forum_row = ctx.db.get_forum_by_id(forum_id) if forum_id is not None else None
    if forum_row is None or not target_username:
        return protocol.make_response(
            "KICK_MEMBER_RESPONSE", protocol.STATUS_ERROR, message="forum_id e username sao obrigatorios"
        )

    perm_err = _require_permission(
        ctx, forum_id, session["user_id"], permissions.Permission.KICK_MEMBER, "KICK_MEMBER_RESPONSE"
    )
    if perm_err is not None:
        return perm_err

    target_row = ctx.db.get_user_by_username(target_username)
    if target_row is None or not ctx.db.is_member(forum_id, target_row["id"]):
        return protocol.make_response(
            "KICK_MEMBER_RESPONSE", protocol.STATUS_ERROR, message="usuario nao e membro deste forum"
        )
    if target_row["id"] == forum_row["owner_id"]:
        return protocol.make_response(
            "KICK_MEMBER_RESPONSE", protocol.STATUS_ERROR, message="o dono do forum nao pode ser expulso"
        )

    ctx.db.remove_member(forum_id, target_row["id"])

    remaining_members = ctx.db.get_forum_members(forum_id)
    remaining_ids = {row["id"] for row in remaining_members}
    event_left = protocol.make_event(
        protocol.EVT_MEMBER_LEFT,
        data={
            "forum_id": forum_id,
            "username": target_username,
            "owner_id": forum_row["owner_id"],
            "remaining_members": [row["username"] for row in remaining_members],
        },
    )
    ctx.sessions.broadcast_to_users(remaining_ids, event_left, exclude=ctx.sock)

    event_kicked = protocol.make_event(
        protocol.EVT_MEMBER_KICKED,
        data={"forum_id": forum_id, "username": target_username, "by": session["username"]},
    )
    ctx.sessions.broadcast_to_users({target_row["id"]}, event_kicked)

    return protocol.make_response(
        "KICK_MEMBER_RESPONSE", protocol.STATUS_OK, message="membro expulso com sucesso"
    )


def handle_ban_member(data: dict, ctx: HandlerContext) -> dict:
    """Bane um membro do forum (impede reentrada mesmo com convite valido).

    Requer BAN_MEMBER. Espera data = {"forum_id": int, "username": str}.
    """
    session, err = _require_auth(ctx, "BAN_MEMBER_RESPONSE")
    if err is not None:
        return err

    forum_id = data.get("forum_id")
    target_username = (data.get("username") or "").strip()
    forum_row = ctx.db.get_forum_by_id(forum_id) if forum_id is not None else None
    if forum_row is None or not target_username:
        return protocol.make_response(
            "BAN_MEMBER_RESPONSE", protocol.STATUS_ERROR, message="forum_id e username sao obrigatorios"
        )

    perm_err = _require_permission(
        ctx, forum_id, session["user_id"], permissions.Permission.BAN_MEMBER, "BAN_MEMBER_RESPONSE"
    )
    if perm_err is not None:
        return perm_err

    target_row = ctx.db.get_user_by_username(target_username)
    if target_row is None or not ctx.db.is_member(forum_id, target_row["id"]):
        return protocol.make_response(
            "BAN_MEMBER_RESPONSE", protocol.STATUS_ERROR, message="usuario nao e membro deste forum"
        )
    if target_row["id"] == forum_row["owner_id"]:
        return protocol.make_response(
            "BAN_MEMBER_RESPONSE", protocol.STATUS_ERROR, message="o dono do forum nao pode ser banido"
        )

    ctx.db.ban_user(forum_id, target_row["id"])

    remaining_members = ctx.db.get_forum_members(forum_id)
    remaining_ids = {row["id"] for row in remaining_members}
    event_left = protocol.make_event(
        protocol.EVT_MEMBER_LEFT,
        data={
            "forum_id": forum_id,
            "username": target_username,
            "owner_id": forum_row["owner_id"],
            "remaining_members": [row["username"] for row in remaining_members],
        },
    )
    ctx.sessions.broadcast_to_users(remaining_ids, event_left, exclude=ctx.sock)

    event_banned = protocol.make_event(
        protocol.EVT_MEMBER_BANNED,
        data={"forum_id": forum_id, "username": target_username, "by": session["username"]},
    )
    ctx.sessions.broadcast_to_users({target_row["id"]}, event_banned)

    return protocol.make_response(
        "BAN_MEMBER_RESPONSE", protocol.STATUS_OK, message="membro banido com sucesso"
    )
