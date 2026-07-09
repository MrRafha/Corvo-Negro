"""Modal de aceitar convocacao (reconstrucao a partir de Modais.dc.html).

Faixa "▸ RITUS // VOCATIO", titulo "❖ Aceitar Convocação" + divisor, badge fixo
"CORVO" ✦ [XXXX] ✦ [XXXX] (2 entries de 4 chars, uppercase automatico, foco
pula ao completar 4), botao "❖ RESPONDER AO CHAMADO" e nota do rodape.

Ao confirmar: CMD_JOIN_FORUM de verdade — a chave AES chega depois via
KEY_ROTATED (tratado pelo listener central da MainWindow). Layout reescrito.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from shared import protocol
from client.network.gui_bridge import ClientBridge
from client.ui import theme
from client.ui.ui_helpers import DivisorOrnamental, barra_titulo_modal, centralizar_toplevel, grab_seguro

OnEntrou = Callable[[dict], None]


class JoinForumModal(ctk.CTkToplevel):
    def __init__(self, master, bridge: ClientBridge, on_entrou: OnEntrou) -> None:
        super().__init__(master)
        self._bridge = bridge
        self._on_entrou = on_entrou

        self.overrideredirect(True)
        self.configure(fg_color=theme.Cores.BG_MODAL)
        self.transient(master)
        centralizar_toplevel(self, master, 416, 360)
        self.after(10, lambda: grab_seguro(self))

        frame = ctk.CTkFrame(self, fg_color=theme.Cores.BG_MODAL, border_width=1,
                             border_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_MODAL, 0.35), corner_radius=0)
        frame.pack(fill="both", expand=True, padx=1, pady=1)

        barra_titulo_modal(frame, "▸ RITUS // VOCATIO", on_fechar=self.destroy, janela=self)

        corpo = ctk.CTkFrame(frame, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=26, pady=(24, 26))

        ctk.CTkLabel(corpo, text="❖ Aceitar Convocação", font=theme.FONTES["titulo_modal"], text_color=theme.Cores.DOURADO).pack()
        DivisorOrnamental(corpo, largura=190).pack(pady=(6, 18))

        ctk.CTkLabel(corpo, text="CÓDIGO DE CONVITE", font=theme.FONTES["label"], text_color=theme.Cores.MUTED).pack()

        linha = ctk.CTkFrame(corpo, fg_color="transparent")
        linha.pack(pady=(8, 18))
        ctk.CTkLabel(linha, text="CORVO", font=(theme.FAMILIA_SERIFADA, 18, "bold"), text_color=theme.Cores.DOURADO,
                     fg_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_MODAL, 0.06), corner_radius=0,
                     padx=10, pady=7).pack(side="left", padx=(0, 9))
        ctk.CTkLabel(linha, text="✦", font=theme.FONTES["label"], text_color=theme.Cores.MUTED).pack(side="left", padx=4)
        self._entry_a = self._mk_code(linha)
        self._entry_a.pack(side="left", padx=4)
        ctk.CTkLabel(linha, text="✦", font=theme.FONTES["label"], text_color=theme.Cores.MUTED).pack(side="left", padx=4)
        self._entry_b = self._mk_code(linha)
        self._entry_b.pack(side="left", padx=4)

        self._entry_a.bind("<KeyRelease>", lambda e: self._normalizar(self._entry_a, self._entry_b))
        self._entry_b.bind("<KeyRelease>", lambda e: self._normalizar(self._entry_b, None))

        self._label_status = ctk.CTkLabel(corpo, text="", font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.ERRO)
        self._label_status.pack(pady=(0, 8))

        ctk.CTkButton(corpo, text="❖ RESPONDER AO CHAMADO", font=theme.FONTES["corpo"], corner_radius=0, height=42,
                      fg_color=theme.Cores.DOURADO, text_color=theme.Cores.BG_PROFUNDO, hover_color=theme.Cores.TEXTO,
                      command=self._responder).pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(corpo, text="O convite deve ter sido forjado pelo\nCorvo-Mor de um fórum.",
                     font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.MUTED, justify="center").pack()

        self._frame = frame
        self.bind("<Return>", lambda _e: self._responder())
        self.after(20, self._ajustar_altura)

    def _ajustar_altura(self) -> None:
        self.update_idletasks()
        altura_necessaria = self._frame.winfo_reqheight() + 4
        largura = self.winfo_width()
        altura_disponivel = self.winfo_screenheight() - 80
        altura = min(altura_necessaria, altura_disponivel)
        x = self.winfo_x()
        y = max(0, (self.winfo_screenheight() - altura) // 2)
        self.geometry(f"{largura}x{altura}+{x}+{y}")

    def _mk_code(self, master) -> ctk.CTkEntry:
        e = ctk.CTkEntry(master, width=78, height=40, justify="center", font=(theme.FAMILIA_SERIFADA, 20, "bold"),
                         fg_color=theme.Cores.BG_MEDIO, border_color=theme.Cores.BG_ELEVADO, corner_radius=0,
                         text_color=theme.Cores.TEXTO, placeholder_text="XXXX")
        e.bind("<FocusIn>", lambda _e: e.configure(border_color=theme.DOURADO_55))
        e.bind("<FocusOut>", lambda _e: e.configure(border_color=theme.Cores.BG_ELEVADO))
        return e

    def _normalizar(self, entry: ctk.CTkEntry, proximo: ctk.CTkEntry | None) -> None:
        valor = "".join(c for c in entry.get().upper() if c.isalnum())[:4]
        if valor != entry.get():
            entry.delete(0, "end")
            entry.insert(0, valor)
        if len(valor) == 4 and proximo is not None:
            proximo.focus_set()

    def _responder(self) -> None:
        codigo = f"CORVO-{self._entry_a.get()}-{self._entry_b.get()}"
        if len(self._entry_a.get()) != 4 or len(self._entry_b.get()) != 4:
            self._label_status.configure(text="✗ preencha os 2 blocos de 4 caracteres.")
            return
        self._bridge.call(
            protocol.CMD_JOIN_FORUM, {"invite_code": codigo},
            on_ok=self._on_entrar_ok,
            on_error=lambda msg: self._label_status.configure(text=f"✗ {msg}"),
        )

    def _on_entrar_ok(self, data: dict) -> None:
        self._on_entrou(data)
        self.destroy()
