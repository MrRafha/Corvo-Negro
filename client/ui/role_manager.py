"""Modais de Ordens (roles) — reconstrucao a partir de Modais.dc.html.

Dois modais irmaos, agrupados aqui:

  RoleManagerModal(aba="ordens")   — "▸ RITUS // HIERARCHIA", 780px, 2 colunas:
    lista de ordens do forum a esquerda (seleciona com borda dourada) e editor
    a direita (nome, 6 cores, 9 permissoes em checkboxes, portadores, DISSOLVER).
    Criar ordem: CMD_CREATE_ROLE. As 9 permissoes mapeiam Permission (bitmask).

  RoleManagerModal(aba="investir") — "▸ RITUS // INVESTITURA", 600px, 2 colunas:
    escolhe o corvo (esquerda) e a ordem (direita), frase de previa, e ao
    confirmar chama CMD_ASSIGN_ROLE e mostra "✓ Pacto selado." por 3s.

Como nao ha comando "listar roles" no protocolo, as ordens sao derivadas de
CMD_GET_FORUM_MEMBERS (cada membro traz suas roles). So o Corvo-Mor (permissao
MANAGE_ROLES) consegue de fato criar/atribuir — o servidor valida.
"""

from __future__ import annotations

import customtkinter as ctk

from shared import protocol
from shared.permissions import Permission
from client.network.gui_bridge import ClientBridge
from client.ui import theme
from client.ui.app_state import AppState
from client.ui.ui_helpers import DivisorOrnamental, barra_titulo_modal, centralizar_toplevel, grab_seguro

_PERMISSOES = [
    ("Enviar Mensagens", Permission.SEND_MESSAGE),
    ("Apagar Mensagens", Permission.DELETE_MESSAGE),
    ("Fixar Mensagens", Permission.PIN_MESSAGE),
    ("Enviar Imagens", Permission.SEND_IMAGE),
    ("Criar Canais", Permission.CREATE_CHANNEL),
    ("Expulsar Membros", Permission.KICK_MEMBER),
    ("Banir Membros", Permission.BAN_MEMBER),
    ("Gerenciar Ordens", Permission.MANAGE_ROLES),
    ("Governar o Fórum", Permission.MANAGE_FORUM),
]

_PALETA = [
    ("#c9a961", "Dourado"), ("#b0b0b8", "Prata"), ("#8b0000", "Crimson"),
    ("#4a7c3a", "Verde"), ("#6b4a7c", "Roxo"), ("#c9b98a", "Bege"),
]


