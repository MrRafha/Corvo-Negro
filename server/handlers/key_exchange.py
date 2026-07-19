"""Distribuicao de chaves publicas e de forum.

O servidor apenas armazena/repassa a chave AES ja cifrada com a RSA publica
de cada membro. Nunca ve a chave em claro.

handle_update_pubkey    -> grava a public key RSA do usuario autenticado (Dia 4)
handle_get_pubkey       -> devolve a public key PEM de outro usuario (Dia 4)
handle_distribute_key   -> guarda encrypted_aes_key por (forum, membro, key_version) (Dia 6)

Quem controla a distribuicao e sempre o dono do forum: ele gera a AES key da
sala, cifra com a RSA publica de cada membro (uma chamada de DISTRIBUTE_KEY
por destinatario) e o servidor apenas persiste e notifica quem esta online.
"""

from __future__ import annotations

import base64

from shared import protocol
from server.router import HandlerContext


def handle_update_pubkey(data: dict, ctx: HandlerContext) -> dict:
    """Grava/atualiza a public key RSA do usuario autenticado.

    Espera data = {"public_key": str}, PEM da chave publica gerada no cliente.
    """
    session = ctx.sessions.get(ctx.sock)
    if session is None or session.get("user_id") is None:
        return protocol.make_response(
            "UPDATE_PUBKEY_RESPONSE", protocol.STATUS_ERROR, message="nao autenticado"
        )

    public_key = data.get("public_key") or ""
    if not public_key:
        return protocol.make_response(
            "UPDATE_PUBKEY_RESPONSE", protocol.STATUS_ERROR, message="public_key obrigatoria"
        )

    ctx.db.update_public_key(session["user_id"], public_key.encode("utf-8"))
    return protocol.make_response(
        "UPDATE_PUBKEY_RESPONSE", protocol.STATUS_OK, message="chave publica atualizada"
    )


def handle_get_pubkey(data: dict, ctx: HandlerContext) -> dict:
    """Devolve a public key PEM de outro usuario, pelo username.

    Espera data = {"username": str}.
    """
    session = ctx.sessions.get(ctx.sock)
    if session is None or session.get("user_id") is None:
        return protocol.make_response(
            "GET_PUBKEY_RESPONSE", protocol.STATUS_ERROR, message="nao autenticado"
        )

    username = (data.get("username") or "").strip()
    row = ctx.db.get_user_by_username(username)
    if row is None:
        return protocol.make_response(
            "GET_PUBKEY_RESPONSE", protocol.STATUS_ERROR, message="usuario nao encontrado"
        )

    public_key = bytes(row["public_key"])
    if not public_key:
        return protocol.make_response(
            "GET_PUBKEY_RESPONSE", protocol.STATUS_ERROR, message="usuario sem chave publica registrada"
        )

    return protocol.make_response(
        "GET_PUBKEY_RESPONSE",
        protocol.STATUS_OK,
        data={"username": username, "public_key": public_key.decode("utf-8")},
    )


