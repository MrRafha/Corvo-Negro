"""Descoberta LAN via zeroconf/mDNS (Sprint 3, Dia 11).

LanAdvertiser: registra o servico _corvonegro._tcp.local. com props
{user_id, username, forums (json)}. LanBrowser: escuta anuncios e notifica
quando peers aparecem/somem, ignorando o proprio anuncio.

O nome do servico e unico por instancia (username + sufixo aleatorio) para
permitir varios clientes na mesma maquina (ex.: testes/demo) sem colidir.
"""

from __future__ import annotations

import json
import socket
import threading
import uuid as uuid_mod
from dataclasses import dataclass
from typing import Callable

from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf

SERVICE_TYPE = "_corvonegro._tcp.local."


@dataclass
class PeerInfo:
    user_id: int
    username: str
    forum_ids: set[int]
    host: str
    port: int


def _local_ip() -> str:
    """Descobre o IP local usado para sair na rede (sem depender de config manual).

    Nao envia dados de verdade: connect() em UDP so resolve a rota/interface.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


class LanAdvertiser:
    """Anuncia este cliente na rede local via mDNS."""

    def __init__(self, user_id: int, username: str, forum_ids: Callable[[], set[int]], port: int) -> None:
        self._user_id = user_id
        self._username = username
        self._forum_ids = forum_ids
        self._port = port
        self._zeroconf: Zeroconf | None = None
        self._info: ServiceInfo | None = None
        self._nome_servico = f"corvo-{username}-{uuid_mod.uuid4().hex[:6]}.{SERVICE_TYPE}"

    def _montar_info(self) -> ServiceInfo:
        props = {
            "user_id": str(self._user_id).encode("utf-8"),
            "username": self._username.encode("utf-8"),
            "forums": json.dumps(sorted(self._forum_ids())).encode("utf-8"),
        }
        return ServiceInfo(
            SERVICE_TYPE,
            self._nome_servico,
            addresses=[socket.inet_aton(_local_ip())],
            port=self._port,
            properties=props,
        )

    def start(self) -> None:
        self._zeroconf = Zeroconf()
        self._info = self._montar_info()
        self._zeroconf.register_service(self._info)

    def atualizar_foruns(self) -> None:
        """Re-registra o servico com a lista de foruns atual (ex.: apos entrar/sair)."""
        if self._zeroconf is None:
            return
        novo_info = self._montar_info()
        self._zeroconf.update_service(novo_info)
        self._info = novo_info

    def stop(self) -> None:
        if self._zeroconf is not None and self._info is not None:
            try:
                self._zeroconf.unregister_service(self._info)
            except Exception:
                pass
        if self._zeroconf is not None:
            try:
                self._zeroconf.close()
            except Exception:
                pass
        self._zeroconf = None
        self._info = None


class _Listener(ServiceListener):
    def __init__(self, browser: "LanBrowser") -> None:
        self._browser = browser

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info is None:
            return
        self._browser._processar_info(name, info)

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info is None:
            return
        self._browser._processar_info(name, info)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self._browser._processar_remocao(name)


class LanBrowser:
    """Escuta anuncios mDNS de outros clientes Corvo Negro na rede local."""

    def __init__(
        self,
        meu_user_id: int,
        on_peer_encontrado: Callable[[PeerInfo], None],
        on_peer_perdido: Callable[[str], None],
    ) -> None:
        self._meu_user_id = meu_user_id
        self._on_peer_encontrado = on_peer_encontrado
        self._on_peer_perdido = on_peer_perdido
        self._zeroconf: Zeroconf | None = None
        self._browser: ServiceBrowser | None = None
        self._lock = threading.Lock()
        self._nomes_conhecidos: dict[str, int] = {}  # nome mDNS -> user_id

    def start(self) -> None:
        self._zeroconf = Zeroconf()
        self._browser = ServiceBrowser(self._zeroconf, SERVICE_TYPE, _Listener(self))

    def _processar_info(self, nome: str, info: ServiceInfo) -> None:
        props = info.properties or {}
        try:
            user_id = int(props.get(b"user_id", b"-1").decode("utf-8"))
            username = props.get(b"username", b"").decode("utf-8")
            forum_ids = set(json.loads(props.get(b"forums", b"[]").decode("utf-8")))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return
        if user_id == self._meu_user_id:
            return  # ignora o proprio anuncio
        if not info.addresses:
            return
        host = socket.inet_ntoa(info.addresses[0])
        peer = PeerInfo(user_id=user_id, username=username, forum_ids=forum_ids, host=host, port=info.port)
        with self._lock:
            self._nomes_conhecidos[nome] = user_id
        self._on_peer_encontrado(peer)

    def _processar_remocao(self, nome: str) -> None:
        with self._lock:
            self._nomes_conhecidos.pop(nome, None)
        self._on_peer_perdido(nome)

    def stop(self) -> None:
        if self._zeroconf is not None:
            try:
                self._zeroconf.close()
            except Exception:
                pass
        self._zeroconf = None
        self._browser = None