class RoleManagerModal(ctk.CTkToplevel):
    def __init__(self, master, bridge: ClientBridge, state: AppState, forum_id: int, aba: str = "ordens") -> None:
        super().__init__(master)
        self._bridge = bridge
        self._state = state
        self._forum_id = forum_id
        self._aba = aba
        self._roles: list[dict] = []
        self._membros: list[dict] = []
        self._sel_role = 0
        self._perms_atual = 0
        self._cor_atual = _PALETA[0][0]
        self._inv_membro: str | None = None
        self._inv_role = 0

        self.overrideredirect(True)
        self.configure(fg_color=theme.Cores.BG_MODAL)
        self.transient(master)
        largura = 780 if aba == "ordens" else 600
        altura = 520 if aba == "ordens" else 470
        centralizar_toplevel(self, master, largura, altura)
        self.after(10, lambda: grab_seguro(self))

        self._frame = ctk.CTkFrame(self, fg_color=theme.Cores.BG_MODAL, border_width=1,
                                   border_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_MODAL, 0.35), corner_radius=0)
        self._frame.pack(fill="both", expand=True, padx=1, pady=1)
        titulo = "▸ RITUS // HIERARCHIA" if aba == "ordens" else "▸ RITUS // INVESTITURA"
        barra_titulo_modal(self._frame, titulo, on_fechar=self.destroy, janela=self)

        self._corpo = ctk.CTkFrame(self._frame, fg_color="transparent")
        self._corpo.pack(fill="both", expand=True)

        self.bind("<Return>", self._on_enter)
        self._carregar_dados()

    def _on_enter(self, _event=None) -> None:
        if self._aba == "ordens":
            self._salvar_ordem()
        else:
            self._investir()

    def _ajustar_altura(self) -> None:
        self.update_idletasks()
        altura_necessaria = self._frame.winfo_reqheight() + 4
        largura = self.winfo_width()
        altura_disponivel = self.winfo_screenheight() - 80
        altura = min(altura_necessaria, altura_disponivel)
        x = self.winfo_x()
        y = max(0, (self.winfo_screenheight() - altura) // 2)
        self.geometry(f"{largura}x{altura}+{x}+{y}")

    # --- dados ----------------------------------------------------------------------

    def _carregar_dados(self) -> None:
        self._bridge.call(protocol.CMD_GET_FORUM_MEMBERS, {"forum_id": self._forum_id}, on_ok=self._on_membros)

    def _on_membros(self, data: dict) -> None:
        self._membros = data.get("members", [])
        if self._aba == "ordens":
            # CMD_LIST_ROLES traz TODAS as ordens (mesmo sem portadores) — ao
            # contrario de derivar de CMD_GET_FORUM_MEMBERS, que so mostra
            # ordens que ja tem pelo menos 1 membro.
            self._bridge.call(protocol.CMD_LIST_ROLES, {"forum_id": self._forum_id}, on_ok=self._on_roles)
        else:
            self._roles = self._derivar_roles_dos_membros()
            self._montar_investir()
            self.after(20, self._ajustar_altura)

    def _on_roles(self, data: dict) -> None:
        roles = data.get("roles", [])
        self._roles = [
            {"role_id": r["role_id"], "name": r["name"], "color": r["color"],
             "priority": r.get("priority", 0), "members": r.get("members", []),
             "_mask": r.get("permissions", 0)}
            for r in sorted(roles, key=lambda r: -r.get("priority", 0))
        ]
        if not self._roles:
            self._roles = [{"role_id": None, "name": "Corvo-Mor", "color": "#c9a961", "priority": 100, "members": [], "_mask": 0}]
        self._montar_ordens()
        self.after(20, self._ajustar_altura)

    def _derivar_roles_dos_membros(self) -> list[dict]:
        roles_por_id: dict = {}
        for m in self._membros:
            for r in m.get("roles", []):
                rid = r.get("role_id")
                if rid not in roles_por_id:
                    roles_por_id[rid] = {"role_id": rid, "name": r["name"], "color": r["color"],
                                         "priority": r.get("priority", 0), "members": [],
                                         "_mask": r.get("permissions", 0)}
                roles_por_id[rid]["members"].append(m["username"])
        roles = sorted(roles_por_id.values(), key=lambda r: -r["priority"])
        if not roles:
            roles = [{"role_id": None, "name": "Corvo-Mor", "color": "#c9a961", "priority": 100, "members": []}]
        return roles

    # --- ABA ORDENS -----------------------------------------------------------------

    def _montar_ordens(self) -> None:
        for w in self._corpo.winfo_children():
            w.destroy()
        self._corpo.grid_columnconfigure(0, weight=0, minsize=232)
        self._corpo.grid_columnconfigure(1, weight=1)
        self._corpo.grid_rowconfigure(0, weight=1)

        esq = ctk.CTkFrame(self._corpo, fg_color=theme.Cores.BG_PAINEL, corner_radius=0)
        esq.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(esq, text="⚔ ORDENS DO FÓRUM", font=theme.FONTES["label"], text_color=theme.Cores.DOURADO).pack(anchor="w", padx=14, pady=(14, 10))
        self._lista_roles = ctk.CTkFrame(esq, fg_color="transparent")
        self._lista_roles.pack(fill="both", expand=True, padx=10)
        ctk.CTkButton(esq, text="＋ FORJAR NOVA ORDEM", font=theme.FONTES["label"], corner_radius=0, height=34,
                      fg_color="transparent", border_width=1, border_color=theme.DOURADO_45,
                      text_color=theme.Cores.DOURADO, hover_color=theme.Cores.BG_MEDIO,
                      command=self._nova_ordem).pack(fill="x", padx=12, pady=12)

        self._editor = ctk.CTkFrame(self._corpo, fg_color="transparent")
        self._editor.grid(row=0, column=1, sticky="nsew", padx=22, pady=18)

        self._popular_lista_roles()
        self._selecionar_role(0)

    def _popular_lista_roles(self) -> None:
        for w in self._lista_roles.winfo_children():
            w.destroy()
        self._itens_role = []
        for i, r in enumerate(self._roles):
            item = ctk.CTkFrame(self._lista_roles, height=1, fg_color="transparent", corner_radius=0)
            item.pack(fill="x", pady=2)
            borda = ctk.CTkFrame(item, width=2, height=1, fg_color="transparent", corner_radius=0)
            borda.pack(side="left", fill="y")
            dot = ctk.CTkFrame(item, width=9, height=9, fg_color=r["color"], corner_radius=0)
            dot.pack(side="left", padx=(9, 9), pady=9)
            dot.pack_propagate(False)
            nome = ctk.CTkLabel(item, text=r["name"], font=(theme.FAMILIA_SERIFADA, 16, "bold"), text_color=r["color"], anchor="w")
            nome.pack(side="left", fill="x", expand=True)
            cnt = ctk.CTkLabel(item, text=str(len(r["members"])), font=theme.FONTES["label"], text_color=theme.Cores.MUTED)
            cnt.pack(side="right", padx=10)
            for w in (item, borda, dot, nome, cnt):
                w.bind("<Button-1>", lambda e, idx=i: self._selecionar_role(idx))
            self._itens_role.append({"frame": item, "borda": borda})

    def _selecionar_role(self, idx: int) -> None:
        if not self._roles:
            return
        self._sel_role = max(0, min(idx, len(self._roles) - 1))
        for i, it in enumerate(self._itens_role):
            ativo = i == self._sel_role
            it["frame"].configure(fg_color=theme.Cores.BG_MEDIO if ativo else "transparent")
            it["borda"].configure(fg_color=theme.Cores.DOURADO if ativo else "transparent")
        self._montar_editor()

    def _montar_editor(self) -> None:
        for w in self._editor.winfo_children():
            w.destroy()
        r = self._roles[self._sel_role]
        self._cor_atual = r["color"]
        self._perms_atual = r.get("_mask", 0)

        ctk.CTkLabel(self._editor, text="NOME DA ORDEM", font=theme.FONTES["label"], text_color=theme.Cores.MUTED, anchor="w").pack(fill="x")
        self._entry_nome = ctk.CTkEntry(self._editor, height=36, font=(theme.FAMILIA_SERIFADA, 19, "bold"),
                                        fg_color=theme.Cores.BG_MEDIO, border_color=theme.Cores.BG_ELEVADO,
                                        corner_radius=0, text_color=r["color"])
        self._entry_nome.insert(0, r["name"])
        self._entry_nome.pack(fill="x", pady=(4, 12))

        ctk.CTkLabel(self._editor, text="COR DA ORDEM", font=theme.FONTES["label"], text_color=theme.Cores.MUTED, anchor="w").pack(fill="x")
        cores = ctk.CTkFrame(self._editor, fg_color="transparent")
        cores.pack(anchor="w", pady=(6, 12))
        self._botoes_cor = []
        for hexcor, nome in _PALETA:
            b = ctk.CTkFrame(cores, width=30, height=30, fg_color=hexcor, corner_radius=0,
                             border_width=2, border_color=theme.Cores.TEXTO if hexcor == self._cor_atual else theme.mix("#000000", hexcor, 0.5))
            b.pack(side="left", padx=(0, 8))
            b.pack_propagate(False)
            b.bind("<Button-1>", lambda e, c=hexcor: self._escolher_cor(c))
            self._botoes_cor.append((b, hexcor))

        ctk.CTkLabel(self._editor, text="PERMISSÕES", font=theme.FONTES["label"], text_color=theme.Cores.MUTED, anchor="w").pack(fill="x")
        grade = ctk.CTkFrame(self._editor, fg_color="transparent")
        grade.pack(fill="x", pady=(6, 12))
        for c in range(3):
            grade.grid_columnconfigure(c, weight=1)
        self._botoes_perm = []
        for i, (nome, flag) in enumerate(_PERMISSOES):
            marcado = bool(self._perms_atual & flag)
            b = self._mk_perm(grade, nome, flag, marcado)
            b["frame"].grid(row=i // 3, column=i % 3, sticky="ew", padx=(0, 10), pady=4)
            self._botoes_perm.append(b)

        ctk.CTkLabel(self._editor, text=f"PORTADORES — {len(r['members'])}", font=theme.FONTES["label"], text_color=theme.Cores.MUTED, anchor="w").pack(fill="x")
        portadores = ctk.CTkFrame(self._editor, fg_color="transparent")
        portadores.pack(fill="x", anchor="w", pady=(6, 12))
        for nome in r["members"]:
            ctk.CTkLabel(portadores, text=nome, font=theme.FONTES["corpo_pequeno"], text_color=r["color"],
                         fg_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_MODAL, 0.04), corner_radius=0,
                         padx=10, pady=4).pack(side="left", padx=(0, 7))

        rodape = ctk.CTkFrame(self._editor, fg_color="transparent")
        rodape.pack(fill="x", side="bottom", pady=(6, 0))
        self._label_editor_status = ctk.CTkLabel(rodape, text="", font=theme.FONTES["label"], text_color=theme.Cores.SUCESSO)
        self._label_editor_status.pack(side="bottom", pady=(4, 0))
        botoes_editor = ctk.CTkFrame(rodape, fg_color="transparent")
        botoes_editor.pack(fill="x", side="bottom")
        ctk.CTkButton(botoes_editor, text="SALVAR ALTERAÇÕES", font=theme.FONTES["corpo_pequeno"], corner_radius=0, height=38,
                      fg_color=theme.Cores.DOURADO, text_color=theme.Cores.BG_PROFUNDO, hover_color=theme.Cores.TEXTO,
                      command=self._salvar_ordem).pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._botao_dissolver = ctk.CTkButton(
            botoes_editor, text="☠ DISSOLVER ORDEM", font=theme.FONTES["corpo_pequeno"], corner_radius=0, height=38, width=180,
            fg_color="transparent", border_width=1, border_color=theme.mix(theme.Cores.ERRO, theme.Cores.BG_MODAL, 0.55),
            text_color=theme.Cores.ERRO, hover_color=theme.mix(theme.Cores.CRIMSON, theme.Cores.BG_MODAL, 0.18),
            command=self._dissolver_ordem,
        )
        self._botao_dissolver.pack(side="left")
        if r["name"] == "Corvo-Mor":
            self._botao_dissolver.configure(state="disabled")

    def _mk_perm(self, master, nome, flag, marcado) -> dict:
        frame = ctk.CTkFrame(master, fg_color="transparent", border_width=1,
                             border_color=theme.mix(theme.Cores.MUTED, theme.Cores.BG_MODAL, 0.25), corner_radius=0)
        box = ctk.CTkLabel(frame, text="✓" if marcado else "", width=17, height=17, font=theme.FONTES["label"],
                           text_color=theme.Cores.BG_PROFUNDO,
                           fg_color=theme.Cores.DOURADO if marcado else theme.Cores.BG_MODAL, corner_radius=0)
        box.pack(side="left", padx=8, pady=6)
        lbl = ctk.CTkLabel(frame, text=nome, font=theme.FONTES["corpo_pequeno"],
                           text_color=theme.Cores.TEXTO if marcado else theme.Cores.MUTED, anchor="w")
        lbl.pack(side="left", fill="x", expand=True)
        d = {"frame": frame, "box": box, "lbl": lbl, "flag": flag, "marcado": marcado}
        for w in (frame, box, lbl):
            w.bind("<Button-1>", lambda e, dd=d: self._toggle_perm(dd))
        return d

    def _toggle_perm(self, d: dict) -> None:
        d["marcado"] = not d["marcado"]
        if d["marcado"]:
            self._perms_atual |= d["flag"]
            d["box"].configure(text="✓", fg_color=theme.Cores.DOURADO, text_color=theme.Cores.BG_PROFUNDO)
            d["lbl"].configure(text_color=theme.Cores.TEXTO)
            d["frame"].configure(border_color=theme.DOURADO_55)
        else:
            self._perms_atual &= ~d["flag"]
            d["box"].configure(text="", fg_color=theme.Cores.BG_MODAL)
            d["lbl"].configure(text_color=theme.Cores.MUTED)
            d["frame"].configure(border_color=theme.mix(theme.Cores.MUTED, theme.Cores.BG_MODAL, 0.25))

    def _escolher_cor(self, cor: str) -> None:
        self._cor_atual = cor
        for b, hexcor in self._botoes_cor:
            b.configure(border_color=theme.Cores.TEXTO if hexcor == cor else theme.mix("#000000", hexcor, 0.5))
        self._entry_nome.configure(text_color=cor)

    def _nova_ordem(self) -> None:
        self._roles.append({"role_id": None, "name": "Nova Ordem", "color": "#8b0000", "priority": 10, "members": [], "_mask": 0})
        self._popular_lista_roles()
        self._selecionar_role(len(self._roles) - 1)

    def _salvar_ordem(self) -> None:
        nome = self._entry_nome.get().strip()
        if not nome:
            self._label_editor_status.configure(text="✗ o nome da ordem é obrigatório.", text_color=theme.Cores.ERRO)
            return
        r = self._roles[self._sel_role]
        if r.get("role_id") is None:
            self._bridge.call(
                protocol.CMD_CREATE_ROLE,
                {"forum_id": self._forum_id, "name": nome, "color": self._cor_atual,
                 "permissions": self._perms_atual, "priority": r.get("priority", 10)},
                on_ok=lambda d: self._on_ordem_criada(d),
                on_error=lambda msg: self._label_editor_status.configure(text=f"✗ {msg}", text_color=theme.Cores.ERRO),
            )
        else:
            self._bridge.call(
                protocol.CMD_UPDATE_ROLE,
                {"role_id": r["role_id"], "name": nome, "color": self._cor_atual, "permissions": self._perms_atual},
                on_ok=lambda d: self._on_ordem_atualizada(d),
                on_error=lambda msg: self._label_editor_status.configure(text=f"✗ {msg}", text_color=theme.Cores.ERRO),
            )

    def _on_ordem_criada(self, data: dict) -> None:
        self._label_editor_status.configure(text="✓ Ordem forjada.", text_color=theme.Cores.SUCESSO)
        self._carregar_dados()

    def _on_ordem_atualizada(self, data: dict) -> None:
        self._label_editor_status.configure(text="✓ Alterações registradas.", text_color=theme.Cores.SUCESSO)
        self._carregar_dados()

    def _dissolver_ordem(self) -> None:
        r = self._roles[self._sel_role]
        if r.get("role_id") is None:
            # ordem ainda nao existe no servidor (recem-criada localmente) —
            # so remove da lista local.
            self._roles.pop(self._sel_role)
            self._popular_lista_roles()
            self._selecionar_role(max(0, self._sel_role - 1))
            return
        self._bridge.call(
            protocol.CMD_DELETE_ROLE, {"role_id": r["role_id"]},
            on_ok=lambda d: self._carregar_dados(),
            on_error=lambda msg: self._label_editor_status.configure(text=f"✗ {msg}", text_color=theme.Cores.ERRO),
        )

    # --- ABA INVESTIR ---------------------------------------------------------------

    def _montar_investir(self) -> None:
        for w in self._corpo.winfo_children():
            w.destroy()
        outer = ctk.CTkFrame(self._corpo, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=26, pady=(20, 24))

        ctk.CTkLabel(outer, text="⚔ Investir Corvo em Ordem", font=theme.FONTES["titulo_modal"], text_color=theme.Cores.DOURADO).pack()
        DivisorOrnamental(outer, largura=190).pack(pady=(6, 14))

        cols = ctk.CTkFrame(outer, fg_color="transparent")
        cols.pack(fill="both", expand=True)
        cols.grid_columnconfigure((0, 1), weight=1)
        cols.grid_rowconfigure(0, weight=1)

        esq = ctk.CTkFrame(cols, fg_color="transparent")
        esq.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        ctk.CTkLabel(esq, text="O CORVO", font=theme.FONTES["label"], text_color=theme.Cores.MUTED, anchor="w").pack(fill="x", pady=(0, 6))
        cx_membros = ctk.CTkScrollableFrame(esq, fg_color="transparent", border_width=1,
                                            border_color=theme.mix(theme.Cores.MUTED, theme.Cores.BG_MODAL, 0.25), corner_radius=0, height=196)
        cx_membros.pack(fill="both", expand=True)
        self._itens_inv_membro = []
        for m in self._membros:
            roles = m.get("roles", [])
            principal = max(roles, key=lambda r: r.get("priority", 0)) if roles else {"name": "—", "color": theme.Cores.MUTED}
            it = self._mk_inv_membro(cx_membros, m["username"], principal, m.get("online", True))
            it["frame"].pack(fill="x", pady=1)
            self._itens_inv_membro.append(it)

        dir_ = ctk.CTkFrame(cols, fg_color="transparent")
        dir_.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        ctk.CTkLabel(dir_, text="A ORDEM", font=theme.FONTES["label"], text_color=theme.Cores.MUTED, anchor="w").pack(fill="x", pady=(0, 6))
        cx_roles = ctk.CTkFrame(dir_, fg_color="transparent", border_width=1,
                                border_color=theme.mix(theme.Cores.MUTED, theme.Cores.BG_MODAL, 0.25), corner_radius=0)
        cx_roles.pack(fill="both", expand=True)
        self._itens_inv_role = []
        for i, r in enumerate(self._roles):
            it = self._mk_inv_role(cx_roles, i, r)
            it["frame"].pack(fill="x", pady=1)
            self._itens_inv_role.append(it)

        self._label_previa = ctk.CTkLabel(outer, text="", font=(theme.FAMILIA_SERIFADA, 16, "italic"),
                                          text_color=theme.Cores.MUTED, wraplength=520, justify="center")
        self._label_previa.pack(pady=(12, 4))
        self._label_inv_status = ctk.CTkLabel(outer, text="", font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.SUCESSO)
        self._label_inv_status.pack()

        botoes = ctk.CTkFrame(outer, fg_color="transparent")
        botoes.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(botoes, text="⚔ INVESTIR", font=theme.FONTES["corpo"], corner_radius=0, height=42,
                      fg_color=theme.Cores.DOURADO, text_color=theme.Cores.BG_PROFUNDO, hover_color=theme.Cores.TEXTO,
                      command=self._investir).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(botoes, text="CANCELAR", font=theme.FONTES["corpo_pequeno"], corner_radius=0, height=42, width=100,
                      fg_color="transparent", border_width=1, border_color=theme.mix(theme.Cores.MUTED, theme.Cores.BG_MODAL, 0.4),
                      text_color=theme.Cores.MUTED, hover_color=theme.Cores.BG_MEDIO, command=self.destroy).pack(side="left")

        if self._membros:
            self._sel_inv_membro(0)
        self._sel_inv_role(0)

    def _mk_inv_membro(self, master, nome, principal, online) -> dict:
        frame = ctk.CTkFrame(master, height=1, fg_color="transparent", corner_radius=0)
        borda = ctk.CTkFrame(frame, width=2, height=1, fg_color="transparent", corner_radius=0)
        borda.pack(side="left", fill="y")
        dot = ctk.CTkFrame(frame, width=7, height=7, fg_color=theme.Cores.SUCESSO if online else theme.MEMBRO_OFFLINE, corner_radius=0)
        dot.pack(side="left", padx=(8, 8), pady=8)
        dot.pack_propagate(False)
        lbl = ctk.CTkLabel(frame, text=nome, font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.TEXTO, anchor="w")
        lbl.pack(side="left", fill="x", expand=True)
        rl = ctk.CTkLabel(frame, text=principal["name"], font=theme.FONTES["label"], text_color=principal["color"])
        rl.pack(side="right", padx=9)
        d = {"frame": frame, "borda": borda, "nome": nome}
        for w in (frame, borda, dot, lbl, rl):
            w.bind("<Button-1>", lambda e, n=nome: self._sel_inv_membro_by_name(n))
        return d

    def _mk_inv_role(self, master, idx, r) -> dict:
        frame = ctk.CTkFrame(master, height=1, fg_color="transparent", corner_radius=0)
        borda = ctk.CTkFrame(frame, width=2, height=1, fg_color="transparent", corner_radius=0)
        borda.pack(side="left", fill="y")
        mark = ctk.CTkLabel(frame, text="○", font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.DOURADO)
        mark.pack(side="left", padx=(8, 6), pady=8)
        dot = ctk.CTkFrame(frame, width=9, height=9, fg_color=r["color"], corner_radius=0)
        dot.pack(side="left", padx=(0, 8))
        dot.pack_propagate(False)
        lbl = ctk.CTkLabel(frame, text=r["name"], font=(theme.FAMILIA_SERIFADA, 16, "bold"), text_color=r["color"], anchor="w")
        lbl.pack(side="left", fill="x", expand=True)
        cnt = ctk.CTkLabel(frame, text=str(len(r["members"])), font=theme.FONTES["label"], text_color=theme.Cores.MUTED)
        cnt.pack(side="right", padx=9)
        d = {"frame": frame, "borda": borda, "mark": mark, "idx": idx}
        for w in (frame, borda, mark, dot, lbl, cnt):
            w.bind("<Button-1>", lambda e, i=idx: self._sel_inv_role(i))
        return d

    def _sel_inv_membro_by_name(self, nome: str) -> None:
        for i, m in enumerate(self._membros):
            if m["username"] == nome:
                self._sel_inv_membro(i)
                return

    def _sel_inv_membro(self, idx: int) -> None:
        self._inv_membro = self._membros[idx]["username"]
        for i, it in enumerate(self._itens_inv_membro):
            ativo = i == idx
            it["frame"].configure(fg_color=theme.Cores.BG_MEDIO if ativo else "transparent")
            it["borda"].configure(fg_color=theme.Cores.DOURADO if ativo else "transparent")
        self._atualizar_previa()

    def _sel_inv_role(self, idx: int) -> None:
        self._inv_role = idx
        for i, it in enumerate(self._itens_inv_role):
            ativo = i == idx
            it["frame"].configure(fg_color=theme.Cores.BG_MEDIO if ativo else "transparent")
            it["borda"].configure(fg_color=theme.Cores.DOURADO if ativo else "transparent")
            it["mark"].configure(text="◉" if ativo else "○")
        self._atualizar_previa()

    def _atualizar_previa(self) -> None:
        if self._inv_membro is None or not self._roles:
            return
        r = self._roles[self._inv_role]
        self._label_previa.configure(
            text=f"{self._inv_membro} será investido na ordem {r['name']}, perante os olhos da Cripta."
        )

    def _investir(self) -> None:
        if self._inv_membro is None or not self._roles:
            return
        r = self._roles[self._inv_role]
        role_id = r.get("role_id")
        if role_id is None:
            self._label_inv_status.configure(text="✗ ordem sem id (forje-a primeiro).", text_color=theme.Cores.ERRO)
            return
        self._bridge.call(
            protocol.CMD_ASSIGN_ROLE,
            {"forum_id": self._forum_id, "username": self._inv_membro, "role_id": role_id},
            on_ok=lambda d: self._investido(r["name"]),
            on_error=lambda msg: self._label_inv_status.configure(text=f"✗ {msg}", text_color=theme.Cores.ERRO),
        )

    def _investido(self, role_nome: str) -> None:
        self._label_inv_status.configure(
            text=f"✓ Pacto selado. {self._inv_membro} agora pertence à ordem: {role_nome}.",
            text_color=theme.Cores.SUCESSO,
        )
        self.after(3000, lambda: self._label_inv_status.configure(text=""))
