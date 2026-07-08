"""Gerenciador de sessoes: mapa socket -> dados do usuario, thread-safe.

Cada conexao aceita pelo servidor tem uma thread propria. O SessionManager e
o ponto de estado compartilhado entre essas threads, protegido por um Lock.

Guarda, por socket conectado:
    {"user_id": int, "username": str, "session_token": str}

Um usuario autenticado tem user_id != None; antes do login o registro existe
mas sem identidade.
"""

from __future__ import annotations

import socket
import threading

from shared import protocol


class SessionManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        # socket -> dict de dados da sessao
        self._sessions: dict[socket.socket, dict] = {}

    # --- ciclo de vida da conexao --------------------------------------------

    def add(self, sock: socket.socket) -> None:
        """Registra uma nova conexao (ainda nao autenticada)."""
        with self._lock:
            self._sessions[sock] = {"user_id": None, "username": None, "session_token": None}

    def remove(self, sock: socket.socket) -> dict | None:
        """Remove a conexao e retorna os dados que ela tinha (ou None)."""
        with self._lock:
            return self._sessions.pop(sock, None)

    # --- autenticacao ---------------------------------------------------------

    def authenticate(self, sock: socket.socket, user_id: int, username: str, token: str) -> None:
        """Marca a sessao como autenticada."""
        with self._lock:
            data = self._sessions.get(sock)
            if data is not None:
                data.update(user_id=user_id, username=username, session_token=token)

    def get(self, sock: socket.socket) -> dict | None:
        with self._lock:
            data = self._sessions.get(sock)
            return dict(data) if data is not None else None

    def is_authenticated(self, sock: socket.socket) -> bool:
        with self._lock:
            data = self._sessions.get(sock)
            return bool(data and data.get("user_id") is not None)

    def socket_for_user(self, user_id: int) -> socket.socket | None:
        """Retorna o socket conectado de um usuario, se estiver online."""
        with self._lock:
            for sock, data in self._sessions.items():
                if data.get("user_id") == user_id:
                    return sock
            return None

    def online_user_ids(self) -> set[int]:
        with self._lock:
            return {d["user_id"] for d in self._sessions.values() if d.get("user_id") is not None}

    # --- envio ----------------------------------------------------------------

    def unicast(self, sock: socket.socket, message: dict) -> bool:
        """Envia uma mensagem para um socket. Retorna False se falhar."""
        try:
            sock.sendall(protocol.pack_message(message))
            return True
        except OSError:
            return False

    def send_to_user(self, user_id: int, message: dict) -> bool:
        """Envia para um usuario pelo id, se estiver online."""
        sock = self.socket_for_user(user_id)
        if sock is None:
            return False
        return self.unicast(sock, message)

    def broadcast_to_users(self, user_ids, message: dict, exclude: socket.socket | None = None) -> int:
        """Envia `message` a todos os user_ids online. Retorna quantos receberam.

        Usado para rotear eventos de forum apenas aos membros conectados.
        """
        targets: list[socket.socket] = []
        wanted = set(user_ids)
        with self._lock:
            for sock, data in self._sessions.items():
                if sock is exclude:
                    continue
                if data.get("user_id") in wanted:
                    targets.append(sock)
        sent = 0
        for sock in targets:
            if self.unicast(sock, message):
                sent += 1
        return sent
