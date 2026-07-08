"""Distribuicao de chaves publicas e de forum.

O servidor apenas armazena/repassa a chave AES ja cifrada com a RSA publica
de cada membro. Nunca ve a chave em claro.

handle_update_pubkey -> grava a public key RSA do usuario autenticado (Dia 4)
handle_get_pubkey     -> devolve a public key PEM de outro usuario (Dia 4)
distribute_key        -> guarda encrypted_aes_key por (forum, membro, key_version)
"""

from __future__ import annotations

from shared import protocol
from server.router import HandlerContext

# TODO(Sprint 1, Dia 6): distribute_key + rotacao de versao.


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
