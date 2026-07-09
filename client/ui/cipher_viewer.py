"""Cipher Viewer (reconstrucao a partir de Janela Principal.dc.html).

Modal 540px "Assim viajou a mensagem" com o ciphertext REAL da mensagem em
base64 (quebrado a cada 56 chars), a frase "Isto é o que os olhos profanos
veriam...", e o grid ALGORITMO / PAYLOAD / IV. Botoes Copiar / Fechar.

Overlay escuro semi-transparente por tras (aproximado por um Toplevel escuro em
tela cheia sob o card) + borda dourada. So o visual mudou; recebe o ciphertext
real de quem abre.
"""

from __future__ import annotations

import customtkinter as ctk

from client.ui import theme
from client.ui.ui_helpers import barra_titulo_modal, centralizar_toplevel, grab_seguro


def _quebrar_linhas(texto: str, largura: int = 56) -> str:
    return "\n".join(texto[i : i + largura] for i in range(0, len(texto), largura))


class CipherViewer(ctk.CTkToplevel):
    def __init__(self, master, ciphertext_b64: str, iv_hex: str, payload_bytes: int,
                 algoritmo: str = "AES-256-CBC") -> None:
        super().__init__(master)
        self.overrideredirect(True)
        self.configure(fg_color=theme.Cores.BG_MODAL)
        self.transient(master)
        centralizar_toplevel(self, master, 540, 420)
        self.after(10, lambda: grab_seguro(self))

        frame = ctk.CTkFrame(self, fg_color=theme.Cores.BG_MODAL, border_width=1,
                             border_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_MODAL, 0.35), corner_radius=0)
        frame.pack(fill="both", expand=True, padx=1, pady=1)

        barra_titulo_modal(frame, "▸ RITUS // INTERCEPTIO", on_fechar=self.destroy, janela=self)

        topo = ctk.CTkFrame(frame, fg_color="transparent")
        topo.pack(pady=(20, 4))
        ctk.CTkLabel(topo, text="🔒", font=theme.glifo(16), text_color=theme.Cores.DOURADO).pack()
        ctk.CTkLabel(topo, text="Assim viajou a mensagem", font=(theme.FAMILIA_SERIFADA, 22, "bold"),
                     text_color=theme.Cores.DOURADO).pack(pady=(4, 6))
        div = ctk.CTkFrame(topo, fg_color="transparent", width=200)
        div.pack()
        ctk.CTkFrame(div, width=88, height=1, fg_color=theme.DOURADO_45, corner_radius=0).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(div, text="✦", font=theme.glifo(8), text_color=theme.Cores.MUTED).pack(side="left")
        ctk.CTkFrame(div, width=88, height=1, fg_color=theme.DOURADO_45, corner_radius=0).pack(side="left", padx=(8, 0))

        texto_cifrado = ctk.CTkTextbox(
            frame, font=theme.FONTES["corpo_pequeno"], fg_color=theme.Cores.BG_MEDIO,
            text_color=theme.CIPHER_TEXTO, corner_radius=0, border_width=1,
            border_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_MODAL, 0.25), height=150,
        )
        texto_cifrado.pack(fill="x", padx=24, pady=(6, 8))
        texto_cifrado.insert("1.0", _quebrar_linhas(ciphertext_b64))
        texto_cifrado.configure(state="disabled")

        ctk.CTkLabel(
            frame, text="Isto é o que os olhos profanos veriam se interceptassem esta transmissão.",
            font=(theme.FAMILIA_SERIFADA, 13, "italic"), text_color=theme.Cores.MUTED, wraplength=460,
        ).pack(pady=(0, 10))

        grid = ctk.CTkFrame(frame, fg_color="transparent")
        grid.pack(fill="x", padx=24)
        grid.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkFrame(frame, height=1, fg_color=theme.mix(theme.Cores.MUTED, theme.Cores.BG_MODAL, 0.25), corner_radius=0)

        for col, (label, valor) in enumerate(
            [("ALGORITMO", algoritmo), ("PAYLOAD", f"{payload_bytes} bytes"), ("IV", iv_hex[:16] + "…")]
        ):
            bloco = ctk.CTkFrame(grid, fg_color="transparent")
            bloco.grid(row=0, column=col, sticky="w")
            ctk.CTkLabel(bloco, text=label, font=theme.FONTES["label"], text_color=theme.Cores.MUTED).pack(anchor="w")
            ctk.CTkLabel(bloco, text=valor, font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.ROLE_BEGE).pack(anchor="w")

        botoes = ctk.CTkFrame(frame, fg_color="transparent")
        botoes.pack(pady=(16, 20))
        self._botao_copiar = ctk.CTkButton(
            botoes, text="Copiar", font=theme.FONTES["corpo_pequeno"], corner_radius=0,
            fg_color="transparent", border_width=1, border_color=theme.DOURADO_45,
            text_color=theme.Cores.DOURADO, hover_color=theme.Cores.BG_MEDIO,
            command=lambda: self._copiar(ciphertext_b64),
        )
        self._botao_copiar.pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            botoes, text="Fechar", font=theme.FONTES["corpo_pequeno"], corner_radius=0,
            fg_color="transparent", border_width=1,
            border_color=theme.mix(theme.Cores.MUTED, theme.Cores.BG_MODAL, 0.4),
            text_color=theme.Cores.MUTED, hover_color=theme.Cores.BG_MEDIO, command=self.destroy,
        ).pack(side="left")

        self._frame = frame
        self.bind("<Return>", lambda _e: self.destroy())
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

    def _copiar(self, texto: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(texto)
        self._botao_copiar.configure(text="Copiado ✓")
        self.after(2000, lambda: self._botao_copiar.configure(text="Copiar"))
