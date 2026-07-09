"""Handlers de mensagens.

handle_msg_1v1        -> persiste e roteia mensagem direta cifrada (Dia 4, nao decifra)
handle_send_to_forum  -> persiste ciphertext e rotea para membros online (Dia 6, nao decifra)
handle_get_history    -> retorna mensagens do forum com key_version correspondente (Dia 6)
handle_pin_message    -> fixa/desafixa mensagem, checa PIN_MESSAGE (Dia 7)
handle_delete_message -> apaga mensagem, checa DELETE_MESSAGE ou autoria (Dia 7)
"""

from __future__ import annotations

import base64
import uuid as uuid_lib

from shared import permissions, protocol
from server.router import HandlerContext


def handle_msg_1v1(data: dict, ctx: HandlerContext) -> dict:
    """Recebe uma mensagem 1:1 ja cifrada (hibrido RSA+AES) e roteia.

    O servidor apenas persiste e repassa — nunca decifra o conteudo.
    Espera data = {
        "recipient": str (username),
        "ciphertext": str (base64),
        "encrypted_key": str (base64),
        "iv": str (base64),
    }
    """
    session = ctx.sessions.get(ctx.sock)
    if session is None or session.get("user_id") is None:
        return protocol.make_response(
            "MSG_1V1_RESPONSE", protocol.STATUS_ERROR, message="nao autenticado"
        )

    recipient_username = (data.get("recipient") or "").strip()
    ciphertext_b64 = data.get("ciphertext")
    encrypted_key_b64 = data.get("encrypted_key")
    iv_b64 = data.get("iv")

    if not recipient_username or not ciphertext_b64 or not encrypted_key_b64 or not iv_b64:
        return protocol.make_response(
            "MSG_1V1_RESPONSE",
            protocol.STATUS_ERROR,
            message="recipient, ciphertext, encrypted_key e iv sao obrigatorios",
        )

    recipient_row = ctx.db.get_user_by_username(recipient_username)
    if recipient_row is None:
        return protocol.make_response(
            "MSG_1V1_RESPONSE", protocol.STATUS_ERROR, message="destinatario nao encontrado"
        )

    try:
        ciphertext = base64.b64decode(ciphertext_b64)
        encrypted_key = base64.b64decode(encrypted_key_b64)
        iv = base64.b64decode(iv_b64)
    except (ValueError, TypeError):
        return protocol.make_response(
            "MSG_1V1_RESPONSE", protocol.STATUS_ERROR, message="payload base64 invalido"
        )

    msg_uuid = str(uuid_lib.uuid4())
    ctx.db.save_direct_message(
        uuid=msg_uuid,
        sender_id=session["user_id"],
        recipient_id=recipient_row["id"],
        ciphertext=ciphertext,
        encrypted_key=encrypted_key,
        iv=iv,
    )

    event = protocol.make_event(
        protocol.EVT_NEW_DM,
        data={
            "uuid": msg_uuid,
            "sender": session["username"],
            "ciphertext": ciphertext_b64,
            "encrypted_key": encrypted_key_b64,
            "iv": iv_b64,
        },
    )
    ctx.sessions.send_to_user(recipient_row["id"], event)

    return protocol.make_response(
        "MSG_1V1_RESPONSE", protocol.STATUS_OK, message="mensagem enviada", data={"uuid": msg_uuid}
    )


def handle_send_to_forum(data: dict, ctx: HandlerContext) -> dict:
    """Recebe uma mensagem de forum ja cifrada com a AES da sala e roteia.

    O servidor apenas persiste e repassa aos membros online — nunca decifra.
    Espera data = {
        "forum_id": int,
        "ciphertext": str (base64),
        "iv": str (base64),
        "key_version": int,
    }
    """
    session = ctx.sessions.get(ctx.sock)
    if session is None or session.get("user_id") is None:
        return protocol.make_response(
            "SEND_TO_FORUM_RESPONSE", protocol.STATUS_ERROR, message="nao autenticado"
        )

    forum_id = data.get("forum_id")
    ciphertext_b64 = data.get("ciphertext")
    iv_b64 = data.get("iv")
    key_version = data.get("key_version")

    if forum_id is None or not ciphertext_b64 or not iv_b64 or not key_version:
        return protocol.make_response(
            "SEND_TO_FORUM_RESPONSE",
            protocol.STATUS_ERROR,
            message="forum_id, ciphertext, iv e key_version sao obrigatorios",
        )

    if not ctx.db.is_member(forum_id, session["user_id"]):
        return protocol.make_response(
            "SEND_TO_FORUM_RESPONSE", protocol.STATUS_ERROR, message="voce nao e membro deste forum"
        )

    try:
        ciphertext = base64.b64decode(ciphertext_b64)
        iv = base64.b64decode(iv_b64)
    except (ValueError, TypeError):
        return protocol.make_response(
            "SEND_TO_FORUM_RESPONSE", protocol.STATUS_ERROR, message="payload base64 invalido"
        )

    msg_uuid = str(uuid_lib.uuid4())
    ctx.db.save_message(
        uuid=msg_uuid,
        forum_id=forum_id,
        sender_id=session["user_id"],
        ciphertext=ciphertext,
        iv=iv,
        key_version=key_version,
    )

    member_ids = {row["id"] for row in ctx.db.get_forum_members(forum_id)}
    event = protocol.make_event(
        protocol.EVT_NEW_MESSAGE,
        data={
            "uuid": msg_uuid,
            "forum_id": forum_id,
            "sender": session["username"],
            "ciphertext": ciphertext_b64,
            "iv": iv_b64,
            "key_version": key_version,
        },
    )
    ctx.sessions.broadcast_to_users(member_ids, event, exclude=ctx.sock)

    return protocol.make_response(
        "SEND_TO_FORUM_RESPONSE", protocol.STATUS_OK, message="mensagem enviada", data={"uuid": msg_uuid}
    )