def handle_distribute_key(data: dict, ctx: HandlerContext) -> dict:
    """Distribui a AES key de um forum (ja cifrada) para um membro especifico.

    Espera data = {
        "forum_id": int,
        "recipient": str (username),
        "encrypted_aes_key": str (base64),
        "key_version": int,
    }

    Apenas o dono do forum pode distribuir chaves. O servidor nunca decifra
    a AES key: apenas guarda em forum_keys e notifica o destinatario, se
    estiver online, para que ele guarde a chave em memoria.
    """
    session = ctx.sessions.get(ctx.sock)
    if session is None or session.get("user_id") is None:
        return protocol.make_response(
            "DISTRIBUTE_KEY_RESPONSE", protocol.STATUS_ERROR, message="nao autenticado"
        )

    forum_id = data.get("forum_id")
    recipient_username = (data.get("recipient") or "").strip()
    encrypted_key_b64 = data.get("encrypted_aes_key")
    key_version = data.get("key_version")

    if forum_id is None or not recipient_username or not encrypted_key_b64 or not key_version:
        return protocol.make_response(
            "DISTRIBUTE_KEY_RESPONSE",
            protocol.STATUS_ERROR,
            message="forum_id, recipient, encrypted_aes_key e key_version sao obrigatorios",
        )

    forum_row = ctx.db.get_forum_by_id(forum_id)
    if forum_row is None:
        return protocol.make_response(
            "DISTRIBUTE_KEY_RESPONSE", protocol.STATUS_ERROR, message="forum nao encontrado"
        )
    if forum_row["owner_id"] != session["user_id"]:
        return protocol.make_response(
            "DISTRIBUTE_KEY_RESPONSE",
            protocol.STATUS_ERROR,
            message="apenas o dono do forum pode distribuir chaves",
        )

    recipient_row = ctx.db.get_user_by_username(recipient_username)
    if recipient_row is None or not ctx.db.is_member(forum_id, recipient_row["id"]):
        return protocol.make_response(
            "DISTRIBUTE_KEY_RESPONSE",
            protocol.STATUS_ERROR,
            message="destinatario nao e membro deste forum",
        )

    try:
        encrypted_key = base64.b64decode(encrypted_key_b64)
    except (ValueError, TypeError):
        return protocol.make_response(
            "DISTRIBUTE_KEY_RESPONSE", protocol.STATUS_ERROR, message="encrypted_aes_key base64 invalido"
        )

    ctx.db.save_forum_key(forum_id, recipient_row["id"], encrypted_key, key_version)

    event = protocol.make_event(
        protocol.EVT_KEY_ROTATED,
        data={
            "forum_id": forum_id,
            "encrypted_aes_key": encrypted_key_b64,
            "key_version": key_version,
        },
    )
    ctx.sessions.send_to_user(recipient_row["id"], event)

    return protocol.make_response(
        "DISTRIBUTE_KEY_RESPONSE", protocol.STATUS_OK, message="chave distribuida"
    )


def handle_request_forum_key(data: dict, ctx: HandlerContext) -> dict:
    """Um membro pede a AES key mais recente do forum, sem depender de o
    dono estar online no exato momento em que entrou (Dia 8, polimento).

    Espera data = {"forum_id": int}.

    Se o servidor ja tem uma copia da chave da versao atual cifrada para
    este usuario (porque o dono a distribuiu em algum momento em que o
    usuario nao estava online), devolve na propria resposta. Caso
    contrario, apenas avisa o dono (se online) via EVT_KEY_REQUESTED para
    que ele distribua; o pedido nao bloqueia esperando o dono responder —
    o cliente recebera a chave depois via EVT_KEY_ROTATED, como sempre.
    O servidor nunca decifra a chave em nenhum dos dois caminhos.
    """
    session = ctx.sessions.get(ctx.sock)
    if session is None or session.get("user_id") is None:
        return protocol.make_response(
            "REQUEST_FORUM_KEY_RESPONSE", protocol.STATUS_ERROR, message="nao autenticado"
        )

    forum_id = data.get("forum_id")
    if forum_id is None:
        return protocol.make_response(
            "REQUEST_FORUM_KEY_RESPONSE", protocol.STATUS_ERROR, message="forum_id obrigatorio"
        )

    if not ctx.db.is_member(forum_id, session["user_id"]):
        return protocol.make_response(
            "REQUEST_FORUM_KEY_RESPONSE", protocol.STATUS_ERROR, message="voce nao e membro deste forum"
        )

    forum_row = ctx.db.get_forum_by_id(forum_id)
    if forum_row is None:
        return protocol.make_response(
            "REQUEST_FORUM_KEY_RESPONSE", protocol.STATUS_ERROR, message="forum nao encontrado"
        )

    current_version = ctx.db.get_current_key_version(forum_id)
    if current_version > 0:
        key_row = ctx.db.get_forum_key(forum_id, session["user_id"], current_version)
        if key_row is not None:
            return protocol.make_response(
                "REQUEST_FORUM_KEY_RESPONSE",
                protocol.STATUS_OK,
                data={
                    "forum_id": forum_id,
                    "encrypted_aes_key": base64.b64encode(bytes(key_row["encrypted_aes_key"])).decode("ascii"),
                    "key_version": current_version,
                },
            )

    event = protocol.make_event(
        protocol.EVT_KEY_REQUESTED,
        data={
            "forum_id": forum_id,
            "username": session["username"],
        },
    )
    ctx.sessions.send_to_user(forum_row["owner_id"], event)

    return protocol.make_response(
        "REQUEST_FORUM_KEY_RESPONSE",
        protocol.STATUS_ERROR,
        message="chave ainda nao distribuida; dono foi notificado se estiver online",
    )
