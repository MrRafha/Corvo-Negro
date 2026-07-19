"""Cache local SQLite cifrado (Sprint 3, Dia 12).

Guarda o historico de mensagens visto (online ou modo LAN) para sobreviver a
fechamentos do app e alimentar o merge de sync com o servidor central.

Modelo de cifragem — campo a campo, nao o arquivo inteiro (mesmo espirito de
client/storage/key_vault.py): `ciphertext`/`iv` das mensagens ja chegam
cifrados com a AES do forum (a mesma cifragem do modo online) e sao gravados
como vieram — cifrar de novo com a chave da senha seria dupla-cifragem sem
ganho real de seguranca e so complicaria o sync. O que e cifrado com a chave
derivada da senha do usuario (PBKDF2, mesmo `derive_key_from_password` do
key_vault) sao os METADADOS que aparecem em claro no banco: nome de quem
enviou, nome do forum, chave publica de usuarios conhecidos.

O salt fica em claro numa tabela `_meta` (nao e segredo — precisa ser lido
antes de re-derivar a chave em cada abertura, mesmo padrao do prefixo do
arquivo do key_vault).
"""

from __future__ import annotations

import os
import sqlite3
import threading

from shared import crypto_utils


class LocalDB:
    def __init__(self, path: str, password: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self.init_schema()
        self._key = crypto_utils.derive_key_from_password(password, self._obter_ou_criar_salt())

    # --- schema -----------------------------------------------------------------

    def init_schema(self) -> None:
        """Cria as tabelas (idempotente — usa IF NOT EXISTS)."""
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS _meta (
                    key   TEXT PRIMARY KEY,
                    value BLOB NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid              TEXT    UNIQUE NOT NULL,
                    forum_id          INTEGER NOT NULL,
                    sender_enc        BLOB    NOT NULL,
                    sender_iv         BLOB    NOT NULL,
                    ciphertext        BLOB    NOT NULL,
                    iv                BLOB    NOT NULL,
                    key_version       INTEGER NOT NULL DEFAULT 1,
                    origin_timestamp  TEXT    NOT NULL,
                    synced            INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS forums (
                    forum_id  INTEGER PRIMARY KEY,
                    name_enc  BLOB NOT NULL,
                    name_iv   BLOB NOT NULL,
                    icon      TEXT
                );

                CREATE TABLE IF NOT EXISTS known_users (
                    username        TEXT PRIMARY KEY,
                    pubkey_enc      BLOB NOT NULL,
                    pubkey_iv       BLOB NOT NULL
                );
            """)
            self._conn.commit()

    def _obter_ou_criar_salt(self) -> bytes:
        with self._lock:
            row = self._conn.execute("SELECT value FROM _meta WHERE key = 'salt'").fetchone()
            if row is not None:
                return bytes(row["value"])
            salt = os.urandom(crypto_utils.SALT_SIZE)
            self._conn.execute("INSERT INTO _meta (key, value) VALUES ('salt', ?)", (salt,))
            self._conn.commit()
            return salt

    # --- cifragem de campo --------------------------------------------------------

    def _cifrar_campo(self, texto: str) -> tuple[bytes, bytes]:
        return crypto_utils.aes_encrypt(texto.encode("utf-8"), self._key)

    def _decifrar_campo(self, ciphertext: bytes, iv: bytes) -> str:
        return crypto_utils.aes_decrypt(bytes(ciphertext), self._key, bytes(iv)).decode("utf-8")

    # --- messages -----------------------------------------------------------------

    def save_message(
        self, uuid: str, forum_id: int, sender: str, ciphertext: bytes, iv: bytes,
        key_version: int, origin_timestamp: str, synced: bool = False,
    ) -> None:
        """Persiste uma mensagem (ja cifrada com a AES do forum). Idempotente
        por uuid — reenviar a mesma mensagem nao duplica linha."""
        sender_enc, sender_iv = self._cifrar_campo(sender)
        with self._lock:
            self._conn.execute(
                """INSERT OR IGNORE INTO messages
                   (uuid, forum_id, sender_enc, sender_iv, ciphertext, iv, key_version,
                    origin_timestamp, synced)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (uuid, forum_id, sender_enc, sender_iv, ciphertext, iv, key_version,
                 origin_timestamp, int(synced)),
            )
            self._conn.commit()

    def get_messages_for_forum(self, forum_id: int) -> list[dict]:
        """Historico local do forum, ordenado por origin_timestamp (nao pelo
        id local, que e so ordem de chegada — mensagens LAN e online podem
        chegar fora de ordem cronologica)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM messages WHERE forum_id = ? ORDER BY origin_timestamp ASC",
                (forum_id,),
            ).fetchall()
        return [self._linha_para_dict(row) for row in rows]

    def get_unsynced_messages(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM messages WHERE synced = 0").fetchall()
        return [self._linha_para_dict(row) for row in rows]

    def mark_synced(self, uuid: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE messages SET synced = 1 WHERE uuid = ?", (uuid,))
            self._conn.commit()

    def get_last_seen_msg_id(self, forum_id: int) -> int:
        """Maior id de SERVIDOR ja visto para este forum (nao confundir com o
        `uuid`/id local das mensagens — este e o id incremental do servidor,
        usado para pedir so o que falta no proximo sync). 0 se nunca sincronizou."""
        chave = f"last_seen:{forum_id}"
        with self._lock:
            row = self._conn.execute("SELECT value FROM _meta WHERE key = ?", (chave,)).fetchone()
        return int(bytes(row["value"]).decode("utf-8")) if row is not None else 0

    def set_last_seen_msg_id(self, forum_id: int, msg_id: int) -> None:
        chave = f"last_seen:{forum_id}"
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO _meta (key, value) VALUES (?, ?)",
                (chave, str(msg_id).encode("utf-8")),
            )
            self._conn.commit()

    # --- identidade (para permitir login offline / modo LAN direto) ----------------

    def get_user_id(self) -> int | None:
        """user_id salvo na ultima vez que este usuario logou online com
        sucesso — permite reentrar em modo LAN sem servidor (o servidor e
        quem normalmente atribui esse id, entao so existe apos o 1o login)."""
        with self._lock:
            row = self._conn.execute("SELECT value FROM _meta WHERE key = 'user_id'").fetchone()
        return int(bytes(row["value"]).decode("utf-8")) if row is not None else None

    def set_user_id(self, user_id: int) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO _meta (key, value) VALUES ('user_id', ?)",
                (str(user_id).encode("utf-8"),),
            )
            self._conn.commit()

    def _linha_para_dict(self, row: sqlite3.Row) -> dict:
        return {
            "uuid": row["uuid"],
            "forum_id": row["forum_id"],
            "sender": self._decifrar_campo(row["sender_enc"], row["sender_iv"]),
            "ciphertext": bytes(row["ciphertext"]),
            "iv": bytes(row["iv"]),
            "key_version": row["key_version"],
            "origin_timestamp": row["origin_timestamp"],
            "synced": bool(row["synced"]),
        }

    # --- forums -----------------------------------------------------------------

    def save_forum(self, forum_id: int, name: str, icon: str) -> None:
        name_enc, name_iv = self._cifrar_campo(name)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO forums (forum_id, name_enc, name_iv, icon) VALUES (?, ?, ?, ?)",
                (forum_id, name_enc, name_iv, icon),
            )
            self._conn.commit()

    def get_known_forums(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM forums").fetchall()
        return [
            {"forum_id": row["forum_id"], "name": self._decifrar_campo(row["name_enc"], row["name_iv"]),
             "icon": row["icon"]}
            for row in rows
        ]

    # --- known_users --------------------------------------------------------------

    def save_known_user(self, username: str, public_key_pem: bytes) -> None:
        pubkey_enc, pubkey_iv = crypto_utils.aes_encrypt(public_key_pem, self._key)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO known_users (username, pubkey_enc, pubkey_iv) VALUES (?, ?, ?)",
                (username, pubkey_enc, pubkey_iv),
            )
            self._conn.commit()

    def get_known_user(self, username: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM known_users WHERE username = ?", (username,)
            ).fetchone()
        if row is None:
            return None
        pubkey = crypto_utils.aes_decrypt(bytes(row["pubkey_enc"]), self._key, bytes(row["pubkey_iv"]))
        return {"username": row["username"], "public_key_pem": pubkey}

    # --- ciclo de vida --------------------------------------------------------------

    def close(self) -> None:
        self._conn.close()
