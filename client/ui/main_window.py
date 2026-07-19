"""Janela principal (reconstrucao visual a partir de Janela Principal.dc.html).

Grid de 3 linhas: header (52px, colspan) / corpo (sidebars+chat) / status bar
(30px). O corpo e um grid de 3 colunas: 224px (foruns) | flex (chat) | 204px
(membros). Header mostra o nome do forum ativo + badge de conexao
(ONLINE/CONECTANDO/LAN) com bolinha quadrada.

Preserva integralmente a logica de distribuicao/rotacao de chave de forum
(EVT_MEMBER_JOINED/LEFT/KEY_ROTATED) — so o layout foi reescrito.
"""

from __future__ import annotations

import base64

import customtkinter as ctk

from shared import crypto_utils, protocol
from client.network.connection_manager import ConnectionManager
from client.network.gui_bridge import ClientBridge
from client.ui import theme
from client.ui.chat_view import ChatView
from client.ui.app_state import AppState
from client.ui.forum_sidebar import ForumSidebar
from client.ui.forum_settings_modal import ForumSettingsModal
from client.ui.members_sidebar import MembersSidebar
from client.ui.status_bar import StatusBar
from client.ui.ui_helpers import PontoStatus, montar_janela_sem_moldura, parar_pulso, pulsar_fg

_BADGE = {
    "online": (theme.Cores.SUCESSO, "ONLINE"),
    "conectando": (theme.Cores.AVISO, "CONECTANDO"),
    "lan": (theme.Cores.ERRO, "LAN · 0 CORVOS"),
}


