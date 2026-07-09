"""Modal de criacao de forum (reconstrucao a partir de Modais.dc.html).

Faixa "▸ RITUS // FUNDATIO", titulo "⚜ Fundar Novo Fórum" + divisor, campo de
nome, campo de proposito (opcional), grade 6xN de glifos selecionaveis (borda
dourada no ativo), toggle custom "Fórum público na LAN", e "⚜ SELAR O PACTO".

Ao selar: CMD_CREATE_FORUM de verdade, gera+distribui a AES key v1 (logica
identica a versao validada), e mostra o codigo de convite retornado.
"""

from __future__ import annotations

import base64
from typing import Callable

import customtkinter as ctk

from shared import crypto_utils, protocol
from client.network.gui_bridge import ClientBridge
from client.ui import theme
from client.ui.app_state import AppState
from client.ui.ui_helpers import DivisorOrnamental, barra_titulo_modal, centralizar_toplevel, grab_seguro

_GLIFOS = ["🜲", "⚜", "⚔", "☿", "🜍", "🜔", "☉", "☽", "✠", "✦", "⚝", "🜏"]

OnCriado = Callable[[dict], None]


class CreateForumModal(ctk.CTkToplevel):
    def __init__(self, master, bridge: ClientBridge, state: AppState, on_criado: OnCriado) -> None:
        super().__init__(master)
        self._bridge = bridge
        self._state = state
        self._on_criado = on_criado
        self._glifo_selecionado = 0
        self._lan_publico = True

        self.overrideredirect(True)
        self.configure(fg_color=theme.Cores.BG_MODAL)
        self.transient(master)
        centralizar_toplevel(self, master, 470, 660)
        self.after(10, lambda: grab_seguro(self))

        self._frame = ctk.CTkFrame(self, fg_color=theme.Cores.BG_MODAL, border_width=1,
                                   border_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_MODAL, 0.35), corner_radius=0)
        self._frame.pack(fill="both", expand=True, padx=1, pady=1)

        barra_titulo_modal(self._frame, "▸ RITUS // FUNDATIO", on_fechar=self.destroy, janela=self)

        corpo = ctk.CTkFrame(self._frame, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=26, pady=(20, 22))

        titulo = ctk.CTkFrame(corpo, fg_color="transparent")
        titulo.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(titulo, text="⚜ Fundar Novo Fórum", font=theme.FONTES["titulo_modal"],
                     text_color=theme.Cores.DOURADO).pack()
        DivisorOrnamental(titulo, largura=190).pack(pady=(6, 0))

        ctk.CTkLabel(corpo, text="NOME DO FÓRUM", font=theme.FONTES["label"], text_color=theme.Cores.MUTED, anchor="w").pack(fill="x")
        self._entry_nome = self._mk_entry(corpo, "ex.: Cripta do Silêncio")
        self._entry_nome.pack(fill="x", pady=(4, 12))

        ctk.CTkLabel(corpo, text="PROPÓSITO (opcional)", font=theme.FONTES["label"], text_color=theme.Cores.MUTED, anchor="w").pack(fill="x")
        self._entry_proposito = ctk.CTkTextbox(corpo, height=48, font=theme.FONTES["corpo_pequeno"],
                                               fg_color=theme.Cores.BG_MEDIO, border_width=1,
                                               border_color=theme.Cores.BG_ELEVADO, corner_radius=0,
                                               text_color=theme.Cores.TEXTO)
        self._entry_proposito.pack(fill="x", pady=(4, 12))

        ctk.CTkLabel(corpo, text="SÍMBOLO DO FÓRUM", font=theme.FONTES["label"], text_color=theme.Cores.MUTED, anchor="w").pack(fill="x")
        grade = ctk.CTkFrame(corpo, fg_color="transparent")
        grade.pack(fill="x", pady=(6, 12))
        for i in range(6):
            grade.grid_columnconfigure(i, weight=1)
        self._botoes_glifo: list[ctk.CTkButton] = []
        for i, glifo in enumerate(_GLIFOS):
            btn = ctk.CTkButton(
                grade, text=glifo, height=44, font=theme.glifo(19), corner_radius=0,
                fg_color=theme.Cores.BG_MEDIO, text_color=theme.Cores.MUTED,
                border_width=1, border_color=theme.Cores.BG_ELEVADO, hover_color=theme.Cores.BG_ELEVADO,
                command=lambda idx=i: self._selecionar_glifo(idx),
            )
            btn.grid(row=i // 6, column=i % 6, padx=3, pady=3, sticky="ew")
            self._botoes_glifo.append(btn)
        self._selecionar_glifo(0)

        self._montar_toggle_lan(corpo)

        self._label_status = ctk.CTkLabel(corpo, text="", font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.ERRO, anchor="w")
        self._label_status.pack(fill="x")

        botoes = ctk.CTkFrame(corpo, fg_color="transparent")
        botoes.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(
            botoes, text="⚜ SELAR O PACTO", font=theme.FONTES["corpo"], corner_radius=0, height=42,
            fg_color=theme.Cores.DOURADO, text_color=theme.Cores.BG_PROFUNDO, hover_color=theme.Cores.TEXTO,
            command=self._selar,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            botoes, text="CANCELAR", font=theme.FONTES["corpo_pequeno"], corner_radius=0, height=42, width=100,
            fg_color="transparent", border_width=1, border_color=theme.mix(theme.Cores.MUTED, theme.Cores.BG_MODAL, 0.4),
            text_color=theme.Cores.MUTED, hover_color=theme.Cores.BG_MEDIO, command=self.destroy,
        ).pack(side="left")

        self.bind("<Return>", lambda _e: self._selar())
        self.after(20, self._ajustar_altura)

    def _ajustar_altura(self) -> None:
        """Recalcula a altura da janela para caber todo o conteudo (evita
        botoes cortados fora da area visivel se o conteudo for mais alto que
        o valor inicial estimado)."""
        self.update_idletasks()
        altura_necessaria = self._frame.winfo_reqheight() + 4
        largura = self.winfo_width()
        altura_disponivel = self.winfo_screenheight() - 80
        altura = min(altura_necessaria, altura_disponivel)
        x = self.winfo_x()
        y = max(0, (self.winfo_screenheight() - altura) // 2)
        self.geometry(f"{largura}x{altura}+{x}+{y}")

    def _mk_entry(self, master, placeholder: str) -> ctk.CTkEntry:
        e = ctk.CTkEntry(master, height=38, font=theme.FONTES["corpo"], corner_radius=0,
                         fg_color=theme.Cores.BG_MEDIO, border_color=theme.Cores.BG_ELEVADO,
                         text_color=theme.Cores.TEXTO, placeholder_text=placeholder)
        e.bind("<FocusIn>", lambda _e: e.configure(border_color=theme.DOURADO_55))
        e.bind("<FocusOut>", lambda _e: e.configure(border_color=theme.Cores.BG_ELEVADO))
        return e

    def _montar_toggle_lan(self, master) -> None:
        wrap = ctk.CTkFrame(master, fg_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_MODAL, 0.03),
                            border_width=1, border_color=theme.mix(theme.Cores.MUTED, theme.Cores.BG_MODAL, 0.3), corner_radius=0)
        wrap.pack(fill="x", pady=(0, 14))
        txt = ctk.CTkFrame(wrap, fg_color="transparent")
        txt.pack(side="left", padx=12, pady=8)
        ctk.CTkLabel(txt, text="Fórum público na LAN", font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.TEXTO, anchor="w").pack(anchor="w")
        ctk.CTkLabel(txt, text="visível a corvos próximos quando a internet cair", font=theme.FONTES["label"], text_color=theme.Cores.MUTED, anchor="w").pack(anchor="w")

        self._toggle_track = ctk.CTkFrame(wrap, width=40, height=20, corner_radius=0,
                                          fg_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_MODAL, 0.18),
                                          border_width=1, border_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_MODAL, 0.6))
        self._toggle_track.pack(side="right", padx=12)
        self._toggle_track.pack_propagate(False)
        self._toggle_knob = ctk.CTkFrame(self._toggle_track, width=14, height=14, corner_radius=0, fg_color=theme.Cores.DOURADO)
        self._toggle_knob.place(relx=1.0, rely=0.5, anchor="e", x=-2)
        for w in (self._toggle_track, self._toggle_knob):
            w.bind("<Button-1>", lambda e: self._toggle_lan())

    def _toggle_lan(self) -> None:
        self._lan_publico = not self._lan_publico
        if self._lan_publico:
            self._toggle_track.configure(fg_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_MODAL, 0.18),
                                        border_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_MODAL, 0.6))
            self._toggle_knob.configure(fg_color=theme.Cores.DOURADO)
            self._toggle_knob.place_configure(relx=1.0, anchor="e", x=-2)
        else:
            self._toggle_track.configure(fg_color=theme.Cores.BG_MEDIO, border_color=theme.Cores.BG_ELEVADO)
            self._toggle_knob.configure(fg_color=theme.Cores.MUTED)
            self._toggle_knob.place_configure(relx=0.0, anchor="w", x=2)

    def _selecionar_glifo(self, idx: int) -> None:
        self._glifo_selecionado = idx
        for i, btn in enumerate(self._botoes_glifo):
            if i == idx:
                btn.configure(border_color=theme.Cores.DOURADO, text_color=theme.Cores.DOURADO,
                              fg_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_MODAL, 0.14))
            else:
                btn.configure(border_color=theme.Cores.BG_ELEVADO, text_color=theme.Cores.MUTED, fg_color=theme.Cores.BG_MEDIO)

    # --- rede (identica a versao validada) ------------------------------------------

    def _selar(self) -> None:
        nome = self._entry_nome.get().strip()
        if not nome:
            self._label_status.configure(text="✗ o nome do fórum é obrigatório.")
            return
        self._bridge.call(
            protocol.CMD_CREATE_FORUM, {"name": nome},
            on_ok=self._on_criar_ok,
            on_error=lambda msg: self._label_status.configure(text=f"✗ {msg}"),
        )

    def _on_criar_ok(self, data: dict) -> None:
        forum_id = data["forum_id"]
        self._state.note_ownership(forum_id, data.get("owner_id"))
        aes_key = crypto_utils.generate_aes_key()
        self._state.forum_keys[(forum_id, 1)] = aes_key
        self._distribuir_para_mim(forum_id, aes_key)
        self._on_criado(data)
        self._mostrar_convite(data["invite_code"])

    def _distribuir_para_mim(self, forum_id: int, aes_key: bytes) -> None:
        username = self._state.username
        self._bridge.call(protocol.CMD_GET_PUBKEY, {"username": username},
                          on_ok=lambda pubkey_data: self._enviar_distribute_key(forum_id, username, aes_key, pubkey_data))

    def _enviar_distribute_key(self, forum_id: int, username: str, aes_key: bytes, pubkey_data: dict) -> None:
        pub_pem = pubkey_data["public_key"].encode("utf-8")
        encrypted_aes_key = crypto_utils.rsa_encrypt(aes_key, pub_pem)
        self._bridge.call(
            protocol.CMD_DISTRIBUTE_KEY,
            {
                "forum_id": forum_id, "recipient": username,
                "encrypted_aes_key": base64.b64encode(encrypted_aes_key).decode("ascii"), "key_version": 1,
            },
        )

    def _mostrar_convite(self, invite_code: str) -> None:
        for widget in self._frame.winfo_children():
            widget.destroy()
        barra_titulo_modal(self._frame, "▸ RITUS // FUNDATIO", on_fechar=self.destroy, janela=self)
        corpo = ctk.CTkFrame(self._frame, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=26, pady=40)
        ctk.CTkLabel(corpo, text="✓ Pacto selado.", font=(theme.FAMILIA_SERIFADA_MEDIUM, 22, "italic"),
                     text_color=theme.Cores.SUCESSO).pack(pady=(20, 12))
        ctk.CTkLabel(corpo, text="Guarda este código e forja o chamado:", font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.MUTED).pack()
        ctk.CTkLabel(corpo, text=invite_code, font=(theme.FAMILIA_SERIFADA, 26, "bold"), text_color=theme.Cores.DOURADO).pack(pady=(6, 28))
        ctk.CTkButton(corpo, text="Fechar", font=theme.FONTES["corpo"], corner_radius=0, height=40,
                      fg_color=theme.Cores.DOURADO, text_color=theme.Cores.BG_PROFUNDO, hover_color=theme.Cores.TEXTO,
                      command=self.destroy).pack()
        self.unbind("<Return>")
        self.bind("<Return>", lambda _e: self.destroy())
        self.after(20, self._ajustar_altura)
