"""Utilitarios criptograficos do Corvo Negro.

Camadas de protecao:
    - Autenticacao: SHA-256 + PBKDF2 (100k iteracoes, salt 16B unico por usuario)
    - Troca de chaves: RSA-2048 com padding OAEP + SHA-256
    - Sessao: AES-256-CBC

Funcoes previstas (Sprint 1, Dia 1):
    hash_password(password) -> bytes
    verify_password(password, stored) -> bool
    generate_rsa_keypair() -> tuple[bytes, bytes]   # (priv_pem, pub_pem)
    rsa_encrypt(data, public_key_pem) -> bytes
    rsa_decrypt(ciphertext, private_key_pem) -> bytes
    aes_encrypt(plaintext, key) -> tuple[bytes, bytes]   # (ciphertext, iv)
    aes_decrypt(ciphertext, key, iv) -> bytes
    generate_aes_key() -> bytes                     # 32 bytes = AES-256
    derive_key_from_password(password, salt) -> bytes
"""

# TODO(Sprint 1, Dia 1): implementar utilitarios criptograficos.
