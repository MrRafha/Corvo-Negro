"""Modal de configuracoes do forum (aberto pelo botao ⚙ do header).

Menu vertical com ate 5 opcoes, cada uma condicional a permissao do usuario
atual no forum (calculada client-side a partir do CMD_GET_FORUM_MEMBERS, que
ja traz a permission mask de cada role):

    Convite         -> CREATE_INVITE: mostra o codigo atual (regenerado na
                       hora, ja que o servidor so guarda o hash) + botao
                       copiar. Reaproveita a chave AES ja distribuida — nao
                       afeta membros existentes, so o codigo de entrada.
    Gerenciar Ordens -> MANAGE_ROLES: abre o RoleManagerModal (aba "ordens").
    Gerenciar Membros -> KICK_MEMBER ou BAN_MEMBER: lista membros com botoes
                       de expulsar/banir conforme a permissao especifica.
    Editar Fórum    -> so o dono: nome + grade de glifos (mesma do
                       CreateForumModal), chama CMD_UPDATE_FORUM.
    Deletar Fórum   -> so o dono: confirmacao dupla, chama CMD_DELETE_FORUM.

Cada usuario ve so as opcoes que sua role permite; se nenhuma opcao se aplica,
mostra so uma mensagem informativa.
"""

from __future__ import annotations

import customtkinter as ctk

from shared import protocol
from shared.permissions import Permission, has_permission
from client.network.gui_bridge import ClientBridge
from client.ui import theme
from client.ui.app_state import AppState
from client.ui.role_manager import RoleManagerModal
from client.ui.ui_helpers import DivisorOrnamental, barra_titulo_modal, centralizar_toplevel, grab_seguro

_GLIFOS = ["🜲", "⚜", "⚔", "☿", "🜍", "🜔", "☉", "☽", "✠", "✦", "⚝", "🜏"]


