"""Sidebar de foruns a esquerda (reconstrucao a partir de Janela Principal.dc.html).

Cabecalho com 🜲 "CORVO NEGRO" + lema, botoes "＋ Fundar Fórum" (outline dourado)
e "❖ Aceitar Convocação" (outline muted), divisor ornamental, secao "⚜ FÓRUNS" e
a lista real dos foruns do usuario (CMD_LIST_MY_FORUMS). Fórum ativo: fundo
BG_MEDIO + borda esquerda dourada de 2px. Hover: leve crimson.

So o layout foi reescrito; a fiacao de rede (recarregar/selecionar) e a mesma.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from shared import protocol
from client.network.gui_bridge import ClientBridge
from client.ui import theme
from client.ui.app_state import AppState
from client.ui.create_forum_modal import CreateForumModal
from client.ui.join_forum_modal import JoinForumModal

OnSelecionarForum = Callable[..., None]

_GLIFOS_FORUM = ["⚔", "🜲", "☿", "⚜", "🜍", "☉", "☽", "✠"]


class ForumSidebar(ctk.CTkFrame):
    def __init__(self, master, bridge: ClientBridge, state: AppState, on_selecionar_forum: OnSelecionarForum,
                 on_contagem=None) -> None:
        super().__init__(master, width=224, fg_color=theme.Cores.BG_PAINEL, corner_radius=0)
        self.pack_propagate(False)
        self.grid_propagate(False)
        self._bridge = bridge
        self._state = state
        self._on_selecionar_forum = on_selecionar_forum
        self._on_contagem = on_contagem or (lambda _n: None)
        self._forum_id_selecionado: int | None = None
        self._itens: dict[int, dict] = {}
        self._nomes: dict[int, str] = {}

        self._montar_cabecalho()
        self._montar_botoes_acao()
        self._montar_divisor()

        ctk.CTkLabel(self, text="⚜ FÓRUNS", font=theme.FONTES["label"], text_color=theme.Cores.DOURADO).pack(
            anchor="w", padx=14, pady=(4, 6))

        self._lista = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self._lista.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        self._vazio = None
        self._bridge.on(protocol.EVT_MEMBER_JOINED, lambda _data: self.recarregar())
        self._bridge.on(protocol.EVT_MEMBER_LEFT, lambda _data: self.recarregar())
        self.recarregar()

    def _montar_cabecalho(self) -> None:
        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.pack(fill="x", padx=14, pady=(16, 14))
        ctk.CTkLabel(cab, text="🜲", font=theme.glifo(22), text_color=theme.Cores.DOURADO).pack()
        ctk.CTkLabel(cab, text="C O R V O   N E G R O", font=(theme.FAMILIA_SERIFADA, 15, "bold"),
                     text_color=theme.Cores.DOURADO).pack(pady=(1, 0))
        ctk.CTkLabel(cab, text="silentium in aeternum", font=(theme.FAMILIA_SERIFADA, 9, "italic"),
                     text_color=theme.Cores.MUTED).pack()
        sep = ctk.CTkFrame(self, height=1, fg_color=theme.DOURADO_18, corner_radius=0)
        sep.pack(fill="x")

    def _montar_botoes_acao(self) -> None:
        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack(fill="x", padx=12, pady=(14, 8))
        ctk.CTkButton(
            botoes, text="＋ Fundar Fórum", font=theme.FONTES["corpo_pequeno"], corner_radius=0, height=34,
            fg_color="transparent", border_width=1, border_color=theme.DOURADO_45,
            text_color=theme.Cores.DOURADO, hover_color=theme.Cores.BG_MEDIO,
            command=self._abrir_criar_forum,
        ).pack(fill="x", pady=(0, 8))
        ctk.CTkButton(
            botoes, text="❖ Aceitar Convocação", font=theme.FONTES["corpo_pequeno"], corner_radius=0, height=34,
            fg_color="transparent", border_width=1, border_color=theme.mix(theme.Cores.MUTED, theme.Cores.BG_PAINEL, 0.4),
            text_color=theme.Cores.MUTED, hover_color=theme.Cores.BG_MEDIO,
            command=self._abrir_entrar_forum,
        ).pack(fill="x")

    def _montar_divisor(self) -> None:
        div = ctk.CTkFrame(self, fg_color="transparent")
        div.pack(fill="x", padx=16, pady=(4, 10))
        ctk.CTkFrame(div, height=1, fg_color=theme.DOURADO_30, corner_radius=0).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkLabel(div, text="✦", font=theme.glifo(8), text_color=theme.Cores.MUTED).pack(side="left")
        ctk.CTkFrame(div, height=1, fg_color=theme.DOURADO_30, corner_radius=0).pack(side="left", fill="x", expand=True, padx=(8, 0))

    def _abrir_criar_forum(self) -> None:
        CreateForumModal(
            self.winfo_toplevel(), self._bridge, self._state,
            on_criado=lambda data: (self.recarregar(), self.after(120, lambda: self.selecionar(data["forum_id"]))),
        )

    def _abrir_entrar_forum(self) -> None:
        JoinForumModal(
            self.winfo_toplevel(), self._bridge,
            on_entrou=lambda data: (self.recarregar(), self.after(120, lambda: self.selecionar(data["forum_id"]))),
        )

    def recarregar(self) -> None:
        self._bridge.call(protocol.CMD_LIST_MY_FORUMS, {}, on_ok=self._popular)

    def _popular(self, data: dict) -> None:
        for widget in self._lista.winfo_children():
            widget.destroy()
        self._itens.clear()
        self._nomes.clear()

        forums = data.get("forums", [])
        self._on_contagem(len(forums))
        if not forums:
            self._mostrar_vazio()
            return

        for i, forum in enumerate(forums):
            self._state.note_ownership(forum["forum_id"], forum.get("owner_id"))
            self._nomes[forum["forum_id"]] = forum["name"]
            item = self._criar_item_forum(forum["forum_id"], forum["name"], _GLIFOS_FORUM[i % len(_GLIFOS_FORUM)])
            item["frame"].pack(fill="x", pady=2)
            self._itens[forum["forum_id"]] = item

        if self._forum_id_selecionado in self._itens:
            self._destacar_selecionado()

    def _mostrar_vazio(self) -> None:
        vazio = ctk.CTkLabel(
            self._lista, text="Nenhum fórum reclama\ntua presença.",
            font=(theme.FAMILIA_SERIFADA, 14, "italic"), text_color=theme.Cores.MUTED, justify="center",
        )
        vazio.pack(pady=20)

    def _criar_item_forum(self, forum_id: int, nome: str, glifo: str) -> dict:
        frame = ctk.CTkFrame(self._lista, height=1, fg_color="transparent", corner_radius=0)
        borda = ctk.CTkFrame(frame, width=2, height=1, fg_color="transparent", corner_radius=0)
        borda.pack(side="left", fill="y")
        conteudo = ctk.CTkFrame(frame, fg_color="transparent")
        conteudo.pack(side="left", fill="x", expand=True, padx=(8, 8), pady=8)

        top = ctk.CTkFrame(conteudo, fg_color="transparent")
        top.pack(fill="x")
        lbl_glifo = ctk.CTkLabel(top, text=glifo, font=theme.glifo(12), text_color=theme.Cores.MUTED)
        lbl_glifo.pack(side="left", padx=(0, 7))
        lbl_nome = ctk.CTkLabel(top, text=nome, font=(theme.FAMILIA_SERIFADA, 15, "bold"),
                                text_color=theme.Cores.ROLE_BEGE, anchor="w")
        lbl_nome.pack(side="left", fill="x", expand=True)
        lbl_hora = ctk.CTkLabel(conteudo, text="agora", font=theme.FONTES["label"], text_color=theme.Cores.MUTED, anchor="w")
        lbl_hora.pack(fill="x", anchor="w")

        item = {"frame": frame, "borda": borda, "glifo": lbl_glifo, "nome": lbl_nome}
        for w in (frame, conteudo, top, lbl_glifo, lbl_nome, lbl_hora, borda):
            w.bind("<Button-1>", lambda e, fid=forum_id: self.selecionar(fid))
        return item

    def selecionar(self, forum_id: int) -> None:
        self._forum_id_selecionado = forum_id
        self._destacar_selecionado()
        nome = self._nomes.get(forum_id, "")
        try:
            self._on_selecionar_forum(forum_id, nome)
        except TypeError:
            self._on_selecionar_forum(forum_id)

    def _destacar_selecionado(self) -> None:
        for fid, item in self._itens.items():
            ativo = fid == self._forum_id_selecionado
            item["frame"].configure(fg_color=theme.Cores.BG_MEDIO if ativo else "transparent")
            item["borda"].configure(fg_color=theme.Cores.DOURADO if ativo else "transparent")
            item["glifo"].configure(text_color=theme.Cores.DOURADO if ativo else theme.Cores.MUTED)
            item["nome"].configure(text_color=theme.Cores.TEXTO if ativo else theme.Cores.ROLE_BEGE)
