"""Sidebar de membros a direita (reconstrucao a partir de Janela Principal.dc.html).

Lista os membros do forum atual agrupados por role (CMD_GET_FORUM_MEMBERS),
cada grupo com cabecalho na cor da role + linha inferior, e cada membro com uma
bolinha QUADRADA de status (verde online / cinza offline) e o nome na cor da
role. Roles ordenadas por priority (maior primeiro).

So o layout foi reescrito; a fiacao de rede e a mesma.
"""

from __future__ import annotations

import customtkinter as ctk

from shared import protocol
from client.network.gui_bridge import ClientBridge
from client.ui import theme
from client.ui.ui_helpers import PontoStatus


class MembersSidebar(ctk.CTkFrame):
    def __init__(self, master, bridge: ClientBridge) -> None:
        super().__init__(master, width=204, fg_color=theme.Cores.BG_PAINEL, corner_radius=0)
        self.pack_propagate(False)
        self.grid_propagate(False)
        self._bridge = bridge
        self._forum_id: int | None = None

        self._label_titulo = ctk.CTkLabel(self, text="⚔ MEMBROS", font=theme.FONTES["label"], text_color=theme.Cores.DOURADO)
        self._label_titulo.pack(anchor="w", padx=14, pady=(14, 8))

        self._lista = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self._lista.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        self._bridge.on(protocol.EVT_MEMBER_JOINED, lambda _data: self._recarregar())
        self._bridge.on(protocol.EVT_MEMBER_LEFT, lambda _data: self._recarregar())
        self._bridge.on(protocol.EVT_ROLE_UPDATED, self._on_role_alterada)
        self._bridge.on(protocol.EVT_ROLE_DELETED, self._on_role_alterada)

    def _on_role_alterada(self, data: dict) -> None:
        if data.get("forum_id") == self._forum_id:
            self._recarregar()

    def carregar_forum(self, forum_id: int) -> None:
        self._forum_id = forum_id
        self._recarregar()

    def _recarregar(self) -> None:
        if self._forum_id is None:
            return
        self._bridge.call(protocol.CMD_GET_FORUM_MEMBERS, {"forum_id": self._forum_id}, on_ok=self._popular)

    def _popular(self, data: dict) -> None:
        for widget in self._lista.winfo_children():
            widget.destroy()

        membros = data.get("members", [])
        self._label_titulo.configure(text=f"⚔ MEMBROS — {len(membros)}")

        grupos: dict[str, list[dict]] = {}
        cores_por_role: dict[str, str] = {}
        prioridades: dict[str, int] = {}
        for membro in membros:
            roles = membro.get("roles") or [{"name": "Sem Ordem", "color": theme.Cores.MUTED, "priority": -1}]
            principal = max(roles, key=lambda r: r["priority"])
            nome_role = principal["name"]
            grupos.setdefault(nome_role, []).append(membro)
            cores_por_role[nome_role] = principal["color"]
            prioridades[nome_role] = principal["priority"]

        for nome_role in sorted(grupos, key=lambda r: -prioridades[r]):
            cor = cores_por_role[nome_role]
            membros_grupo = grupos[nome_role]

            grupo = ctk.CTkFrame(self._lista, fg_color="transparent")
            grupo.pack(fill="x", padx=8, pady=(10, 0))
            cabecalho = ctk.CTkLabel(grupo, text=f"{nome_role.upper()} — {len(membros_grupo)}",
                                     font=theme.FONTES["label"], text_color=cor, anchor="w")
            cabecalho.pack(fill="x")
            ctk.CTkFrame(grupo, height=1, fg_color=theme.mix(cor, theme.Cores.BG_PAINEL, 0.2), corner_radius=0).pack(fill="x", pady=(4, 4))

            for membro in membros_grupo:
                online = membro.get("online", True)
                linha = ctk.CTkFrame(grupo, fg_color="transparent")
                linha.pack(fill="x", pady=2)
                PontoStatus(linha, cor=theme.Cores.SUCESSO if online else theme.MEMBRO_OFFLINE).pack(side="left", padx=(2, 8))
                ctk.CTkLabel(linha, text=membro["username"], font=theme.FONTES["corpo_pequeno"],
                             text_color=cor if online else theme.MEMBRO_OFFLINE_TXT, anchor="w").pack(side="left", fill="x", expand=True)
