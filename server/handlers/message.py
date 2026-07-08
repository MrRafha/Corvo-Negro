"""Handlers de mensagens.

handle_msg_1v1 -> persiste e roteia mensagem direta cifrada (Dia 4, nao decifra)
send    -> persiste ciphertext e rotea para membros online (nao decifra) (Dia 6)
history -> retorna mensagens do forum com key_version correspondente (Dia 6)
pin     -> fixar mensagem (checa permissao) (Dia 6)
delete  -> apagar mensagem (checa permissao) (Dia 6)
"""

from __future__ import annotations

import base64
import uuid as uuid_lib

from shared import protocol
from server.router import HandlerContext

# TODO(Sprint 1, Dia 6): send / history + pin / delete (checagem de permissao).


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
