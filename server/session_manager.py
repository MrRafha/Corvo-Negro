"""Gerenciador de sessoes: mapa socket -> user_data, thread-safe.

Metodos previstos: register, unregister (disconnect), unicast, broadcast.
Protegido por lock para acesso concorrente das threads de cliente.
"""

# TODO(Sprint 1, Dia 2): dict {socket: user_data} com lock + broadcast/unicast.
