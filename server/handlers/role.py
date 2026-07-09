"""Handlers de roles (Sprint 1, Dia 7).

create_default_roles -> cria Corvo-Mor/Escriba/Iniciado ao criar um forum
create_role / edit_role / delete_role / assign_role / revoke_role.
Toda acao sensivel checa permissao no SERVIDOR antes de executar.

Roles padrao ao criar forum:
    Corvo-Mor (ALL)   -> atribuida automaticamente ao dono
    Escriba (SEND+DELETE+PIN+KICK)
    Iniciado (SEND)   -> atribuida automaticamente a quem entra depois
"""

from __future__ import annotations

from shared import permissions, protocol
from server.router import HandlerContext

_DEFAULT_ROLES = [
    ("Corvo-Mor", "#c9a961", permissions.Permission.ALL, 100),
    (
        "Escriba",
        "#8b0000",
        permissions.Permission.SEND_MESSAGE
        | permissions.Permission.DELETE_MESSAGE
        | permissions.Permission.PIN_MESSAGE
        | permissions.Permission.KICK_MEMBER
        | permissions.Permission.CREATE_INVITE,
        50,
    ),
    ("Iniciado", "#5a5a5a", permissions.Permission.SEND_MESSAGE, 0),
]


def create_default_roles(ctx: HandlerContext, forum_id: int, owner_id: int) -> None:
    """Cria as 3 roles padrao do forum e atribui Corvo-Mor ao dono, Iniciado
    a quem entra depois (chamado por handle_create_forum/handle_join_forum).
    """
    for name, color, mask, priority in _DEFAULT_ROLES:
        role_id = ctx.db.create_role(forum_id, name, color, mask, priority)
        if name == "Corvo-Mor":
            ctx.db.assign_role(forum_id, owner_id, role_id)


def assign_default_role_to_new_member(ctx: HandlerContext, forum_id: int, user_id: int) -> None:
    """Atribui a role Iniciado a quem acabou de entrar no forum."""
    role_row = ctx.db.get_role_by_name(forum_id, "Iniciado")
    if role_row is not None:
        ctx.db.assign_role(forum_id, user_id, role_row["id"])


def _require_auth(ctx: HandlerContext, response_cmd: str) -> tuple[dict | None, dict | None]:
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


def handle_list_roles(data: dict, ctx: HandlerContext) -> dict:
    """Lista TODAS as roles do forum (mesmo as sem nenhum membro atribuido).

    Espera data = {"forum_id": int}. Diferente de derivar roles a partir de
    CMD_GET_FORUM_MEMBERS (que so mostra roles com pelo menos 1 portador).
    """
    session, err = _require_auth(ctx, "LIST_ROLES_RESPONSE")
    if err is not None:
        return err

    forum_id = data.get("forum_id")
    if forum_id is None or not ctx.db.is_member(forum_id, session["user_id"]):
        return protocol.make_response(
            "LIST_ROLES_RESPONSE", protocol.STATUS_ERROR, message="voce nao e membro deste forum"
        )

    roles = [
        {
            "role_id": role["id"], "name": role["name"], "color": role["color"],
            "priority": role["priority"], "permissions": role["permissions"],
            "members": [m["username"] for m in ctx.db.get_members_for_role(role["id"])],
        }
        for role in ctx.db.get_roles_for_forum(forum_id)
    ]
    return protocol.make_response(
        "LIST_ROLES_RESPONSE", protocol.STATUS_OK, data={"forum_id": forum_id, "roles": roles}
    )


def handle_create_role(data: dict, ctx: HandlerContext) -> dict:
    """Cria uma role customizada. Requer MANAGE_ROLES no forum.

    Espera data = {"forum_id": int, "name": str, "color": str (opcional),
    "permissions": int, "priority": int (opcional)}.
    """
    session, err = _require_auth(ctx, "CREATE_ROLE_RESPONSE")
    if err is not None:
        return err

    forum_id = data.get("forum_id")
    name = (data.get("name") or "").strip()
    perm_mask = data.get("permissions")

    if forum_id is None or not name or perm_mask is None:
        return protocol.make_response(
            "CREATE_ROLE_RESPONSE",
            protocol.STATUS_ERROR,
            message="forum_id, name e permissions sao obrigatorios",
        )
    if not ctx.db.is_member(forum_id, session["user_id"]):
        return protocol.make_response(
            "CREATE_ROLE_RESPONSE", protocol.STATUS_ERROR, message="voce nao e membro deste forum"
        )

    perm_err = _require_permission(
        ctx, forum_id, session["user_id"], permissions.Permission.MANAGE_ROLES, "CREATE_ROLE_RESPONSE"
    )
    if perm_err is not None:
        return perm_err

    color = data.get("color") or "#8b0000"
    priority = data.get("priority", 0)
    role_id = ctx.db.create_role(forum_id, name, color, perm_mask, priority)

    return protocol.make_response(
        "CREATE_ROLE_RESPONSE",
        protocol.STATUS_OK,
        message="role criada com sucesso",
        data={"role_id": role_id, "forum_id": forum_id, "name": name},
    )


