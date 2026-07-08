"""Despachador de mensagens: mapeia cmd -> handler.

Recebe o dict ja desempacotado pelo protocol.unpack_message e chama o
handler correspondente (auth, forum, message, role, key_exchange).
"""

# TODO(Sprint 1, Dia 2): tabela de despacho cmd -> handler.