class ForumSettingsModal(ctk.CTkToplevel):
    def __init__(
        self, master, bridge: ClientBridge, state: AppState, forum_id: int,
        nome_atual: str, icone_atual: str,
        on_forum_atualizado=None, on_forum_deletado=None,
    ) -> None:
        super().__init__(master)
        self._bridge = bridge
        self._state = state
        self._forum_id = forum_id
        self._nome_atual = nome_atual
        self._icone_atual = icone_atual
        self._on_forum_atualizado = on_forum_atualizado or (lambda nome, icone: None)
        self._on_forum_deletado = on_forum_deletado or (lambda: None)
        self._is_owner = forum_id in state.owned_forums
        self._minha_mask = 0
        self._membros: list[dict] = []
        self._glifo_edit_sel = _GLIFOS.index(icone_atual) if icone_atual in _GLIFOS else 0

        self.overrideredirect(True)
        self.configure(fg_color=theme.Cores.BG_MODAL)
        self.transient(master)
        centralizar_toplevel(self, master, 460, 520)
        self.after(10, lambda: grab_seguro(self))

        self._frame = ctk.CTkFrame(self, fg_color=theme.Cores.BG_MODAL, border_width=1,
                                   border_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_MODAL, 0.35), corner_radius=0)
        self._frame.pack(fill="both", expand=True, padx=1, pady=1)
        barra_titulo_modal(self._frame, "▸ RITUS // GUBERNIA", on_fechar=self.destroy, janela=self)

        self._corpo = ctk.CTkFrame(self._frame, fg_color="transparent")
        self._corpo.pack(fill="both", expand=True, padx=24, pady=(18, 22))

        self.bind("<Return>", lambda _e: None)
        self._carregar_permissoes()

    def _ajustar_altura(self) -> None:
        self.update_idletasks()
        altura_necessaria = self._frame.winfo_reqheight() + 4
        largura = self.winfo_width()
        altura_disponivel = self.winfo_screenheight() - 80
        altura = min(altura_necessaria, altura_disponivel)
        x = self.winfo_x()
        y = max(0, (self.winfo_screenheight() - altura) // 2)
        self.geometry(f"{largura}x{altura}+{x}+{y}")

    # --- dados ------------------------------------------------------------------------

    def _carregar_permissoes(self) -> None:
        self._bridge.call(protocol.CMD_GET_FORUM_MEMBERS, {"forum_id": self._forum_id}, on_ok=self._on_membros)

    def _on_membros(self, data: dict) -> None:
        self._membros = data.get("members", [])
        for m in self._membros:
            if m.get("username") == self._state.username:
                for r in m.get("roles", []):
                    self._minha_mask |= r.get("permissions", 0)
                break
        self._montar_menu()

    # --- menu principal -----------------------------------------------------------------

    def _montar_menu(self) -> None:
        for w in self._corpo.winfo_children():
            w.destroy()

        ctk.CTkLabel(self._corpo, text="⚙ Configurações do Fórum", font=theme.FONTES["titulo_modal"],
                     text_color=theme.Cores.DOURADO).pack()
        DivisorOrnamental(self._corpo, largura=190).pack(pady=(6, 16))

        opcoes = []
        if has_permission(self._minha_mask, Permission.CREATE_INVITE):
            opcoes.append(("✦", "Convite", "ver/gerar o código de convite atual", self._montar_convite))
        if has_permission(self._minha_mask, Permission.MANAGE_ROLES):
            opcoes.append(("⚔", "Gerenciar Ordens", "criar ordens e definir permissões", self._abrir_roles))
        if has_permission(self._minha_mask, Permission.KICK_MEMBER) or has_permission(self._minha_mask, Permission.BAN_MEMBER):
            opcoes.append(("☠", "Gerenciar Membros", "expulsar ou banir corvos do fórum", self._montar_membros))
        if self._is_owner:
            opcoes.append(("✎", "Editar Fórum", "mudar nome e símbolo", self._montar_editar))
            opcoes.append(("🜏", "Deletar Fórum", "apagar o fórum permanentemente", self._montar_deletar))

        if not opcoes:
            ctk.CTkLabel(self._corpo, text="Tua ordem não te concede\nnenhum poder aqui.",
                         font=(theme.FAMILIA_SERIFADA, 15, "italic"), text_color=theme.Cores.MUTED,
                         justify="center").pack(pady=30)
            self.after(20, self._ajustar_altura)
            return

        for glifo, titulo, desc, comando in opcoes:
            self._mk_opcao(glifo, titulo, desc, comando)

        self.after(20, self._ajustar_altura)

    def _mk_opcao(self, glifo: str, titulo: str, desc: str, comando) -> None:
        item = ctk.CTkFrame(self._corpo, fg_color=theme.Cores.BG_MEDIO, border_width=1,
                            border_color=theme.mix(theme.Cores.MUTED, theme.Cores.BG_MODAL, 0.3), corner_radius=0)
        item.pack(fill="x", pady=4)
        conteudo = ctk.CTkFrame(item, fg_color="transparent")
        conteudo.pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(conteudo, text=glifo, font=theme.glifo(18), text_color=theme.Cores.DOURADO).pack(side="left", padx=(0, 12))
        textos = ctk.CTkFrame(conteudo, fg_color="transparent")
        textos.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(textos, text=titulo, font=(theme.FAMILIA_SERIFADA, 16, "bold"),
                     text_color=theme.Cores.TEXTO, anchor="w").pack(fill="x")
        ctk.CTkLabel(textos, text=desc, font=theme.FONTES["corpo_pequeno"],
                     text_color=theme.Cores.MUTED, anchor="w").pack(fill="x")
        ctk.CTkLabel(conteudo, text="›", font=theme.glifo(16), text_color=theme.Cores.MUTED).pack(side="right")
        for w in (item, conteudo, *textos.winfo_children(), textos):
            w.bind("<Button-1>", lambda e: comando())
        item.bind("<Enter>", lambda e: item.configure(border_color=theme.DOURADO_55))
        item.bind("<Leave>", lambda e: item.configure(border_color=theme.mix(theme.Cores.MUTED, theme.Cores.BG_MODAL, 0.3)))

    def _voltar(self) -> None:
        self._montar_menu()

    def _mk_botao_voltar(self, master) -> None:
        ctk.CTkButton(master, text="‹ voltar", font=theme.FONTES["corpo_pequeno"], corner_radius=0, height=30, width=90,
                      fg_color="transparent", border_width=1, border_color=theme.mix(theme.Cores.MUTED, theme.Cores.BG_MODAL, 0.4),
                      text_color=theme.Cores.MUTED, hover_color=theme.Cores.BG_MEDIO, command=self._voltar).pack(anchor="w", pady=(0, 12))

    # --- opcao: convite -------------------------------------------------------------------

    def _montar_convite(self) -> None:
        for w in self._corpo.winfo_children():
            w.destroy()
        self._mk_botao_voltar(self._corpo)
        ctk.CTkLabel(self._corpo, text="✦ Convite do Fórum", font=theme.FONTES["titulo_modal"], text_color=theme.Cores.DOURADO).pack()
        DivisorOrnamental(self._corpo, largura=170).pack(pady=(6, 16))
        ctk.CTkLabel(self._corpo, text="Gerar um novo convite invalida o código anterior.\nTodos com poder de convocar serão avisados.",
                     font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.MUTED, justify="center", wraplength=380).pack(pady=(0, 16))

        self._label_convite = ctk.CTkLabel(self._corpo, text="— gere um convite para vê-lo —",
                                           font=(theme.FAMILIA_SERIFADA, 22, "bold"), text_color=theme.Cores.MUTED)
        self._label_convite.pack(pady=(0, 16))

        self._label_convite_status = ctk.CTkLabel(self._corpo, text="", font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.SUCESSO)
        self._label_convite_status.pack(pady=(0, 8))

        botoes = ctk.CTkFrame(self._corpo, fg_color="transparent")
        botoes.pack(fill="x")
        ctk.CTkButton(botoes, text="⚜ GERAR NOVO CONVITE", font=theme.FONTES["corpo"], corner_radius=0, height=42,
                      fg_color=theme.Cores.DOURADO, text_color=theme.Cores.BG_PROFUNDO, hover_color=theme.Cores.TEXTO,
                      command=self._regenerar_convite).pack(fill="x", pady=(0, 8))
        self._botao_copiar_convite = ctk.CTkButton(
            botoes, text="Copiar", font=theme.FONTES["corpo_pequeno"], corner_radius=0, height=36,
            fg_color="transparent", border_width=1, border_color=theme.DOURADO_45,
            text_color=theme.Cores.DOURADO, hover_color=theme.Cores.BG_MEDIO,
            command=self._copiar_convite, state="disabled",
        )
        self._botao_copiar_convite.pack(fill="x")
        self._convite_atual: str | None = None
        self.after(20, self._ajustar_altura)

    def _regenerar_convite(self) -> None:
        self._bridge.call(
            protocol.CMD_REGENERATE_INVITE, {"forum_id": self._forum_id},
            on_ok=self._on_convite_gerado,
            on_error=lambda msg: self._label_convite_status.configure(text=f"✗ {msg}", text_color=theme.Cores.ERRO),
        )

    def _on_convite_gerado(self, data: dict) -> None:
        self._convite_atual = data["invite_code"]
        self._label_convite.configure(text=self._convite_atual, text_color=theme.Cores.DOURADO)
        self._botao_copiar_convite.configure(state="normal")
        self._label_convite_status.configure(text="✓ Convite forjado.", text_color=theme.Cores.SUCESSO)

    def _copiar_convite(self) -> None:
        if not self._convite_atual:
            return
        self.clipboard_clear()
        self.clipboard_append(self._convite_atual)
        self._botao_copiar_convite.configure(text="Copiado ✓")
        self.after(2000, lambda: self._botao_copiar_convite.configure(text="Copiar"))

    # --- opcao: gerenciar ordens (delega ao modal ja existente) ----------------------------

    def _abrir_roles(self) -> None:
        RoleManagerModal(self.master, self._bridge, self._state, self._forum_id, aba="ordens")
        self.destroy()

    # --- opcao: gerenciar membros -----------------------------------------------------------

    def _montar_membros(self) -> None:
        for w in self._corpo.winfo_children():
            w.destroy()
        self._mk_botao_voltar(self._corpo)
        ctk.CTkLabel(self._corpo, text="☠ Gerenciar Membros", font=theme.FONTES["titulo_modal"], text_color=theme.Cores.DOURADO).pack()
        DivisorOrnamental(self._corpo, largura=170).pack(pady=(6, 14))

        self._label_membros_status = ctk.CTkLabel(self._corpo, text="", font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.SUCESSO)
        self._label_membros_status.pack(pady=(0, 8))

        lista = ctk.CTkScrollableFrame(self._corpo, fg_color="transparent", border_width=1,
                                       border_color=theme.mix(theme.Cores.MUTED, theme.Cores.BG_MODAL, 0.25),
                                       corner_radius=0, height=260)
        lista.pack(fill="both", expand=True)

        pode_kick = has_permission(self._minha_mask, Permission.KICK_MEMBER)
        pode_ban = has_permission(self._minha_mask, Permission.BAN_MEMBER)
        outros = [m for m in self._membros if m["username"] != self._state.username]
        if not outros:
            ctk.CTkLabel(lista, text="Nenhum outro corvo neste fórum.", font=(theme.FAMILIA_SERIFADA, 13, "italic"),
                         text_color=theme.Cores.MUTED).pack(pady=16)

        for m in outros:
            linha = ctk.CTkFrame(lista, fg_color="transparent", height=1, corner_radius=0)
            item = ctk.CTkFrame(lista, fg_color="transparent")
            item.pack(fill="x", pady=3, padx=4)
            ctk.CTkLabel(item, text=m["username"], font=theme.FONTES["corpo_pequeno"],
                         text_color=theme.Cores.TEXTO, anchor="w").pack(side="left", fill="x", expand=True)
            if pode_ban:
                ctk.CTkButton(item, text="Banir", font=theme.FONTES["label"], corner_radius=0, height=26, width=60,
                              fg_color="transparent", border_width=1, border_color=theme.mix(theme.Cores.ERRO, theme.Cores.BG_MODAL, 0.55),
                              text_color=theme.Cores.ERRO, hover_color=theme.mix(theme.Cores.CRIMSON, theme.Cores.BG_MODAL, 0.18),
                              command=lambda u=m["username"]: self._banir(u)).pack(side="right", padx=(4, 0))
            if pode_kick:
                ctk.CTkButton(item, text="Expulsar", font=theme.FONTES["label"], corner_radius=0, height=26, width=70,
                              fg_color="transparent", border_width=1, border_color=theme.DOURADO_45,
                              text_color=theme.Cores.DOURADO, hover_color=theme.Cores.BG_MEDIO,
                              command=lambda u=m["username"]: self._expulsar(u)).pack(side="right", padx=(4, 0))

        self.after(20, self._ajustar_altura)

    def _expulsar(self, username: str) -> None:
        self._bridge.call(
            protocol.CMD_KICK_MEMBER, {"forum_id": self._forum_id, "username": username},
            on_ok=lambda d: self._on_membro_removido(f"✓ {username} foi expulso."),
            on_error=lambda msg: self._label_membros_status.configure(text=f"✗ {msg}", text_color=theme.Cores.ERRO),
        )

    def _banir(self, username: str) -> None:
        self._bridge.call(
            protocol.CMD_BAN_MEMBER, {"forum_id": self._forum_id, "username": username},
            on_ok=lambda d: self._on_membro_removido(f"✓ {username} foi banido."),
            on_error=lambda msg: self._label_membros_status.configure(text=f"✗ {msg}", text_color=theme.Cores.ERRO),
        )

    def _on_membro_removido(self, mensagem: str) -> None:
        self._label_membros_status.configure(text=mensagem, text_color=theme.Cores.SUCESSO)
        self._bridge.call(protocol.CMD_GET_FORUM_MEMBERS, {"forum_id": self._forum_id}, on_ok=self._on_membros_atualizados_membros)

    def _on_membros_atualizados_membros(self, data: dict) -> None:
        self._membros = data.get("members", [])
        self._montar_membros()

    # --- opcao: editar forum (so dono) -------------------------------------------------------

    def _montar_editar(self) -> None:
        for w in self._corpo.winfo_children():
            w.destroy()
        self._mk_botao_voltar(self._corpo)
        ctk.CTkLabel(self._corpo, text="✎ Editar Fórum", font=theme.FONTES["titulo_modal"], text_color=theme.Cores.DOURADO).pack()
        DivisorOrnamental(self._corpo, largura=170).pack(pady=(6, 16))

        ctk.CTkLabel(self._corpo, text="NOME DO FÓRUM", font=theme.FONTES["label"], text_color=theme.Cores.MUTED, anchor="w").pack(fill="x")
        self._entry_edit_nome = ctk.CTkEntry(self._corpo, height=38, font=theme.FONTES["corpo"], corner_radius=0,
                                             fg_color=theme.Cores.BG_MEDIO, border_color=theme.Cores.BG_ELEVADO,
                                             text_color=theme.Cores.TEXTO)
        self._entry_edit_nome.insert(0, self._nome_atual)
        self._entry_edit_nome.pack(fill="x", pady=(4, 14))

        ctk.CTkLabel(self._corpo, text="SÍMBOLO DO FÓRUM", font=theme.FONTES["label"], text_color=theme.Cores.MUTED, anchor="w").pack(fill="x")
        grade = ctk.CTkFrame(self._corpo, fg_color="transparent")
        grade.pack(fill="x", pady=(6, 14))
        for i in range(6):
            grade.grid_columnconfigure(i, weight=1)
        self._botoes_glifo_edit: list[ctk.CTkButton] = []
        for i, glifo in enumerate(_GLIFOS):
            btn = ctk.CTkButton(
                grade, text=glifo, height=40, font=theme.glifo(17), corner_radius=0,
                fg_color=theme.Cores.BG_MEDIO, text_color=theme.Cores.MUTED,
                border_width=1, border_color=theme.Cores.BG_ELEVADO, hover_color=theme.Cores.BG_ELEVADO,
                command=lambda idx=i: self._selecionar_glifo_edit(idx),
            )
            btn.grid(row=i // 6, column=i % 6, padx=3, pady=3, sticky="ew")
            self._botoes_glifo_edit.append(btn)
        self._selecionar_glifo_edit(self._glifo_edit_sel)

        self._label_edit_status = ctk.CTkLabel(self._corpo, text="", font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.ERRO)
        self._label_edit_status.pack(pady=(0, 8))

        ctk.CTkButton(self._corpo, text="✎ SALVAR ALTERAÇÕES", font=theme.FONTES["corpo"], corner_radius=0, height=42,
                      fg_color=theme.Cores.DOURADO, text_color=theme.Cores.BG_PROFUNDO, hover_color=theme.Cores.TEXTO,
                      command=self._salvar_edicao).pack(fill="x")

        self.after(20, self._ajustar_altura)

    def _selecionar_glifo_edit(self, idx: int) -> None:
        self._glifo_edit_sel = idx
        for i, btn in enumerate(self._botoes_glifo_edit):
            if i == idx:
                btn.configure(border_color=theme.Cores.DOURADO, text_color=theme.Cores.DOURADO,
                              fg_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_MODAL, 0.14))
            else:
                btn.configure(border_color=theme.Cores.BG_ELEVADO, text_color=theme.Cores.MUTED, fg_color=theme.Cores.BG_MEDIO)

    def _salvar_edicao(self) -> None:
        nome = self._entry_edit_nome.get().strip()
        if not nome:
            self._label_edit_status.configure(text="✗ o nome do fórum é obrigatório.")
            return
        icone = _GLIFOS[self._glifo_edit_sel]
        self._bridge.call(
            protocol.CMD_UPDATE_FORUM, {"forum_id": self._forum_id, "name": nome, "icon": icone},
            on_ok=lambda d: self._on_editado(d),
            on_error=lambda msg: self._label_edit_status.configure(text=f"✗ {msg}"),
        )

    def _on_editado(self, data: dict) -> None:
        self._nome_atual = data["name"]
        self._icone_atual = data["icon"]
        self._on_forum_atualizado(data["name"], data["icon"])
        self.destroy()

    # --- opcao: deletar forum (so dono) -------------------------------------------------------

    def _montar_deletar(self) -> None:
        for w in self._corpo.winfo_children():
            w.destroy()
        self._mk_botao_voltar(self._corpo)
        ctk.CTkLabel(self._corpo, text="🜏 Deletar Fórum", font=theme.FONTES["titulo_modal"], text_color=theme.Cores.ERRO).pack()
        DivisorOrnamental(self._corpo, largura=170).pack(pady=(6, 16))
        ctk.CTkLabel(
            self._corpo,
            text=f"Isto apagará \"{self._nome_atual}\" para sempre —\nmensagens, ordens e membros serão perdidos.\nEsta ação não pode ser desfeita.",
            font=(theme.FAMILIA_SERIFADA, 14, "italic"), text_color=theme.Cores.MUTED, justify="center", wraplength=380,
        ).pack(pady=(0, 18))

        ctk.CTkLabel(self._corpo, text=f"Digite \"{self._nome_atual}\" para confirmar:",
                     font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.MUTED).pack()
        self._entry_confirmar_delete = ctk.CTkEntry(self._corpo, height=38, font=theme.FONTES["corpo"], corner_radius=0,
                                                    fg_color=theme.Cores.BG_MEDIO, border_color=theme.Cores.ERRO,
                                                    text_color=theme.Cores.TEXTO)
        self._entry_confirmar_delete.pack(fill="x", pady=(6, 14))

        self._label_delete_status = ctk.CTkLabel(self._corpo, text="", font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.ERRO)
        self._label_delete_status.pack(pady=(0, 8))

        ctk.CTkButton(self._corpo, text="🜏 APAGAR PARA SEMPRE", font=theme.FONTES["corpo"], corner_radius=0, height=42,
                      fg_color=theme.Cores.ERRO, text_color=theme.Cores.TEXTO,
                      hover_color=theme.mix(theme.Cores.CRIMSON, theme.Cores.BG_MODAL, 0.6),
                      command=self._confirmar_delecao).pack(fill="x")

        self.after(20, self._ajustar_altura)

    def _confirmar_delecao(self) -> None:
        if self._entry_confirmar_delete.get().strip() != self._nome_atual:
            self._label_delete_status.configure(text="✗ o nome digitado não confere.")
            return
        self._bridge.call(
            protocol.CMD_DELETE_FORUM, {"forum_id": self._forum_id},
            on_ok=lambda d: self._on_deletado(),
            on_error=lambda msg: self._label_delete_status.configure(text=f"✗ {msg}"),
        )

    def _on_deletado(self) -> None:
        self._on_forum_deletado()
        self.destroy()
