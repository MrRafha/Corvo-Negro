"""Armazenamento seguro da chave privada RSA (Sprint 1, Dia 4).

A private key nunca sai do dispositivo em claro: e cifrada com AES-256 usando
chave derivada da senha (PBKDF2) e so e decifrada em memoria apos o login.
"""

# TODO(Sprint 1, Dia 4): salvar/carregar priv key cifrada com a senha.
