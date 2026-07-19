"""Testes do LocalDB: cache local SQLite cifrado (Sprint 3, Dia 12).

Cobre:
    - init_schema idempotente (abrir 2x nao quebra)
    - save_message/get_messages_for_forum round-trip, ordenado por origin_timestamp
    - uuid duplicado nao duplica linha (INSERT OR IGNORE)
    - get_unsynced_messages/mark_synced refletem o campo synced
    - abrir com senha errada nao decifra corretamente os metadados (sender)
    - reabrir com a senha certa recupera os dados normalmente
    - known_users e forums: save/get round-trip
"""

from __future__ import annotations

import pytest

from client.storage.local_db import LocalDB
from shared import crypto_utils


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "corvo_local.db")


def _nova_mensagem(db: LocalDB, uuid: str, forum_id: int, sender: str, texto: str,
                    origin_timestamp: str, key_version: int = 1, synced: bool = False) -> bytes:
    aes_key = crypto_utils.generate_aes_key()
    ciphertext, iv = crypto_utils.aes_encrypt(texto.encode("utf-8"), aes_key)
    db.save_message(uuid, forum_id, sender, ciphertext, iv, key_version, origin_timestamp, synced=synced)
    return aes_key


def test_init_schema_idempotente(db_path):
    db1 = LocalDB(db_path, "senha123")
    db1.close()
    db2 = LocalDB(db_path, "senha123")  # reabrir nao deve quebrar (IF NOT EXISTS)
    db2.close()


def test_save_e_get_messages_round_trip(db_path):
    db = LocalDB(db_path, "senha123")
    try:
        _nova_mensagem(db, "uuid-1", 10, "alice", "primeira", "2026-07-13T10:00:00")
        _nova_mensagem(db, "uuid-2", 10, "bob", "segunda", "2026-07-13T10:05:00")

        mensagens = db.get_messages_for_forum(10)
        assert len(mensagens) == 2
        assert [m["uuid"] for m in mensagens] == ["uuid-1", "uuid-2"]
        assert mensagens[0]["sender"] == "alice"
        assert mensagens[1]["sender"] == "bob"
    finally:
        db.close()


def test_get_messages_ordenado_por_origin_timestamp(db_path):
    db = LocalDB(db_path, "senha123")
    try:
        # insere fora de ordem cronologica de proposito
        _nova_mensagem(db, "uuid-b", 10, "bob", "chegou depois mas e mais antiga", "2026-07-13T09:00:00")
        _nova_mensagem(db, "uuid-a", 10, "alice", "chegou primeiro mas e mais nova", "2026-07-13T11:00:00")

        mensagens = db.get_messages_for_forum(10)
        assert [m["uuid"] for m in mensagens] == ["uuid-b", "uuid-a"]
    finally:
        db.close()


def test_uuid_duplicado_nao_duplica_linha(db_path):
    db = LocalDB(db_path, "senha123")
    try:
        _nova_mensagem(db, "uuid-1", 10, "alice", "original", "2026-07-13T10:00:00")
        _nova_mensagem(db, "uuid-1", 10, "alice", "original", "2026-07-13T10:00:00")

        mensagens = db.get_messages_for_forum(10)
        assert len(mensagens) == 1
    finally:
        db.close()


def test_unsynced_messages_e_mark_synced(db_path):
    db = LocalDB(db_path, "senha123")
    try:
        _nova_mensagem(db, "uuid-1", 10, "alice", "nao sincronizada", "2026-07-13T10:00:00", synced=False)
        _nova_mensagem(db, "uuid-2", 10, "bob", "ja sincronizada", "2026-07-13T10:05:00", synced=True)

        pendentes = db.get_unsynced_messages()
        assert len(pendentes) == 1
        assert pendentes[0]["uuid"] == "uuid-1"

        db.mark_synced("uuid-1")
        assert db.get_unsynced_messages() == []
    finally:
        db.close()


def test_reabrir_com_senha_correta_recupera_dados(db_path):
    db1 = LocalDB(db_path, "senha-certa")
    _nova_mensagem(db1, "uuid-1", 10, "alice", "mensagem", "2026-07-13T10:00:00")
    db1.close()

    db2 = LocalDB(db_path, "senha-certa")
    try:
        mensagens = db2.get_messages_for_forum(10)
        assert len(mensagens) == 1
        assert mensagens[0]["sender"] == "alice"
    finally:
        db2.close()


def test_reabrir_com_senha_errada_nao_decifra_corretamente(db_path):
    db1 = LocalDB(db_path, "senha-certa")
    _nova_mensagem(db1, "uuid-1", 10, "alice", "mensagem", "2026-07-13T10:00:00")
    db1.close()

    db2 = LocalDB(db_path, "senha-errada")
    try:
        with pytest.raises(Exception):
            db2.get_messages_for_forum(10)
    finally:
        db2.close()


def test_forums_save_e_get(db_path):
    db = LocalDB(db_path, "senha123")
    try:
        db.save_forum(1, "Conclave dos Corvos", "⚔")
        foruns = db.get_known_forums()
        assert len(foruns) == 1
        assert foruns[0] == {"forum_id": 1, "name": "Conclave dos Corvos", "icon": "⚔"}
    finally:
        db.close()


def test_user_id_persiste_entre_aberturas(db_path):
    db1 = LocalDB(db_path, "senha123")
    assert db1.get_user_id() is None
    db1.set_user_id(42)
    db1.close()

    db2 = LocalDB(db_path, "senha123")
    try:
        assert db2.get_user_id() == 42
    finally:
        db2.close()


def test_known_users_save_e_get(db_path):
    db = LocalDB(db_path, "senha123")
    try:
        _, pub_pem = crypto_utils.generate_rsa_keypair()
        db.save_known_user("bob", pub_pem)

        recuperado = db.get_known_user("bob")
        assert recuperado is not None
        assert recuperado["public_key_pem"] == pub_pem
        assert db.get_known_user("fantasma") is None
    finally:
        db.close()
