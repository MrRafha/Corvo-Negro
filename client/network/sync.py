"""Sync de historico ao reconectar online (Sprint 3, Dia 12).

Fluxo:
    1. Envia ao servidor last_seen_msg_id por forum
    2. Servidor devolve tudo desde esses IDs
    3. Cliente envia msgs LAN geradas offline (uuid + origin_timestamp)
    4. Servidor faz INSERT OR IGNORE (uuid = PK) -> resolve duplicatas
    5. Ordenacao final por timestamp (last-write-wins) e merge no local_db
"""

# TODO(Sprint 3, Dia 12): merge de historico LAN <-> online.
