"""Utilitarios criptograficos do Corvo Negro.

Camadas de protecao:
    - Autenticacao: SHA-256 + PBKDF2 (100k iteracoes, salt 16B unico por usuario)
    - Troca de chaves: RSA-2048 com padding OAEP + SHA-256
    - Sessao: AES-256-CBC

API publica:
    hash_password(password) -> bytes                     # salt(16B) + hash(32B)
    verify_password(password, stored) -> bool
    generate_rsa_keypair() -> tuple[bytes, bytes]        # (priv_pem, pub_pem)
    public_key_from_private(private_key_pem) -> bytes    # re-deriva a pub key
    rsa_encrypt(data, public_key_pem) -> bytes
    rsa_decrypt(ciphertext, private_key_pem) -> bytes
    aes_encrypt(plaintext, key) -> tuple[bytes, bytes]   # (ciphertext, iv)
    aes_decrypt(ciphertext, key, iv) -> bytes
    generate_aes_key() -> bytes                          # 32 bytes = AES-256
    derive_key_from_password(password, salt) -> bytes    # 32 bytes p/ cifrar DB local

Notas de seguranca:
    - PBKDF2-HMAC-SHA256 com 100_000 iteracoes (parametro PBKDF2_ITERATIONS).
    - verify_password usa comparacao em tempo constante (hmac.compare_digest).
    - RSA usa OAEP com MGF1/SHA-256 (padding autenticado, resistente a Bleichenbacher).
    - AES-256-CBC com IV aleatorio de 16B por operacao e padding PKCS7.
"""

from __future__ import annotations

import hmac
import os

from cryptography.hazmat.primitives import hashes, padding, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# --- Parametros ---------------------------------------------------------------

SALT_SIZE = 16              # bytes de salt para PBKDF2
KEY_SIZE = 32              # 32 bytes = 256 bits (AES-256 / hash de senha)
IV_SIZE = 16              # bloco AES = 128 bits
PBKDF2_ITERATIONS = 100_000
RSA_KEY_SIZE = 2048
RSA_PUBLIC_EXPONENT = 65537
AES_BLOCK_BITS = 128            # tamanho do bloco para o padding PKCS7


# --- Autenticacao de senha (SHA-256 + PBKDF2) ---------------------------------

def _pbkdf2(password: str, salt: bytes, length: int = KEY_SIZE) -> bytes:
    """Deriva `length` bytes da senha via PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def hash_password(password: str) -> bytes:
    """Gera o hash da senha para armazenamento.

    Retorna `salt (16B) || hash (32B)` = 48 bytes. O salt e aleatorio e unico
    por chamada, entao o mesmo password produz hashes diferentes a cada vez.
    """
    salt = os.urandom(SALT_SIZE)
    derived = _pbkdf2(password, salt, KEY_SIZE)
    return salt + derived


def verify_password(password: str, stored: bytes) -> bool:
    """Verifica a senha contra o valor armazenado por hash_password.

    Extrai o salt do prefixo, re-deriva o hash e compara em tempo constante.
    """
    if len(stored) != SALT_SIZE + KEY_SIZE:
        return False
    salt, expected = stored[:SALT_SIZE], stored[SALT_SIZE:]
    derived = _pbkdf2(password, salt, KEY_SIZE)
    return hmac.compare_digest(derived, expected)


# --- Chave derivada para cifrar o DB local ------------------------------------

def derive_key_from_password(password: str, salt: bytes) -> bytes:
    """Deriva uma chave AES-256 (32B) da senha, deterministica p/ o mesmo salt.

    Usada para cifrar o banco/historico local. O salt deve ser guardado junto
    (nao e segredo) para permitir re-derivar a chave nos acessos seguintes.
    """
    return _pbkdf2(password, salt, KEY_SIZE)


# --- Troca de chaves (RSA-2048 OAEP) ------------------------------------------

def generate_rsa_keypair() -> tuple[bytes, bytes]:
    """Gera um par RSA-2048 e retorna (private_pem, public_pem) em PEM.

    A chave privada e serializada SEM cifragem no PEM: quem chama e
    responsavel por protege-la (ver client/storage/key_vault.py, que a cifra
    com a senha do usuario antes de gravar em disco).
    """
    private_key = rsa.generate_private_key(
        public_exponent=RSA_PUBLIC_EXPONENT,
        key_size=RSA_KEY_SIZE,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def public_key_from_private(private_key_pem: bytes) -> bytes:
    """Deriva a public key PEM a partir de uma private key PEM existente.

    Usada quando a private key ja esta salva localmente (key_vault) e so
    precisamos re-derivar a public key para reenviar ao servidor.
    """
    private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _oaep() -> asym_padding.OAEP:
    """Padding OAEP com MGF1/SHA-256 (usado no encrypt e no decrypt)."""
    return asym_padding.OAEP(
        mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None,
    )


def rsa_encrypt(data: bytes, public_key_pem: bytes) -> bytes:
    """Cifra `data` com a chave publica RSA (PEM) usando OAEP+SHA-256.

    RSA-2048 com OAEP/SHA-256 suporta no maximo 190 bytes de payload. Por isso
    o padrao do projeto e cifrar apenas chaves AES (32B) com RSA, e as
    mensagens com AES.
    """
    public_key = serialization.load_pem_public_key(public_key_pem)
    return public_key.encrypt(data, _oaep())


def rsa_decrypt(ciphertext: bytes, private_key_pem: bytes) -> bytes:
    """Decifra `ciphertext` com a chave privada RSA (PEM) usando OAEP+SHA-256."""
    private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    return private_key.decrypt(ciphertext, _oaep())


# --- Criptografia de sessao (AES-256-CBC) -------------------------------------

def generate_aes_key() -> bytes:
    """Gera uma chave AES-256 aleatoria (32 bytes)."""
    return os.urandom(KEY_SIZE)


def aes_encrypt(plaintext: bytes, key: bytes) -> tuple[bytes, bytes]:
    """Cifra `plaintext` com AES-256-CBC. Retorna (ciphertext, iv).

    Gera um IV aleatorio de 16B por chamada e aplica padding PKCS7. O IV nao e
    secreto e deve trafegar/ser armazenado junto do ciphertext.
    """
    if len(key) != KEY_SIZE:
        raise ValueError(f"chave AES deve ter {KEY_SIZE} bytes, recebeu {len(key)}")
    iv = os.urandom(IV_SIZE)
    padder = padding.PKCS7(AES_BLOCK_BITS).padder()
    padded = padder.update(plaintext) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return ciphertext, iv


def aes_decrypt(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    """Decifra `ciphertext` (AES-256-CBC) e remove o padding PKCS7."""
    if len(key) != KEY_SIZE:
        raise ValueError(f"chave AES deve ter {KEY_SIZE} bytes, recebeu {len(key)}")
    if len(iv) != IV_SIZE:
        raise ValueError(f"IV deve ter {IV_SIZE} bytes, recebeu {len(iv)}")
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(AES_BLOCK_BITS).unpadder()
    return unpadder.update(padded) + unpadder.finalize()
