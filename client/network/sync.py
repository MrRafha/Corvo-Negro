"""Sync de historico ao reconectar online (Sprint 3, Dia 12).

Fluxo:
    1. Envia ao servidor last_seen_msg_id por forum (o que este cliente ja tem)
       + pending (mensagens geradas offline via mesh P2P, ainda nao vistas
       pelo servidor).
    2. Servidor devolve tudo desde esses IDs (new_messages) e confirma quais
       uuids de pending foram aceitos (accepted_uuids) — o INSERT OR IGNORE
       do servidor por uuid resolve duplicatas se a mesma sync rodar 2x.
    3. Cliente decifra e grava new_messages no local_db; marca accepted_uuids
       como synced=True.
    4. Ordenacao final de exibicao e por origin_timestamp (last-write-wins
       so pra desempate de ordem — nao ha edicao de mensagens neste app,
       entao nao existe conflito real de conteudo a resolver).
"""

from __future__ import annotations

import base64
from typing import Callable

from shared import protocol
from client.network.gui_bridge import ClientBridge
from client.storage.local_db import LocalDB
from client.ui.app_state import AppState


def montar_payload_sync(local_db: LocalDB, state: AppState) -> dict:
    """Monta {last_seen, pending} a partir do local_db e dos foruns conhecidos."""
    foruns_conhecidos = local_db.get_known_forums()
    last_seen = {
        str(f["forum_id"]): local_db.get_last_seen_msg_id(f["forum_id"])
        for f in foruns_conhecidos
    }
    pending = [
        {
            "forum_id": msg["forum_id"],
            "uuid": msg["uuid"],
            "ciphertext": base64.b64encode(msg["ciphertext"]).decode("ascii"),
            "iv": base64.b64encode(msg["iv"]).decode("ascii"),
            "key_version": msg["key_version"],
            "origin_timestamp": msg["origin_timestamp"],
        }
        for msg in local_db.get_unsynced_messages()
    ]
    return {"last_seen": last_seen, "pending": pending}


def aplicar_resultado_sync(
    local_db: LocalDB, state: AppState, resultado: dict, on_concluido: Callable[[int], None],
) -> None:
    """Decifra e grava no local_db as `new_messages` recebidas; marca
    `accepted_uuids` como synced. Chama on_concluido(n_mensagens_novas)."""
    from shared import crypto_utils

    n_novas = 0
    new_messages = resultado.get("new_messages", {}) or {}
    for forum_id_str, mensagens in new_messages.items():
        forum_id = int(forum_id_str)
        for msg in mensagens:
            key_version = msg["key_version"]
            aes_key = state.forum_keys.get((forum_id, key_version))
            if aes_key is None:
                continue  # sem a chave desta versao ainda — fica de fora deste ciclo
            try:
                ciphertext = base64.b64decode(msg["ciphertext"])
                iv = base64.b64decode(msg["iv"])
                crypto_utils.aes_decrypt(ciphertext, aes_key, iv)  # so pra validar que decifra
            except Exception:
                continue
            local_db.save_message(
                msg["uuid"], forum_id, msg["sender"], ciphertext, iv, key_version,
                msg.get("timestamp", ""), synced=True,
            )
            n_novas += 1
        maior_id = max((m.get("id", 0) for m in mensagens), default=None)
        if maior_id is not None:
            local_db.set_last_seen_msg_id(forum_id, maior_id)

    for uuid in resultado.get("accepted_uuids", []) or []:
        local_db.mark_synced(uuid)

    on_concluido(n_novas)


def iniciar_sync(
    bridge: ClientBridge,
    local_db: LocalDB,
    state: AppState,
    on_concluido: Callable[[int], None],
    on_erro: Callable[[str], None],
) -> None:
    """Ponto de entrada: monta o payload, chama CMD_SYNC_MESSAGES e aplica o resultado."""
    payload = montar_payload_sync(local_db, state)
    bridge.call(
        protocol.CMD_SYNC_MESSAGES,
        payload,
        on_ok=lambda data: aplicar_resultado_sync(local_db, state, data, on_concluido),
        on_error=on_erro,
    )