class MainWindow(ctk.CTkToplevel):
    def __init__(self, master, bridge: ClientBridge, state: AppState) -> None:
        super().__init__(master)
        self._bridge = bridge
        self._state = state
        self._nome_forum_atual = ""
        self._reconectando = False
        self._connection_manager = ConnectionManager(bridge, state, self)
        self._connection_manager.configurar_callbacks(
            on_peer_conectado=self._on_peers_lan_changed,
            on_sem_peers_apos_timeout=self._on_lan_sem_peers_timeout,
            on_mesh_message=lambda data: self._chat_view.on_mesh_message(data),
            on_sync_concluido=self._on_sync_concluido,
        )

        theme.carregar_fontes()
        self.title("Corvo Negro — Cripta do Silêncio")
        self.geometry("1180x760")
        self.minsize(1000, 620)
        self.configure(fg_color=theme.Cores.BG_PROFUNDO)

        # linha 0 = barra de titulo customizada, 1 = header do forum, 2 = corpo
        # (sidebars+chat), 3 = status bar.
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        montar_janela_sem_moldura(self, "🜲 CORVO NEGRO", on_fechar=self._fechar, row=0)
        self._montar_header()
        self._montar_corpo()

        self._status_bar = StatusBar(self, username=state.username or "?")
        self._status_bar.grid(row=3, column=0, sticky="ew")

        self._bridge.on(protocol.EVT_KEY_ROTATED, self._on_key_rotated)
        self._bridge.on(protocol.EVT_KEY_REQUESTED, self._on_key_requested)
        self._bridge.on(protocol.EVT_MEMBER_JOINED, self._on_member_joined)
        self._bridge.on(protocol.EVT_MEMBER_LEFT, self._on_member_left)
        self._bridge.on(protocol.EVT_FORUM_UPDATED, self._on_forum_updated)
        self._bridge.on(protocol.EVT_FORUM_DELETED, self._on_forum_deleted)
        self._bridge.on(protocol.EVT_MEMBER_KICKED, self._on_removido_do_forum)
        self._bridge.on(protocol.EVT_MEMBER_BANNED, self._on_removido_do_forum)
        self._bridge.on("_DISCONNECTED", self._on_desconectado)

        if state.modo_lan:
            # login offline (LoginWindow._tentar_login_offline): nasce direto
            # em modo LAN, sem passar pelo ciclo normal de reconexao (o bridge
            # nem chegou a se conectar de verdade — nao ha sessao online a
            # perder aqui).
            self.after(50, self._on_reconexao_falhou)

    # --- layout -------------------------------------------------------------------

    def _fechar(self) -> None:
        try:
            self._bridge.close()
        except Exception:
            pass
        self.destroy()
        try:
            self.master.destroy()
        except Exception:
            pass

    def _montar_header(self) -> None:
        header = ctk.CTkFrame(self, height=52, fg_color=theme.Cores.BG_PAINEL, corner_radius=0)
        header.grid(row=1, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(0, weight=1)

        esquerda = ctk.CTkFrame(header, fg_color="transparent")
        esquerda.grid(row=0, column=0, sticky="w", padx=18)
        self._label_glifo_forum = ctk.CTkLabel(esquerda, text="⚔", font=theme.glifo(17), text_color=theme.Cores.DOURADO)
        self._label_glifo_forum.pack(side="left", padx=(0, 9))
        self._label_forum = ctk.CTkLabel(
            esquerda, text="Selecione um fórum", font=theme.FONTES["titulo_forum"], text_color=theme.Cores.DOURADO
        )
        self._label_forum.pack(side="left")
        self._label_lema = ctk.CTkLabel(
            esquerda, text="  onde os segredos dormem sob sete selos",
            font=(theme.FAMILIA_SERIFADA, 12, "italic"), text_color=theme.Cores.MUTED,
        )
        self._label_lema.pack(side="left", padx=(6, 0))

        direita = ctk.CTkFrame(header, fg_color="transparent")
        direita.grid(row=0, column=1, sticky="e", padx=18)

        self._direita_header = direita
        self._badge = ctk.CTkFrame(
            direita, fg_color=theme.mix(theme.Cores.SUCESSO, theme.Cores.BG_PAINEL, 0.08),
            border_width=1, border_color=theme.mix(theme.Cores.SUCESSO, theme.Cores.BG_PAINEL, 0.45), corner_radius=0,
        )
        self._badge_dot = PontoStatus(self._badge, theme.Cores.SUCESSO)
        self._badge_dot.pack(side="left", padx=(12, 7), pady=6)
        self._badge_label = ctk.CTkLabel(self._badge, text="ONLINE", font=theme.FONTES["label"], text_color=theme.Cores.SUCESSO)
        self._badge_label.pack(side="left", padx=(0, 12))

        self._botao_config_header = ctk.CTkButton(
            direita, text="⚙", width=30, height=28, font=theme.glifo(14),
            fg_color="transparent", text_color=theme.Cores.MUTED, corner_radius=0,
            hover_color=theme.Cores.BG_MEDIO, command=self._abrir_configuracoes_forum,
        )

    def _montar_corpo(self) -> None:
        corpo = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        corpo.grid(row=2, column=0, sticky="nsew")
        corpo.grid_rowconfigure(0, weight=1)
        corpo.grid_columnconfigure(1, weight=1)

        self._forum_sidebar = ForumSidebar(
            corpo, self._bridge, self._state, on_selecionar_forum=self._selecionar_forum,
            on_contagem=self._atualizar_contagem_foruns,
        )
        self._forum_sidebar.grid(row=0, column=0, sticky="nsew")

        self._chat_view = ChatView(corpo, self._bridge, self._state, on_forum_nome=self._set_nome_forum)
        self._chat_view.grid(row=0, column=1, sticky="nsew")

        self._members_sidebar = MembersSidebar(corpo, self._bridge)
        self._members_sidebar.grid(row=0, column=2, sticky="nsew")
        self._atualizar_visibilidade_header_forum()

    # --- estado visual --------------------------------------------------------------

    def set_conexao(self, modo: str, peers: int | None = None) -> None:
        cor, texto = _BADGE.get(modo, (theme.Cores.MUTED, modo.upper()))
        if modo == "lan" and peers is not None:
            texto = f"LAN · {peers} CORVOS"
        self._badge.configure(
            fg_color=theme.mix(cor, theme.Cores.BG_PAINEL, 0.08),
            border_color=theme.mix(cor, theme.Cores.BG_PAINEL, 0.45),
        )
        self._badge_dot.configure(fg_color=cor)
        self._badge_label.configure(text=texto, text_color=cor)
        parar_pulso(self._badge_dot)
        if modo == "conectando":
            pulsar_fg(self._badge_dot, cor, theme.mix(cor, theme.Cores.BG_PAINEL, 0.2), periodo_ms=800)
        self._status_bar.set_modo(modo, peers)

    def _atualizar_contagem_foruns(self, n: int) -> None:
        if hasattr(self, "_status_bar"):
            self._status_bar.set_foruns(n)

    def _set_nome_forum(self, nome: str, glifo: str = "⚔") -> None:
        self._nome_forum_atual = nome
        self._glifo_forum_atual = glifo
        self._label_forum.configure(text=nome or "Selecione um fórum")
        self._label_glifo_forum.configure(text=glifo)

    def _atualizar_visibilidade_header_forum(self) -> None:
        """Esconde o badge de conexao, o botao de configuracoes e a sidebar
        de membros quando nenhum forum esta selecionado — todos so fazem
        sentido com um forum ativo."""
        tem_forum = self._state.current_forum_id is not None
        if tem_forum:
            self._badge.pack(side="left", padx=(0, 14))
            self._botao_config_header.pack(side="left", padx=1)
            self._members_sidebar.grid(row=0, column=2, sticky="nsew")
        else:
            self._badge.pack_forget()
            self._botao_config_header.pack_forget()
            self._members_sidebar.grid_forget()

    # --- selecao de forum ------------------------------------------------------------

    def _selecionar_forum(self, forum_id: int, nome: str = "") -> None:
        if nome:
            self._set_nome_forum(nome)
        self._chat_view.carregar_forum(forum_id)
        self._members_sidebar.carregar_forum(forum_id)
        self._atualizar_visibilidade_header_forum()

    def _abrir_configuracoes_forum(self) -> None:
        forum_id = self._state.current_forum_id
        if forum_id is None:
            return
        ForumSettingsModal(
            self, self._bridge, self._state, forum_id,
            nome_atual=self._nome_forum_atual, icone_atual=getattr(self, "_glifo_forum_atual", "⚔"),
            on_forum_atualizado=self._on_forum_atualizado_localmente,
            on_forum_deletado=lambda: self._forum_sidebar.recarregar(),
        )

    def _on_forum_atualizado_localmente(self, nome: str, icone: str) -> None:
        self._set_nome_forum(nome, icone)
        self._forum_sidebar.recarregar()

    def _on_forum_updated(self, data: dict) -> None:
        if data.get("forum_id") == self._state.current_forum_id:
            self._set_nome_forum(data.get("name", self._nome_forum_atual), data.get("icon", "⚔"))
        self._forum_sidebar.recarregar()

    def _on_forum_deleted(self, data: dict) -> None:
        self._forum_sidebar.recarregar()
        if data.get("forum_id") == self._state.current_forum_id:
            self._state.current_forum_id = None
            self._set_nome_forum("")
            self._chat_view.limpar()
            self._atualizar_visibilidade_header_forum()

    def _on_removido_do_forum(self, data: dict) -> None:
        if data.get("username") != self._state.username:
            return
        self._forum_sidebar.recarregar()
        if data.get("forum_id") == self._state.current_forum_id:
            self._state.current_forum_id = None
            self._set_nome_forum("")
            self._chat_view.limpar()
            self._atualizar_visibilidade_header_forum()

    def _on_desconectado(self, _data: dict) -> None:
        if self._reconectando:
            return  # sentinela redundante da thread de recv antiga (mesma queda)
        self._reconectando = True
        from client.ui.estados import ToastReconexao
        self.set_conexao("conectando")
        ToastReconexao.exibir(self, "Conexão perdida — tentando reconectar...", modo="aviso")
        self._bridge.tentar_reconectar(
            on_tentativa=self._on_tentativa_reconexao,
            on_sucesso=self._on_reconectado,
            on_falha_final=self._on_reconexao_falhou,
        )

    def _on_tentativa_reconexao(self, numero: int, total: int) -> None:
        from client.ui.estados import ToastReconexao
        ToastReconexao.exibir(self, f"Reconectando ao astropata... (tentativa {numero}/{total})", modo="aviso")

    def _on_reconectado(self) -> None:
        from client.ui.estados import ToastReconexao
        self._reconectando = False
        self.set_conexao("online")
        ToastReconexao.exibir(self, "Pacto restabelecido.", modo="sucesso")
        self._connection_manager.parar_modo_lan_e_sincronizar()

    def _on_reconexao_falhou(self) -> None:
        # nao esgota mais em TelaHostAbatido direto: tenta modo LAN primeiro.
        # TelaHostAbatido so aparece se ninguem for encontrado na rede local
        # dentro do timeout (ver ConnectionManager._checar_sem_peers).
        self.set_conexao("lan", peers=0)
        self._connection_manager.ativar_modo_lan()
        self._chat_view.definir_mesh_manager(self._connection_manager.obter_mesh_manager())
        self._atualizar_estado_lan_sem_peers()

    def _on_peers_lan_changed(self, n: int) -> None:
        self.set_conexao("lan", peers=n)
        self._chat_view.atualizar_lan_sem_peers(self._state.modo_lan and n == 0)

    def _atualizar_estado_lan_sem_peers(self) -> None:
        mesh = self._connection_manager.obter_mesh_manager()
        n = mesh.peer_count() if mesh is not None else 0
        self._chat_view.atualizar_lan_sem_peers(self._state.modo_lan and n == 0)

    def _on_lan_sem_peers_timeout(self) -> None:
        from client.ui.estados import TelaHostAbatido
        TelaHostAbatido(self, on_encerrar=self._fechar)

    def _on_sync_concluido(self, n_mensagens: int) -> None:
        if n_mensagens > 0:
            self._chat_view.mostrar_banner_sync(n_mensagens)
        self._chat_view.definir_mesh_manager(None)

    # --- distribuicao/rotacao de chave (identica a versao validada) ------------------

    def _on_key_rotated(self, data: dict) -> None:
        priv_pem = self._state.private_key_pem
        if priv_pem is None:
            return
        try:
            encrypted_aes_key = base64.b64decode(data["encrypted_aes_key"])
            aes_key = crypto_utils.rsa_decrypt(encrypted_aes_key, priv_pem)
            self._state.forum_keys[(data["forum_id"], data["key_version"])] = aes_key
        except Exception:
            pass

    def _on_member_joined(self, data: dict) -> None:
        forum_id = data["forum_id"]
        self._state.note_ownership(forum_id, data.get("owner_id"))
        if forum_id not in self._state.owned_forums:
            return
        key_version = self._state.current_key_version(forum_id)
        aes_key = self._state.forum_keys.get((forum_id, key_version))
        if aes_key is None:
            return
        self._distribuir_chave_para(forum_id, data["username"], aes_key, key_version)

    def _on_key_requested(self, data: dict) -> None:
        """Um membro pediu a chave do forum porque nao a recebeu a tempo
        (ex.: entrou enquanto eu, dono, estava offline). So o dono recebe
        este evento (ver handle_request_forum_key no servidor)."""
        forum_id = data["forum_id"]
        key_version = self._state.current_key_version(forum_id)
        aes_key = self._state.forum_keys.get((forum_id, key_version))
        if aes_key is None:
            return
        self._distribuir_chave_para(forum_id, data["username"], aes_key, key_version)

    def _on_member_left(self, data: dict) -> None:
        forum_id = data["forum_id"]
        self._state.note_ownership(forum_id, data.get("owner_id"))
        if forum_id not in self._state.owned_forums:
            return
        new_version = self._state.current_key_version(forum_id) + 1
        aes_key = crypto_utils.generate_aes_key()
        self._state.forum_keys[(forum_id, new_version)] = aes_key
        for membro in data.get("remaining_members", []):
            if membro == self._state.username:
                continue
            self._distribuir_chave_para(forum_id, membro, aes_key, new_version)

    def _distribuir_chave_para(self, forum_id: int, destinatario: str, aes_key: bytes, key_version: int) -> None:
        self._bridge.call(
            protocol.CMD_GET_PUBKEY, {"username": destinatario},
            on_ok=lambda pubkey_data: self._enviar_distribute_key(forum_id, destinatario, aes_key, key_version, pubkey_data),
        )

    def _enviar_distribute_key(self, forum_id: int, destinatario: str, aes_key: bytes, key_version: int, pubkey_data: dict) -> None:
        pub_pem = pubkey_data["public_key"].encode("utf-8")
        encrypted_aes_key = crypto_utils.rsa_encrypt(aes_key, pub_pem)
        self._bridge.call(
            protocol.CMD_DISTRIBUTE_KEY,
            {
                "forum_id": forum_id,
                "recipient": destinatario,
                "encrypted_aes_key": base64.b64encode(encrypted_aes_key).decode("ascii"),
                "key_version": key_version,
            },
        )
