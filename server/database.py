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
                    icon        TEXT    NOT NULL DEFAULT '⚔',
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

                CREATE TABLE IF NOT EXISTS forum_bans (
                    forum_id  INTEGER NOT NULL,
                    user_id   INTEGER NOT NULL,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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

    # --- forums -------------------------------------------------------------------

    def create_forum(self, name: str, invite_hash: bytes, owner_id: int, icon: str = "⚔") -> int:
        """Cria um forum e ja adiciona o dono como membro. Retorna o forum_id."""
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO forums (name, invite_hash, owner_id, icon) VALUES (?, ?, ?, ?)",
                (name, invite_hash, owner_id, icon),
            )
            forum_id = cursor.lastrowid
            self._conn.execute(
                "INSERT INTO forum_members (forum_id, user_id) VALUES (?, ?)",
                (forum_id, owner_id),
            )
            self._conn.commit()
            return forum_id

    def get_forum_by_invite_hash(self, invite_hash: bytes) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM forums WHERE invite_hash = ?", (invite_hash,)
            ).fetchone()

    def get_forum_by_id(self, forum_id: int) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM forums WHERE id = ?", (forum_id,)
            ).fetchone()

    def add_member(self, forum_id: int, user_id: int) -> None:
        """Adiciona um membro ao forum. Idempotente (INSERT OR IGNORE)."""
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO forum_members (forum_id, user_id) VALUES (?, ?)",
                (forum_id, user_id),
            )
            self._conn.commit()

    def remove_member(self, forum_id: int, user_id: int) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM forum_members WHERE forum_id = ? AND user_id = ?",
                (forum_id, user_id),
            )
            self._conn.commit()

    def is_member(self, forum_id: int, user_id: int) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM forum_members WHERE forum_id = ? AND user_id = ?",
                (forum_id, user_id),
            ).fetchone()
            return row is not None

    def get_forum_members(self, forum_id: int) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(
                "SELECT users.id, users.username FROM forum_members "
                "JOIN users ON users.id = forum_members.user_id "
                "WHERE forum_members.forum_id = ?",
                (forum_id,),
            ).fetchall()

    def get_forums_for_user(self, user_id: int) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(
                "SELECT forums.* FROM forums "
                "JOIN forum_members ON forum_members.forum_id = forums.id "
                "WHERE forum_members.user_id = ?",
                (user_id,),
            ).fetchall()

    def update_forum(self, forum_id: int, name: str | None = None, icon: str | None = None) -> None:
        """Atualiza so os campos informados (None = mantem o valor atual)."""
        current = self.get_forum_by_id(forum_id)
        if current is None:
            return
        with self._lock:
            self._conn.execute(
                "UPDATE forums SET name = ?, icon = ? WHERE id = ?",
                (
                    name if name is not None else current["name"],
                    icon if icon is not None else current["icon"],
                    forum_id,
                ),
            )
            self._conn.commit()

    def update_invite_hash(self, forum_id: int, invite_hash: bytes) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE forums SET invite_hash = ? WHERE id = ?", (invite_hash, forum_id)
            )
            self._conn.commit()

    def delete_forum(self, forum_id: int) -> None:
        """Apaga o forum e todos os dados relacionados (membros, chaves,
        mensagens, roles, banimentos)."""
        with self._lock:
            self._conn.execute("DELETE FROM member_roles WHERE forum_id = ?", (forum_id,))
            self._conn.execute("DELETE FROM roles WHERE forum_id = ?", (forum_id,))
            self._conn.execute("DELETE FROM messages WHERE forum_id = ?", (forum_id,))
            self._conn.execute("DELETE FROM forum_keys WHERE forum_id = ?", (forum_id,))
            self._conn.execute("DELETE FROM forum_bans WHERE forum_id = ?", (forum_id,))
            self._conn.execute("DELETE FROM forum_members WHERE forum_id = ?", (forum_id,))
            self._conn.execute("DELETE FROM forums WHERE id = ?", (forum_id,))
            self._conn.commit()

    def ban_user(self, forum_id: int, user_id: int) -> None:
        """Remove o membro e registra o banimento (impede reentrada via convite)."""
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO forum_bans (forum_id, user_id) VALUES (?, ?)",
                (forum_id, user_id),
            )
            self._conn.execute(
                "DELETE FROM forum_members WHERE forum_id = ? AND user_id = ?", (forum_id, user_id)
            )
            self._conn.commit()

    def is_banned(self, forum_id: int, user_id: int) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM forum_bans WHERE forum_id = ? AND user_id = ?",
                (forum_id, user_id),
            ).fetchone()
            return row is not None

    # --- forum_keys -----------------------------------------------------------

    def save_forum_key(
        self, forum_id: int, user_id: int, encrypted_aes_key: bytes, key_version: int
    ) -> None:
        """Guarda a AES key do forum cifrada com a RSA publica de um membro."""
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO forum_keys
                   (forum_id, user_id, encrypted_aes_key, key_version)
                   VALUES (?, ?, ?, ?)""",
                (forum_id, user_id, encrypted_aes_key, key_version),
            )
            self._conn.commit()

    def get_forum_key(self, forum_id: int, user_id: int, key_version: int) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM forum_keys WHERE forum_id = ? AND user_id = ? AND key_version = ?",
                (forum_id, user_id, key_version),
            ).fetchone()

    def get_current_key_version(self, forum_id: int) -> int:
        """Maior key_version ja distribuida para o forum (0 se nenhuma ainda)."""
        with self._lock:
            row = self._conn.execute(
                "SELECT MAX(key_version) AS v FROM forum_keys WHERE forum_id = ?",
                (forum_id,),
            ).fetchone()
            return row["v"] if row and row["v"] is not None else 0

    # --- messages (forum) -------------------------------------------------------

    def save_message(
        self,
        uuid: str,
        forum_id: int,
        sender_id: int,
        ciphertext: bytes,
        iv: bytes,
        key_version: int,
    ) -> int:
        """Persiste uma mensagem de forum ja cifrada. O servidor nunca decifra."""
        with self._lock:
            cursor = self._conn.execute(
                """INSERT INTO messages (uuid, forum_id, sender_id, ciphertext, iv, key_version)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (uuid, forum_id, sender_id, ciphertext, iv, key_version),
            )
            self._conn.commit()
            return cursor.lastrowid

    def get_messages_for_forum(self, forum_id: int) -> list[sqlite3.Row]:
        """Historico completo do forum, em ordem cronologica."""
        with self._lock:
            return self._conn.execute(
                "SELECT messages.*, users.username AS sender_username FROM messages "
                "JOIN users ON users.id = messages.sender_id "
                "WHERE messages.forum_id = ? ORDER BY messages.id ASC",
                (forum_id,),
            ).fetchall()

    def get_message_by_uuid(self, uuid: str) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM messages WHERE uuid = ?", (uuid,)
            ).fetchone()

    def set_message_pinned(self, uuid: str, pinned: bool) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE messages SET pinned = ? WHERE uuid = ?", (int(pinned), uuid)
            )
            self._conn.commit()

    def delete_message(self, uuid: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM messages WHERE uuid = ?", (uuid,))
            self._conn.commit()

    # --- roles ------------------------------------------------------------------

    def create_role(
        self, forum_id: int, name: str, color: str, permissions: int, priority: int = 0
    ) -> int:
        """Cria uma role no forum. Retorna o role_id."""
        with self._lock:
            cursor = self._conn.execute(
                """INSERT INTO roles (forum_id, name, color, permissions, priority)
                   VALUES (?, ?, ?, ?, ?)""",
                (forum_id, name, color, permissions, priority),
            )
            self._conn.commit()
            return cursor.lastrowid

    def get_role_by_id(self, role_id: int) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM roles WHERE id = ?", (role_id,)
            ).fetchone()

    def get_role_by_name(self, forum_id: int, name: str) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM roles WHERE forum_id = ? AND name = ?", (forum_id, name)
            ).fetchone()

    def get_roles_for_forum(self, forum_id: int) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(
                "SELECT * FROM roles WHERE forum_id = ? ORDER BY priority DESC", (forum_id,)
            ).fetchall()

    def update_role(
        self, role_id: int, name: str | None = None, color: str | None = None,
        permissions: int | None = None, priority: int | None = None,
    ) -> None:
        """Atualiza so os campos informados (None = mantem o valor atual)."""
        current = self.get_role_by_id(role_id)
        if current is None:
            return
        with self._lock:
            self._conn.execute(
                "UPDATE roles SET name = ?, color = ?, permissions = ?, priority = ? WHERE id = ?",
                (
                    name if name is not None else current["name"],
                    color if color is not None else current["color"],
                    permissions if permissions is not None else current["permissions"],
                    priority if priority is not None else current["priority"],
                    role_id,
                ),
            )
            self._conn.commit()

    def delete_role(self, role_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM member_roles WHERE role_id = ?", (role_id,))
            self._conn.execute("DELETE FROM roles WHERE id = ?", (role_id,))
            self._conn.commit()

    def assign_role(self, forum_id: int, user_id: int, role_id: int) -> None:
        """Atribui uma role a um membro. Idempotente."""
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO member_roles (forum_id, user_id, role_id) VALUES (?, ?, ?)",
                (forum_id, user_id, role_id),
            )
            self._conn.commit()

    def revoke_role(self, forum_id: int, user_id: int, role_id: int) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM member_roles WHERE forum_id = ? AND user_id = ? AND role_id = ?",
                (forum_id, user_id, role_id),
            )
            self._conn.commit()

    def get_roles_for_member(self, forum_id: int, user_id: int) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(
                "SELECT roles.* FROM roles "
                "JOIN member_roles ON member_roles.role_id = roles.id "
                "WHERE member_roles.forum_id = ? AND member_roles.user_id = ?",
                (forum_id, user_id),
            ).fetchall()

    def get_members_for_role(self, role_id: int) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(
                "SELECT users.id, users.username FROM users "
                "JOIN member_roles ON member_roles.user_id = users.id "
                "WHERE member_roles.role_id = ?",
                (role_id,),
            ).fetchall()

    def get_member_permission_mask(self, forum_id: int, user_id: int) -> int:
        """OR de todas as permissions das roles do membro nesse forum."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT roles.permissions FROM roles "
                "JOIN member_roles ON member_roles.role_id = roles.id "
                "WHERE member_roles.forum_id = ? AND member_roles.user_id = ?",
                (forum_id, user_id),
            ).fetchall()
            mask = 0
            for row in rows:
                mask |= row["permissions"]
            return mask

    def close(self) -> None:
        self._conn.close()
