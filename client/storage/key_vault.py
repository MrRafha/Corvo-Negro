"""Armazenamento seguro da chave privada RSA (Sprint 1, Dia 4).

A private key nunca sai do dispositivo em claro: e cifrada com AES-256 usando
chave derivada da senha (PBKDF2) e so e decifrada em memoria apos o login.

Formato do arquivo em disco (bytes concatenados):
    salt (16B) || iv (16B) || ciphertext

Uso:
    save_private_key("corvo", priv_pem, "s3nh4!")
    priv_pem = load_private_key("corvo", "s3nh4!")
"""

from __future__ import annotations

import os
from pathlib import Path

from shared import crypto_utils

VAULT_DIR = Path.home() / ".corvo_negro" / "keys"


def _vault_path(username: str) -> Path:
    return VAULT_DIR / f"{username}.key"


def save_private_key(username: str, private_key_pem: bytes, password: str) -> None:
    """Cifra `private_key_pem` com chave derivada da senha e grava em disco."""
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    salt = os.urandom(crypto_utils.SALT_SIZE)
    key = crypto_utils.derive_key_from_password(password, salt)
    ciphertext, iv = crypto_utils.aes_encrypt(private_key_pem, key)
    _vault_path(username).write_bytes(salt + iv + ciphertext)


def load_private_key(username: str, password: str) -> bytes:
    """Le e decifra a chave privada do usuario com a senha informada.

    Levanta FileNotFoundError se nao houver vault para o usuario, ou
    ValueError/InvalidTag se a senha estiver errada (padding PKCS7 invalido).
    """
    path = _vault_path(username)
    if not path.exists():
        raise FileNotFoundError(f"nenhuma chave privada salva para '{username}'")

    raw = path.read_bytes()
    salt, iv, ciphertext = (
        raw[: crypto_utils.SALT_SIZE],
        raw[crypto_utils.SALT_SIZE : crypto_utils.SALT_SIZE + crypto_utils.IV_SIZE],
        raw[crypto_utils.SALT_SIZE + crypto_utils.IV_SIZE :],
    )
    key = crypto_utils.derive_key_from_password(password, salt)
    return crypto_utils.aes_decrypt(ciphertext, key, iv)


def has_vault(username: str) -> bool:
    """Verifica se ja existe uma chave privada salva para o usuario."""
    return _vault_path(username).exists()
