"""Distribuicao de chaves AES de forum (Sprint 1, Dia 6).

O servidor apenas armazena/repassa a chave AES ja cifrada com a RSA publica
de cada membro. Nunca ve a chave em claro.

distribute_key -> guarda encrypted_aes_key por (forum, membro, key_version)
get_pubkey     -> devolve a public key de outro usuario (Dia 4)
"""

# TODO(Sprint 1, Dia 4): get_pubkey.
# TODO(Sprint 1, Dia 6): distribute_key + rotacao de versao.
