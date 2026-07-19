"""Conexoes P2P em modo LAN (Sprint 3, Dia 11).

Ao descobrir um peer (via lan_discovery.LanBrowser), abre TCP direto, faz
handshake com identidade assinada (RSA-PSS, prova posse da chave privada),
verifica foruns em comum e mantem a conexao viva. Mensagens de forum sao
cifradas com a AES do forum (igual ao modo online) e retransmitidas a todos
os peers conectados que tambem sao membros daquele forum.

Nao reaproveita client.network.client_socket.CorvoClient (pensado pra uma
unica conexao 1:1 com host/porta fixos do servidor central) porque o mesh
precisa de N conexoes simultaneas, uma por peer, cada uma com seu proprio
socket e thread de recv.
"""

from __future__ import annotations

import secrets
import socket
import threading
import time
from typing import Callable

from shared import crypto_utils, protocol

_TIMEOUT_HANDSHAKE = 5.0


class _MeshConnection:
    """Uma conexao TCP com um unico peer: socket + thread de recv dedicada."""

    def __init__(self, sock: socket.socket, peer_user_id: int, peer_username: str,
                 peer_forum_ids: set[int], on_message: Callable[[dict], None],
                 on_closed: Callable[["_MeshConnection"], None]) -> None:
        self.sock = sock
        self.peer_user_id = peer_user_id
        self.peer_username = peer_username
        self.peer_forum_ids = peer_forum_ids
        self._on_message = on_message
        self._on_closed = on_closed
        self._running = threading.Event()
        self._running.set()
        self._thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._thread.start()

    def _recv_loop(self) -> None:
        try:
            while self._running.is_set():
                try:
                    message = protocol.unpack_message(self.sock)
                except protocol.ProtocolError:
                    continue
                except OSError:
                    break
                if message is None:
                    break
                self._on_message(message)
        finally:
            self._running.clear()
            self._on_closed(self)

    def send(self, message: dict) -> bool:
        try:
            self.sock.sendall(protocol.pack_message(message))
            return True
        except OSError:
            return False

    def close(self) -> None:
        self._running.clear()
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