def handle_get_history(data: dict, ctx: HandlerContext) -> dict:
    """Retorna o historico de mensagens de um forum, ja cifradas.

    O cliente decifra localmente cada mensagem com a AES key da key_version
    correspondente. Espera data = {"forum_id": int}.
    """
    session = ctx.sessions.get(ctx.sock)
    if session is None or session.get("user_id") is None:
        return protocol.make_response(
            "GET_HISTORY_RESPONSE", protocol.STATUS_ERROR, message="nao autenticado"
        )

    forum_id = data.get("forum_id")
    if forum_id is None or not ctx.db.is_member(forum_id, session["user_id"]):
        return protocol.make_response(
            "GET_HISTORY_RESPONSE", protocol.STATUS_ERROR, message="voce nao e membro deste forum"
        )

    messages = [
        {
            "uuid": row["uuid"],
            "sender": row["sender_username"],
            "ciphertext": base64.b64encode(bytes(row["ciphertext"])).decode("ascii"),
            "iv": base64.b64encode(bytes(row["iv"])).decode("ascii"),
            "key_version": row["key_version"],
            "pinned": bool(row["pinned"]),
            "timestamp": row["timestamp"],
        }
        for row in ctx.db.get_messages_for_forum(forum_id)
    ]
    return protocol.make_response(
        "GET_HISTORY_RESPONSE", protocol.STATUS_OK, data={"forum_id": forum_id, "messages": messages}
    )


def handle_pin_message(data: dict, ctx: HandlerContext) -> dict:
    """Fixa ou desafixa uma mensagem de forum. Requer PIN_MESSAGE.

    Espera data = {"uuid": str, "pinned": bool}.
    """
    session = ctx.sessions.get(ctx.sock)
    if session is None or session.get("user_id") is None:
        return protocol.make_response(
            "PIN_MESSAGE_RESPONSE", protocol.STATUS_ERROR, message="nao autenticado"
        )

    msg_uuid = data.get("uuid")
    pinned = bool(data.get("pinned", True))
    message_row = ctx.db.get_message_by_uuid(msg_uuid) if msg_uuid else None
    if message_row is None:
        return protocol.make_response(
            "PIN_MESSAGE_RESPONSE", protocol.STATUS_ERROR, message="mensagem nao encontrada"
        )

    forum_id = message_row["forum_id"]
    mask = ctx.db.get_member_permission_mask(forum_id, session["user_id"])
    if not permissions.has_permission(mask, permissions.Permission.PIN_MESSAGE):
        return protocol.make_response(
            "PIN_MESSAGE_RESPONSE", protocol.STATUS_ERROR, message="permissao negada"
        )

    ctx.db.set_message_pinned(msg_uuid, pinned)

    member_ids = {row["id"] for row in ctx.db.get_forum_members(forum_id)}
    event = protocol.make_event(
        protocol.EVT_MESSAGE_PINNED,
        data={"forum_id": forum_id, "uuid": msg_uuid, "pinned": pinned},
    )
    ctx.sessions.broadcast_to_users(member_ids, event, exclude=ctx.sock)

    return protocol.make_response("PIN_MESSAGE_RESPONSE", protocol.STATUS_OK, message="atualizado")


def handle_delete_message(data: dict, ctx: HandlerContext) -> dict:
    """Apaga uma mensagem de forum. Permitido para o autor ou quem tem DELETE_MESSAGE.

    Espera data = {"uuid": str}.
    """
    session = ctx.sessions.get(ctx.sock)
    if session is None or session.get("user_id") is None:
        return protocol.make_response(
            "DELETE_MESSAGE_RESPONSE", protocol.STATUS_ERROR, message="nao autenticado"
        )

    msg_uuid = data.get("uuid")
    message_row = ctx.db.get_message_by_uuid(msg_uuid) if msg_uuid else None
    if message_row is None:
        return protocol.make_response(
            "DELETE_MESSAGE_RESPONSE", protocol.STATUS_ERROR, message="mensagem nao encontrada"
        )

    forum_id = message_row["forum_id"]
    is_author = message_row["sender_id"] == session["user_id"]
    mask = ctx.db.get_member_permission_mask(forum_id, session["user_id"])
    if not is_author and not permissions.has_permission(mask, permissions.Permission.DELETE_MESSAGE):
        return protocol.make_response(
            "DELETE_MESSAGE_RESPONSE", protocol.STATUS_ERROR, message="permissao negada"
        )

    ctx.db.delete_message(msg_uuid)

    member_ids = {row["id"] for row in ctx.db.get_forum_members(forum_id)}
    event = protocol.make_event(
        protocol.EVT_MESSAGE_DELETED, data={"forum_id": forum_id, "uuid": msg_uuid}
    )
    ctx.sessions.broadcast_to_users(member_ids, event, exclude=ctx.sock)

    return protocol.make_response("DELETE_MESSAGE_RESPONSE", protocol.STATUS_OK, message="mensagem apagada")