def handle_update_role(data: dict, ctx: HandlerContext) -> dict:
    """Edita nome/cor/permissoes/prioridade de uma role. Requer MANAGE_ROLES.

    Espera data = {"role_id": int, "name": str (opcional), "color": str
    (opcional), "permissions": int (opcional), "priority": int (opcional)}.
    """
    session, err = _require_auth(ctx, "UPDATE_ROLE_RESPONSE")
    if err is not None:
        return err

    role_id = data.get("role_id")
    role_row = ctx.db.get_role_by_id(role_id) if role_id is not None else None
    if role_row is None:
        return protocol.make_response(
            "UPDATE_ROLE_RESPONSE", protocol.STATUS_ERROR, message="role nao encontrada"
        )
    forum_id = role_row["forum_id"]

    perm_err = _require_permission(
        ctx, forum_id, session["user_id"], permissions.Permission.MANAGE_ROLES, "UPDATE_ROLE_RESPONSE"
    )
    if perm_err is not None:
        return perm_err

    name = data.get("name")
    if name is not None:
        name = name.strip()
        if not name:
            return protocol.make_response(
                "UPDATE_ROLE_RESPONSE", protocol.STATUS_ERROR, message="nome da ordem obrigatorio"
            )

    ctx.db.update_role(
        role_id, name=name, color=data.get("color"),
        permissions=data.get("permissions"), priority=data.get("priority"),
    )
    updated = ctx.db.get_role_by_id(role_id)

    member_ids = {row["id"] for row in ctx.db.get_forum_members(forum_id)}
    event = protocol.make_event(
        protocol.EVT_ROLE_UPDATED,
        data={
            "forum_id": forum_id, "role_id": role_id, "name": updated["name"],
            "color": updated["color"], "permissions": updated["permissions"], "priority": updated["priority"],
        },
    )
    # sem exclude=ctx.sock: quem editou tambem quer ver o proprio sidebar de
    # membros refletir a mudanca de nome/cor imediatamente.
    ctx.sessions.broadcast_to_users(member_ids, event)

    return protocol.make_response(
        "UPDATE_ROLE_RESPONSE",
        protocol.STATUS_OK,
        message="ordem atualizada com sucesso",
        data={
            "role_id": role_id, "forum_id": forum_id, "name": updated["name"],
            "color": updated["color"], "permissions": updated["permissions"], "priority": updated["priority"],
        },
    )


def handle_delete_role(data: dict, ctx: HandlerContext) -> dict:
    """Dissolve uma role (remove de todos os membros que a possuem). Requer
    MANAGE_ROLES. Espera data = {"role_id": int}."""
    session, err = _require_auth(ctx, "DELETE_ROLE_RESPONSE")
    if err is not None:
        return err

    role_id = data.get("role_id")
    role_row = ctx.db.get_role_by_id(role_id) if role_id is not None else None
    if role_row is None:
        return protocol.make_response(
            "DELETE_ROLE_RESPONSE", protocol.STATUS_ERROR, message="role nao encontrada"
        )
    forum_id = role_row["forum_id"]

    perm_err = _require_permission(
        ctx, forum_id, session["user_id"], permissions.Permission.MANAGE_ROLES, "DELETE_ROLE_RESPONSE"
    )
    if perm_err is not None:
        return perm_err
    if role_row["name"] == "Corvo-Mor":
        return protocol.make_response(
            "DELETE_ROLE_RESPONSE", protocol.STATUS_ERROR, message="a ordem Corvo-Mor nao pode ser dissolvida"
        )

    member_ids = {row["id"] for row in ctx.db.get_forum_members(forum_id)}
    ctx.db.delete_role(role_id)

    event = protocol.make_event(
        protocol.EVT_ROLE_DELETED, data={"forum_id": forum_id, "role_id": role_id, "name": role_row["name"]},
    )
    # sem exclude=ctx.sock: quem editou tambem quer ver o proprio sidebar de
    # membros refletir a mudanca de nome/cor imediatamente.
    ctx.sessions.broadcast_to_users(member_ids, event)

    return protocol.make_response(
        "DELETE_ROLE_RESPONSE", protocol.STATUS_OK, message="ordem dissolvida com sucesso"
    )


def handle_assign_role(data: dict, ctx: HandlerContext) -> dict:
    """Atribui uma role a um membro. Requer MANAGE_ROLES no forum.

    Espera data = {"forum_id": int, "username": str, "role_id": int}.
    """
    session, err = _require_auth(ctx, "ASSIGN_ROLE_RESPONSE")
    if err is not None:
        return err

    forum_id = data.get("forum_id")
    target_username = (data.get("username") or "").strip()
    role_id = data.get("role_id")

    if forum_id is None or not target_username or role_id is None:
        return protocol.make_response(
            "ASSIGN_ROLE_RESPONSE",
            protocol.STATUS_ERROR,
            message="forum_id, username e role_id sao obrigatorios",
        )

    perm_err = _require_permission(
        ctx, forum_id, session["user_id"], permissions.Permission.MANAGE_ROLES, "ASSIGN_ROLE_RESPONSE"
    )
    if perm_err is not None:
        return perm_err

    target_row = ctx.db.get_user_by_username(target_username)
    if target_row is None or not ctx.db.is_member(forum_id, target_row["id"]):
        return protocol.make_response(
            "ASSIGN_ROLE_RESPONSE", protocol.STATUS_ERROR, message="usuario nao e membro deste forum"
        )

    role_row = ctx.db.get_role_by_id(role_id)
    if role_row is None or role_row["forum_id"] != forum_id:
        return protocol.make_response(
            "ASSIGN_ROLE_RESPONSE", protocol.STATUS_ERROR, message="role nao encontrada neste forum"
        )

    ctx.db.assign_role(forum_id, target_row["id"], role_id)

    return protocol.make_response(
        "ASSIGN_ROLE_RESPONSE",
        protocol.STATUS_OK,
        message="role atribuida com sucesso",
        data={"forum_id": forum_id, "username": target_username, "role_id": role_id},
    )