class MeshPeerManager:
    """Gerencia todas as conexoes P2P deste cliente em modo LAN."""

    def __init__(
        self,
        my_user_id: int,
        my_username: str,
        private_key_pem: bytes,
        public_key_pem: bytes,
        meus_foruns: Callable[[], set[int]],
        on_message: Callable[[dict], None],
        on_peers_changed: Callable[[int], None],
    ) -> None:
        self._my_user_id = my_user_id
        self._my_username = my_username
        self._private_key_pem = private_key_pem
        self._public_key_pem = public_key_pem
        self._meus_foruns = meus_foruns
        self._on_message = on_message
        self._on_peers_changed = on_peers_changed

        self._listen_sock: socket.socket | None = None
        self._accept_thread: threading.Thread | None = None
        self._running = threading.Event()
        self._lock = threading.Lock()
        self._conexoes: dict[int, _MeshConnection] = {}  # peer_user_id -> conexao

    # --- ciclo de vida --------------------------------------------------------

    def start_listening(self) -> int:
        """Abre um socket servidor numa porta livre escolhida pelo SO e
        comeca a aceitar handshakes de entrada. Retorna a porta escolhida
        (para publicar via LanAdvertiser)."""
        self._listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listen_sock.bind(("0.0.0.0", 0))
        self._listen_sock.listen(8)
        porta = self._listen_sock.getsockname()[1]
        self._running.set()
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()
        return porta

    def _accept_loop(self) -> None:
        while self._running.is_set():
            try:
                sock, _addr = self._listen_sock.accept()
            except OSError:
                break
            threading.Thread(target=self._handshake_recebido, args=(sock,), daemon=True).start()

    def stop(self) -> None:
        self._running.clear()
        if self._listen_sock is not None:
            try:
                self._listen_sock.close()
            except OSError:
                pass
            self._listen_sock = None
        with self._lock:
            conexoes = list(self._conexoes.values())
            self._conexoes.clear()
        for conn in conexoes:
            conn.close()

    # --- handshake --------------------------------------------------------------

    def _assinar_identidade(self, nonce: str) -> dict:
        payload = f"{self._my_user_id}:{self._my_username}:{nonce}".encode("utf-8")
        signature = crypto_utils.rsa_sign(payload, self._private_key_pem)
        return {
            "user_id": self._my_user_id,
            "username": self._my_username,
            "public_key_pem": self._public_key_pem.decode("utf-8"),
            "forums": sorted(self._meus_foruns()),
            "nonce": nonce,
            "signature": signature.hex(),
        }

    def _verificar_identidade(self, dados: dict) -> bool:
        try:
            nonce = dados["nonce"]
            payload = f"{dados['user_id']}:{dados['username']}:{nonce}".encode("utf-8")
            signature = bytes.fromhex(dados["signature"])
            public_key_pem = dados["public_key_pem"].encode("utf-8")
        except (KeyError, ValueError):
            return False
        return crypto_utils.rsa_verify(payload, signature, public_key_pem)

    def connect_to_peer(self, peer) -> None:
        """Abre uma conexao de saida para `peer` (lan_discovery.PeerInfo) e
        envia o handshake. Nao bloqueia o chamador (roda numa thread)."""
        if peer.user_id in self._conexoes:
            return
        threading.Thread(target=self._conectar_thread, args=(peer,), daemon=True).start()

    def _conectar_thread(self, peer) -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(_TIMEOUT_HANDSHAKE)
            sock.connect((peer.host, peer.port))
            nonce = secrets.token_hex(16)
            handshake = {"cmd": protocol.CMD_MESH_HANDSHAKE, "data": self._assinar_identidade(nonce)}
            sock.sendall(protocol.pack_message(handshake))
            resposta = protocol.unpack_message(sock)
            sock.settimeout(None)
        except (OSError, protocol.ProtocolError):
            return
        if resposta is None or resposta.get("cmd") != protocol.CMD_MESH_HANDSHAKE:
            try:
                sock.close()
            except OSError:
                pass
            return
        dados = resposta.get("data", {})
        if not self._verificar_identidade(dados):
            try:
                sock.close()
            except OSError:
                pass
            return
        peer_forums = set(dados.get("forums", []))
        if not (peer_forums & self._meus_foruns()):
            try:
                sock.close()
            except OSError:
                pass
            return
        self._registrar_conexao(sock, dados["user_id"], dados["username"], peer_forums)

    def _handshake_recebido(self, sock: socket.socket) -> None:
        try:
            sock.settimeout(_TIMEOUT_HANDSHAKE)
            recebido = protocol.unpack_message(sock)
        except (OSError, protocol.ProtocolError):
            try:
                sock.close()
            except OSError:
                pass
            return
        if recebido is None or recebido.get("cmd") != protocol.CMD_MESH_HANDSHAKE:
            try:
                sock.close()
            except OSError:
                pass
            return
        dados = recebido.get("data", {})
        if not self._verificar_identidade(dados):
            try:
                sock.close()
            except OSError:
                pass
            return
        peer_forums = set(dados.get("forums", []))
        overlap = peer_forums & self._meus_foruns()
        try:
            nonce = secrets.token_hex(16)
            resposta = {"cmd": protocol.CMD_MESH_HANDSHAKE, "data": self._assinar_identidade(nonce)}
            sock.sendall(protocol.pack_message(resposta))
            sock.settimeout(None)
        except OSError:
            try:
                sock.close()
            except OSError:
                pass
            return
        if not overlap:
            try:
                sock.close()
            except OSError:
                pass
            return
        self._registrar_conexao(sock, dados["user_id"], dados["username"], peer_forums)

    def _registrar_conexao(self, sock: socket.socket, peer_user_id: int, peer_username: str,
                            peer_forum_ids: set[int]) -> None:
        conn = _MeshConnection(
            sock, peer_user_id, peer_username, peer_forum_ids,
            on_message=self._on_message, on_closed=self._on_conexao_fechada,
        )
        with self._lock:
            antiga = self._conexoes.get(peer_user_id)
            self._conexoes[peer_user_id] = conn
        if antiga is not None:
            antiga.close()
        self._on_peers_changed(self.peer_count())

    def _on_conexao_fechada(self, conn: _MeshConnection) -> None:
        with self._lock:
            atual = self._conexoes.get(conn.peer_user_id)
            if atual is conn:
                del self._conexoes[conn.peer_user_id]
        self._on_peers_changed(self.peer_count())

    # --- estado -----------------------------------------------------------------

    def peer_count(self) -> int:
        with self._lock:
            return len(self._conexoes)

    # --- envio de mensagens de forum ---------------------------------------------

    def broadcast_to_forum(self, forum_id: int, payload: dict) -> None:
        """Envia `payload` (ja cifrado com a AES do forum) a todo peer
        conectado que tambem e membro de `forum_id`."""
        mensagem = {"cmd": protocol.CMD_MESH_MESSAGE, "data": {**payload, "forum_id": forum_id}}
        with self._lock:
            alvo = [c for c in self._conexoes.values() if forum_id in c.peer_forum_ids]
        for conn in alvo:
            conn.send(mensagem)
