"""Barra de status inferior (reconstrucao a partir de Janela Principal.dc.html).

Esquerda: 🜲 usuario · role. Centro: modo ONLINE · N FÓRUNS (ou CONECTANDO /
LAN). Direita: botoes ⚙ ✦ ⏻. Altura fixa de 30px.

Modo LAN/mesh e Sprint 3; por ora o indicador reflete ONLINE (conectado ao
servidor) ou CONECTANDO.
"""

from __future__ import annotations

import customtkinter as ctk

from client.ui import theme

_CORES_MODO = {
    "online": theme.Cores.SUCESSO,
    "conectando": theme.Cores.AVISO,
    "lan": theme.Cores.ERRO,
}
_LABELS_MODO = {
    "online": "ONLINE",
    "conectando": "CONECTANDO · TENTATIVA 2/3",
    "lan": "LAN",
}


class StatusBar(ctk.CTkFrame):
    def __init__(self, master, username: str, role_label: str = "Corvo-Mor") -> None:
        super().__init__(master, height=30, fg_color=theme.Cores.BG_PROFUNDO, border_width=0, corner_radius=0)
        self.pack_propagate(False)
        self.grid_propagate(False)
        self._topo = ctk.CTkFrame(self, height=1, fg_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_PROFUNDO, 0.16), corner_radius=0)
        self._topo.pack(fill="x", side="top")

        conteudo = ctk.CTkFrame(self, fg_color="transparent")
        conteudo.pack(fill="both", expand=True)
        conteudo.grid_columnconfigure(1, weight=1)

        esquerda = ctk.CTkFrame(conteudo, fg_color="transparent")
        esquerda.grid(row=0, column=0, sticky="w", padx=14)
        ctk.CTkLabel(esquerda, text="🜲", font=theme.glifo(12), text_color=theme.Cores.DOURADO).pack(side="left")
        ctk.CTkLabel(esquerda, text=f" {username} ", font=theme.FONTES["label"], text_color=theme.Cores.ROLE_BEGE).pack(side="left")
        ctk.CTkLabel(esquerda, text=f"· {role_label}", font=(theme.FAMILIA_SERIFADA, 12, "italic"), text_color=theme.Cores.MUTED).pack(side="left")

        self._label_modo = ctk.CTkLabel(conteudo, text="ONLINE · 0 FÓRUNS", font=theme.FONTES["label"], text_color=theme.Cores.SUCESSO)
        self._label_modo.grid(row=0, column=1)
        self._n_foruns = 0

        direita = ctk.CTkFrame(conteudo, fg_color="transparent")
        direita.grid(row=0, column=2, sticky="e", padx=10)
        for glifo_txt in ("⚙", "✦", "⏻"):
            ctk.CTkButton(direita, text=glifo_txt, width=24, height=20, font=theme.glifo(12),
                          fg_color="transparent", text_color=theme.Cores.MUTED, corner_radius=0,
                          hover_color=theme.Cores.BG_MEDIO).pack(side="left", padx=1)

    def set_foruns(self, n: int) -> None:
        self._n_foruns = n
        self.set_modo("online")

    def set_modo(self, modo: str, peers: int | None = None) -> None:
        cor = _CORES_MODO.get(modo, theme.Cores.MUTED)
        if modo == "online":
            texto = f"ONLINE · {self._n_foruns} FÓRUNS"
        elif modo == "lan":
            texto = f"LAN · {peers} CORVOS PRÓXIMOS" if peers is not None else "LAN"
        else:
            texto = _LABELS_MODO.get(modo, modo.upper())
        self._label_modo.configure(text=texto, text_color=cor)
