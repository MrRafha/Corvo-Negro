"""Cache local SQLite cifrado (Sprint 3, Dia 12).

Tabelas: messages, forums, roles, known_users. Cada campo sensivel e cifrado
com chave derivada da senha do usuario (PBKDF2). Toda mensagem carrega uuid +
origin_timestamp para o merge de sync.
"""

# TODO(Sprint 3, Dia 12): DB local cifrado.
