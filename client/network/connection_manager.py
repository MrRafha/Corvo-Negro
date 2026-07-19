"""Orquestra a decisao ONLINE vs LAN e a transicao entre os dois modos
(Sprint 3, Dia 11-12).

No boot, tenta o servidor central; se falhar (ou cair depois, apos as
tentativas de reconexao do ClientBridge se esgotarem), ativa o modo LAN:
sobe LanAdvertiser + LanBrowser + MeshPeerManager, conecta automaticamente
em qualquer peer descoberto que compartilhe pelo menos 1 forum. Se ninguem
for encontrado em 15s, desiste (TelaHostAbatido) — nem servidor, nem
ninguem por perto na rede local.

Quando o servidor central volta e o ClientBridge reconecta com sucesso, para
o modo LAN e dispara o sync de historico (client.network.sync.iniciar_sync).
"""

from __future__ import annotations

from typing import Callable

from client import config
from client.network.gui_bridge import ClientBridge
from client.network.lan_discovery import LanAdvertiser, LanBrowser, PeerInfo
from client.network.mesh_peer import MeshPeerManager
from client.ui.app_state import AppState

_TIMEOUT_SEM_PEERS_MS = 15_000


class ConnectionManager:
    def __init__(self, bridge: ClientBridge, state: AppState, tk_root) -> None:
        self._bridge = bridge
        self._state = state
        self._tk_root = tk_root

        self._advertiser: LanAdvertiser | None = None
        self._browser: LanBrowser | None = None
        self._mesh: MeshPeerManager | None = None
        self._timeout_sem_peers_id = None

        self._on_peer_conectado: Callable[[int], None] = lambda n: None
        self._on_sem_peers_apos_timeout: Callable[[], None] = lambda: None
        self._on_mesh_message: Callable[[dict], None] = lambda m: None
        self._on_sync_concluido: Callable[[int], None] = lambda n: None

    # --- callbacks configuraveis (MainWindow injeta) -----------------------------

    def configurar_callbacks(
        self,
        on_peer_conectado: Callable[[int], None] | None = None,
        on_sem_peers_apos_timeout: Callable[[], None] | None = None,
        on_mesh_message: Callable[[dict], None] | None = None,
        on_sync_concluido: Callable[[int], None] | None = None,
    ) -> None:
        if on_peer_conectado is not None:
            self._on_peer_conectado = on_peer_conectado
        if on_sem_peers_apos_timeout is not None:
            self._on_sem_peers_apos_timeout = on_sem_peers_apos_timeout
        if on_mesh_message is not None:
            self._on_mesh_message = on_mesh_message
        if on_sync_concluido is not None:
            self._on_sync_concluido = on_sync_concluido

    # --- conexao inicial ----------------------------------------------------------

    def tentar_conexao_inicial(self, on_online: Callable[[], None], on_lan: Callable[[], None]) -> None:
        try:
            self._bridge.connect(timeout=config.CONNECT_TIMEOUT)
            self._bridge.start_polling()
            on_online()
        except OSError:
            on_lan()
            self.ativar_modo_lan()

    # --- modo LAN -------------------------------------------------------------------

    def ativar_modo_lan(self) -> None:
        if self._mesh is not None:
            return  # ja ativo
        self._state.modo_lan = True
        self._state.peers_lan = {}

        priv_pem = self._state.private_key_pem
        if priv_pem is None or self._state.user_id is None:
            return  # sem identidade ainda (nao deveria acontecer pos-login)

        from shared import crypto_utils
        public_key_pem = crypto_utils.public_key_from_private(priv_pem)

        self._mesh = MeshPeerManager(
            my_user_id=self._state.user_id,
            my_username=self._state.username or "",
            private_key_pem=priv_pem,
            public_key_pem=public_key_pem,
            meus_foruns=self._foruns_conhecidos,
            on_message=self._despachar_mensagem_mesh,
            on_peers_changed=self._on_peers_changed,
        )
        porta = self._mesh.start_listening()

        self._advertiser = LanAdvertiser(
            user_id=self._state.user_id, username=self._state.username or "",
            forum_ids=self._foruns_conhecidos, port=porta,
        )
        self._advertiser.start()

        self._browser = LanBrowser(
            meu_user_id=self._state.user_id,
            on_peer_encontrado=self._on_peer_descoberto,
            on_peer_perdido=lambda _nome: None,
        )
        self._browser.start()

        self._timeout_sem_peers_id = self._tk_root.after(_TIMEOUT_SEM_PEERS_MS, self._checar_sem_peers)

    def _foruns_conhecidos(self) -> set[int]:
        local_db = self._state.local_db
        if local_db is None:
            return set()
        return {f["forum_id"] for f in local_db.get_known_forums()}

    def _on_peer_descoberto(self, peer: PeerInfo) -> None:
        if self._mesh is not None:
            self._mesh.connect_to_peer(peer)

    def _on_peers_changed(self, n: int) -> None:
        # roda na thread de rede do mesh — reagenda na thread do Tk antes de
        # tocar em widgets/estado compartilhado com a UI.
        self._tk_root.after(0, lambda: self._aplicar_mudanca_peers(n))

    def _aplicar_mudanca_peers(self, n: int) -> None:
        if n > 0 and self._timeout_sem_peers_id is not None:
            try:
                self._tk_root.after_cancel(self._timeout_sem_peers_id)
            except Exception:
                pass
            self._timeout_sem_peers_id = None
        self._on_peer_conectado(n)

    def _despachar_mensagem_mesh(self, message: dict) -> None:
        if message.get("cmd") != "MESH_MESSAGE":
            return
        self._tk_root.after(0, lambda: self._on_mesh_message(message.get("data", {})))

    def _checar_sem_peers(self) -> None:
        self._timeout_sem_peers_id = None
        if self._mesh is not None and self._mesh.peer_count() == 0:
            self._on_sem_peers_apos_timeout()

    def obter_mesh_manager(self) -> MeshPeerManager | None:
        return self._mesh

    # --- transicao de volta pro online ------------------------------------------

    def parar_modo_lan_e_sincronizar(self) -> None:
        if self._mesh is None:
            return  # nao estava em modo LAN, nada a fazer
        if self._timeout_sem_peers_id is not None:
            try:
                self._tk_root.after_cancel(self._timeout_sem_peers_id)
            except Exception:
                pass
            self._timeout_sem_peers_id = None
        if self._advertiser is not None:
            self._advertiser.stop()
            self._advertiser = None
        if self._browser is not None:
            self._browser.stop()
            self._browser = None
        if self._mesh is not None:
            self._mesh.stop()
            self._mesh = None
        self._state.modo_lan = False
        self._state.peers_lan = {}

        local_db = self._state.local_db
        if local_db is not None:
            from client.network import sync
            sync.iniciar_sync(
                self._bridge, local_db, self._state,
                on_concluido=self._on_sync_concluido, on_erro=lambda _msg: None,
            )
