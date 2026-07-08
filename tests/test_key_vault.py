"""Testes do key_vault: salvar/carregar a chave privada RSA cifrada (Sprint 1, Dia 4).

Cobre:
    - save + load devolve exatamente a mesma private key PEM
    - has_vault reflete a existencia do arquivo
    - senha errada nao decifra corretamente (falha ao carregar a private key)
    - load sem vault existente levanta FileNotFoundError
"""

import pytest

from client.storage import key_vault
from shared import crypto_utils


@pytest.fixture(autouse=True)
def vault_isolado(tmp_path, monkeypatch):
    """Isola cada teste num diretorio temporario (nunca escreve em ~/.corvo_negro)."""
    monkeypatch.setattr(key_vault, "VAULT_DIR", tmp_path / "keys")


def test_save_e_load_devolve_a_mesma_chave():
    priv_pem, _pub_pem = crypto_utils.generate_rsa_keypair()
    key_vault.save_private_key("corvo", priv_pem, "s3nh4!")

    carregada = key_vault.load_private_key("corvo", "s3nh4!")
    assert carregada == priv_pem


def test_has_vault():
    assert not key_vault.has_vault("corvo")
    priv_pem, _ = crypto_utils.generate_rsa_keypair()
    key_vault.save_private_key("corvo", priv_pem, "s3nh4!")
    assert key_vault.has_vault("corvo")


def test_load_sem_vault_levanta_erro():
    with pytest.raises(FileNotFoundError):
        key_vault.load_private_key("fantasma", "qualquer")


def test_load_senha_errada_falha():
    priv_pem, _ = crypto_utils.generate_rsa_keypair()
    key_vault.save_private_key("corvo", priv_pem, "s3nh4correta!")

    with pytest.raises(Exception):
        key_vault.load_private_key("corvo", "senha-errada")
