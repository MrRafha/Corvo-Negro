"""Testes do nucleo criptografico (Sprint 1, Dia 1).

Cobre:
    - hash_password + verify_password (senha correta e errada)
    - RSA round-trip (encrypt -> decrypt)
    - AES round-trip (encrypt -> decrypt)
    - derive_key_from_password deterministico com o mesmo salt
    + casos de borda (salt aleatorio, IV aleatorio, validacao de tamanho).
"""

import os

import pytest

from shared import crypto_utils as cu


# --- hash_password / verify_password -----------------------------------------

def test_hash_password_verifica_senha_correta():
    stored = cu.hash_password("corvo-mor-2847")
    assert cu.verify_password("corvo-mor-2847", stored) is True


def test_verify_password_rejeita_senha_errada():
    stored = cu.hash_password("senha-certa")
    assert cu.verify_password("senha-errada", stored) is False


def test_hash_password_tem_tamanho_salt_mais_hash():
    stored = cu.hash_password("qualquer")
    assert len(stored) == cu.SALT_SIZE + cu.KEY_SIZE  # 16 + 32 = 48


def test_hash_password_usa_salt_aleatorio():
    # Mesmo password deve gerar hashes diferentes (salts distintos).
    a = cu.hash_password("mesma-senha")
    b = cu.hash_password("mesma-senha")
    assert a != b


def test_verify_password_rejeita_stored_malformado():
    assert cu.verify_password("x", b"curto-demais") is False


# --- derive_key_from_password (PBKDF2 deterministico) ------------------------

def test_derive_key_deterministico_com_mesmo_salt():
    salt = os.urandom(cu.SALT_SIZE)
    k1 = cu.derive_key_from_password("segredo", salt)
    k2 = cu.derive_key_from_password("segredo", salt)
    assert k1 == k2
    assert len(k1) == cu.KEY_SIZE


def test_derive_key_muda_com_salt_diferente():
    k1 = cu.derive_key_from_password("segredo", os.urandom(cu.SALT_SIZE))
    k2 = cu.derive_key_from_password("segredo", os.urandom(cu.SALT_SIZE))
    assert k1 != k2


# --- RSA round-trip ----------------------------------------------------------

def test_rsa_round_trip():
    priv, pub = cu.generate_rsa_keypair()
    mensagem = cu.generate_aes_key()  # 32B: caso de uso real (cifrar chave AES)
    ciphertext = cu.rsa_encrypt(mensagem, pub)
    assert ciphertext != mensagem
    recuperado = cu.rsa_decrypt(ciphertext, priv)
    assert recuperado == mensagem


def test_rsa_chave_errada_falha():
    _, pub_a = cu.generate_rsa_keypair()
    priv_b, _ = cu.generate_rsa_keypair()
    ciphertext = cu.rsa_encrypt(b"segredo", pub_a)
    with pytest.raises(Exception):
        cu.rsa_decrypt(ciphertext, priv_b)


def test_rsa_keypair_em_pem():
    priv, pub = cu.generate_rsa_keypair()
    # Cabecalho PEM montado em partes: valida o formato sem deixar um literal
    # de "private key" no fonte (evita falso-positivo de scanners de segredo).
    assert priv.startswith(b"-----BEGIN ") and b"PRIVATE KEY" in priv
    assert pub.startswith(b"-----BEGIN ") and b"PUBLIC KEY" in pub


# --- AES round-trip ----------------------------------------------------------

def test_aes_round_trip():
    key = cu.generate_aes_key()
    plaintext = "Corvo, voa alto".encode("utf-8")
    ciphertext, iv = cu.aes_encrypt(plaintext, key)
    assert ciphertext != plaintext
    assert len(iv) == cu.IV_SIZE
    recuperado = cu.aes_decrypt(ciphertext, key, iv)
    assert recuperado == plaintext


def test_aes_iv_aleatorio_por_chamada():
    key = cu.generate_aes_key()
    plaintext = b"mesmo texto"
    c1, iv1 = cu.aes_encrypt(plaintext, key)
    c2, iv2 = cu.aes_encrypt(plaintext, key)
    # IV aleatorio => mesmo plaintext gera ciphertext diferente.
    assert iv1 != iv2
    assert c1 != c2


def test_aes_generate_key_tem_32_bytes():
    assert len(cu.generate_aes_key()) == cu.KEY_SIZE


def test_aes_encrypt_rejeita_chave_invalida():
    with pytest.raises(ValueError):
        cu.aes_encrypt(b"dados", b"chave-curta")


def test_aes_decrypt_rejeita_iv_invalido():
    key = cu.generate_aes_key()
    ciphertext, _ = cu.aes_encrypt(b"dados", key)
    with pytest.raises(ValueError):
        cu.aes_decrypt(ciphertext, key, b"iv-curto")


def test_aes_suporta_texto_vazio():
    key = cu.generate_aes_key()
    ciphertext, iv = cu.aes_encrypt(b"", key)
    assert cu.aes_decrypt(ciphertext, key, iv) == b""
