"""Schema e queries SQLite do servidor.

Tabelas criadas ao longo da Sprint 1:
    users            (Dia 3)
    direct_messages  (Dia 4)
    forums           (Dia 5)
    forum_members    (Dia 5)
    forum_keys       (Dia 6)
    messages         (Dia 6)
    roles            (Dia 7)
    member_roles     (Dia 7)

Regra de ouro: o servidor guarda apenas ciphertext. Nunca texto em claro.

Uso:
    db = Database()          # :memory: (testes)
    db = Database("server.db")
    db.init_schema()
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


class Database:
    def __init__(self, path: str = ":memory:") -> None:
        self._path = path
        # check_same_thread=False: usamos um lock proprio para seguranca entre threads.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._lock = threading.Lock()

    # --- schema ---------------------------------------------------------------

    def init_schema(self) -> None:
        """Cria todas as tabelas (idempotente — usa IF NOT EXISTS)."""
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    username      TEXT    UNIQUE NOT NULL,
                    password_hash BLOB    NOT NULL,
                    public_key    BLOB    NOT NULL DEFAULT '',
                    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS direct_messages (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid           TEXT    UNIQUE NOT NULL,
                    sender_id      INTEGER NOT NULL,
                    recipient_id   INTEGER NOT NULL,
                    ciphertext     BLOB    NOT NULL,
                    encrypted_key  BLOB    NOT NULL,
                    iv             BLOB    NOT NULL,
                    timestamp      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sender_id)    REFERENCES users(id),
                    FOREIGN KEY (recipient_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS forums (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    NOT NULL,
                    invite_hash BLOB    NOT NULL,
                    owner_id    INTEGER NOT NULL,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (owner_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS forum_members (
                    forum_id  INTEGER NOT NULL,
                    user_id   INTEGER NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (forum_id, user_id),
                    FOREIGN KEY (forum_id) REFERENCES forums(id),
                    FOREIGN KEY (user_id)  REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS forum_keys (
                    forum_id          INTEGER NOT NULL,
                    user_id           INTEGER NOT NULL,
                    encrypted_aes_key BLOB    NOT NULL,
                    key_version       INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (forum_id, user_id, key_version),
                    FOREIGN KEY (forum_id) REFERENCES forums(id),
                    FOREIGN KEY (user_id)  REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid        TEXT    UNIQUE NOT NULL,
                    forum_id    INTEGER NOT NULL,
                    sender_id   INTEGER NOT NULL,
                    ciphertext  BLOB    NOT NULL,
                    iv          BLOB    NOT NULL,
                    key_version INTEGER NOT NULL DEFAULT 1,
                    pinned      INTEGER NOT NULL DEFAULT 0,
                    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (forum_id)  REFERENCES forums(id),
                    FOREIGN KEY (sender_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS roles (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    forum_id    INTEGER NOT NULL,
                    name        TEXT    NOT NULL,
                    color       TEXT    NOT NULL DEFAULT '#8b0000',
                    permissions INTEGER NOT NULL DEFAULT 1,
                    priority    INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (forum_id) REFERENCES forums(id)
                );

                CREATE TABLE IF NOT EXISTS member_roles (
                    forum_id INTEGER NOT NULL,
                    user_id  INTEGER NOT NULL,
                    role_id  INTEGER NOT NULL,
                    PRIMARY KEY (forum_id, user_id, role_id),
                    FOREIGN KEY (forum_id) REFERENCES forums(id),
                    FOREIGN KEY (user_id)  REFERENCES users(id),
                    FOREIGN KEY (role_id)  REFERENCES roles(id)
                );
            """)
            self._conn.commit()

    # --- users ----------------------------------------------------------------

    def create_user(self, username: str, password_hash: bytes, public_key: bytes = b"") -> int:
        """Insere um novo usuario. Levanta ValueError se o username ja existe."""
        with self._lock:
            try:
                cursor = self._conn.execute(
                    "INSERT INTO users (username, password_hash, public_key) VALUES (?, ?, ?)",
                    (username, password_hash, public_key),
                )
                self._conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                raise ValueError(f"usuario '{username}' ja existe")

    def get_user_by_username(self, username: str) -> sqlite3.Row | None:
        """Retorna a Row do usuario ou None se nao existir."""
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()

    def get_user_by_id(self, user_id: int) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()

    def update_public_key(self, user_id: int, public_key: bytes) -> None:
        """Atualiza a public key RSA do usuario (chamado no login, Dia 4)."""
        with self._lock:
            self._conn.execute(
                "UPDATE users SET public_key = ? WHERE id = ?", (public_key, user_id)
            )
            self._conn.commit()

    # --- direct_messages --------------------------------------------------------

    def save_direct_message(
        self,
        uuid: str,
        sender_id: int,
        recipient_id: int,
        ciphertext: bytes,
        encrypted_key: bytes,
        iv: bytes,
    ) -> int:
        """Persiste uma mensagem 1:1 ja cifrada. O servidor nunca ve o texto claro."""
        with self._lock:
            cursor = self._conn.execute(
                """INSERT INTO direct_messages
                   (uuid, sender_id, recipient_id, ciphertext, encrypted_key, iv)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (uuid, sender_id, recipient_id, ciphertext, encrypted_key, iv),
            )
            self._conn.commit()
            return cursor.lastrowid

    def close(self) -> None:
        self._conn.close()
