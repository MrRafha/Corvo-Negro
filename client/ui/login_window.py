"""Janela de login/registro (reconstrucao visual pixel-perfect).

Recria Login.dc.html: janela 900x640 com fundo radial escuro, card central de
432px de largura FIXA (largura travada com pack_propagate(False) num wrapper de
width fixo — senao o card cresce pra acomodar os filhos e "toma a tela inteira"),
cantos angulares dourados, faixa "▸ COGITATOR // PORTAL DE ACESSO", brasao 🜲 +
"CORVO NEGRO", duas abas (⚜ CONVOCAÇÃO / 🜲 NOVO CORVO) que alternam DENTRO do
card, medidor de forca do selo (4 segmentos) e caixa de erro.

A fiacao de rede (ClientBridge, key_vault, crypto_utils) e identica a versao
anterior ja validada — so o layout/geometria foi reescrito.
"""

from __future__ import annotations

import re
from typing import Callable

import customtkinter as ctk

from shared import crypto_utils, protocol
from client import config
from client.network.client_socket import CorvoClient
from client.network.gui_bridge import ClientBridge
from client.storage import key_vault
from client.ui import theme
from client.ui.app_state import AppState
from client.ui.ui_helpers import cantos_dourados, desenhar_scanlines, montar_janela_sem_moldura

_LARGURA_JANELA = 900
_ALTURA_JANELA = 640
_LARGURA_CARD = 432

_STRENGTH_LEVELS = [
    ("— — —", theme.Cores.MUTED),
    ("FRÁGIL", theme.Cores.ERRO),
    ("COMUM", theme.Cores.AVISO),
    ("FORTE", theme.Cores.SUCESSO),
    ("ANCESTRAL", theme.Cores.DOURADO),
]

OnSuccess = Callable[[ClientBridge, AppState], None]


def _score_senha(senha: str) -> int:
    score = 0
    if len(senha) >= 8:
        score += 1
    if len(senha) >= 13:
        score += 1
    if re.search(r"[A-Z]", senha) and re.search(r"[a-z]", senha):
        score += 1
    if re.search(r"\d", senha):
        score += 1
    if re.search(r"[^A-Za-z0-9]", senha):
        score += 1
    return min(4, score)


def _entry(master, **kwargs) -> ctk.CTkEntry:
    """CTkEntry com o visual do design (fundo BG_MEDIO, borda que doura no foco)."""
    e = ctk.CTkEntry(
        master, height=38, font=theme.FONTES["corpo"], corner_radius=0,
        fg_color=theme.Cores.BG_MEDIO, border_color=theme.Cores.BG_ELEVADO,
        text_color=theme.Cores.TEXTO, **kwargs,
    )
    e.bind("<FocusIn>", lambda _e: e.configure(border_color=theme.DOURADO_55))
    e.bind("<FocusOut>", lambda _e: e.configure(border_color=theme.Cores.BG_ELEVADO))
    return e


def _label(master, texto: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(master, text=texto, font=theme.FONTES["label"], text_color=theme.Cores.MUTED, anchor="w")


class LoginWindow(ctk.CTk):
    def __init__(self, on_success: OnSuccess) -> None:
        # IMPORTANTE: appearance_mode ANTES de instanciar o CTk, senao o
        # customtkinter herda o tema claro do SO por baixo dos frames.
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        super().__init__()
        self._on_success = on_success
        self._aba = "login"
        self._pw_visivel = False

        theme.carregar_fontes()
        self.title("Corvo Negro — Portal de Acesso")
        self.geometry(f"{_LARGURA_JANELA}x{_ALTURA_JANELA}")
        self.minsize(_LARGURA_JANELA, _ALTURA_JANELA)
        self.configure(fg_color=theme.Cores.BG_PROFUNDO)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        montar_janela_sem_moldura(self, "🜲 CORVO NEGRO", on_fechar=self.destroy, row=0)

        self._bridge: ClientBridge | None = None
        self._state = AppState()

        self._montar_fundo()
        self._montar_card()
        self._mostrar_aba("login")
        self.bind("<Return>", self._on_enter)

    def _on_enter(self, _event=None) -> None:
        if self._aba == "login":
            self._submeter_login()
        else:
            self._submeter_registro()

    # --- fundo radial ---------------------------------------------------------------

    def _montar_fundo(self) -> None:
        """Fundo radial escuro (aproxima o radial-gradient do CSS com um Canvas)."""
        self._canvas = ctk.CTkCanvas(self, highlightthickness=0, bd=0, bg=theme.Cores.BG_PROFUNDO)
        self._canvas.grid(row=1, column=0, sticky="nsew")
        self._canvas.bind("<Configure>", self._pintar_fundo)

    def _pintar_fundo(self, event=None) -> None:
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        if w <= 1 or h <= 1:
            return
        self._canvas.delete("bg")
        cx, cy = w * 0.5, h * 0.4
        centro = (0x2e, 0x26, 0x18)
        borda = (0x0a, 0x0a, 0x0a)
        passos = 26
        # raio baseado na diagonal da tela: em telas largas (16:9+), usar so
        # max(w, h) faz o gradiente "esticar" na direcao maior e sumir na
        # menor, deixando quase tudo na cor de borda. A diagonal garante que
        # o gradiente cubra toda a area visivel proporcionalmente.
        raio_max = max((w**2 + h**2) ** 0.5 * 0.55, 820)
        for i in range(1, passos + 1):
            t = i / passos
            # curva nao-linear (t**1.6): mantem mais area proxima da cor
            # central antes de comecar a escurecer, entao o gradiente fica
            # perceptivel em vez de "sumir" logo apos o centro.
            t_cor = t ** 1.6
            cor = "#" + "".join(
                f"{round(b + (c - b) * (1 - t_cor)):02x}" for c, b in zip(centro, borda)
            )
            rx, ry = raio_max * t, raio_max * 0.78 * t
            self._canvas.create_oval(cx - rx, cy - ry, cx + rx, cy + ry, fill=cor, outline="", tags="bg")
        self._canvas.tag_lower("bg")
        desenhar_scanlines(self._canvas, w, h)

    # --- card -----------------------------------------------------------------------

    def _montar_card(self) -> None:
        # Wrapper de LARGURA fixa: pack_propagate(False) impede que os filhos
        # (que usam fill="x") estiquem o card alem de _LARGURA_CARD. A altura
        # cresce com o conteudo (o card do mock nao tem altura fixa).
        # Card de tamanho FIXO: width E height + pack_propagate(False) impedem
        # que os filhos (fill="x") estiquem/encolham o card. A altura e recalculada
        # por aba (o registro e mais alto) em _ajustar_altura_card.
        self._card = ctk.CTkFrame(
            self._canvas, width=_LARGURA_CARD, height=560, fg_color=theme.Cores.BG_PAINEL,
            border_width=1, border_color=theme.DOURADO_30, corner_radius=0,
        )
        self._card.pack_propagate(False)
        self._card.place(relx=0.5, rely=0.5, anchor="center")
        self.after(60, self._ajustar_altura_card)

        cantos_dourados(self._card)

        # faixa "▸ COGITATOR // PORTAL DE ACESSO"
        faixa = ctk.CTkFrame(self._card, fg_color=theme.CABECALHO_CARD, corner_radius=0, height=26)
        faixa.pack(fill="x")
        faixa.pack_propagate(False)
        ctk.CTkLabel(faixa, text="▸ COGITATOR // PORTAL DE ACESSO", font=theme.FONTES["label"],
                     text_color=theme.Cores.MUTED).pack(side="left", padx=12)
        ctk.CTkLabel(faixa, text="AES-256", font=theme.FONTES["label"],
                     text_color=theme.Cores.MUTED).pack(side="right", padx=12)

        # brasao
        brasao = ctk.CTkFrame(self._card, fg_color="transparent")
        brasao.pack(pady=(16, 10))
        ctk.CTkLabel(brasao, text="🜲", font=theme.glifo(28), text_color=theme.Cores.DOURADO).pack()
        ctk.CTkLabel(brasao, text="C O R V O   N E G R O",
                     font=(theme.FAMILIA_SERIFADA, 26, "bold"), text_color=theme.Cores.DOURADO).pack(pady=(6, 0))
        ctk.CTkLabel(brasao, text="SILENTIUM IN AETERNUM", font=theme.FONTES["label"],
                     text_color=theme.Cores.MUTED).pack(pady=(2, 0))

        self._montar_tabs()

        # area de conteudo (troca entre login e registro)
        self._area = ctk.CTkFrame(self._card, fg_color="transparent")
        self._area.pack(fill="x", padx=26, pady=(16, 18))

        self._montar_aba_login()
        self._montar_aba_registro()
        self._montar_caixa_erro()

        # rodape
        ctk.CTkLabel(self._canvas, text="v1.0 · desenvolvido por MrRafha",
                     font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.MUTED).place(
            relx=0.5, rely=0.965, anchor="center")

    def _ajustar_altura_card(self) -> None:
        """Ajusta a altura do card a aba visivel.

        Com pack_propagate(False) o reqheight do card nao reflete os filhos;
        entao habilitamos a propagacao um instante para medir a altura natural
        e voltamos a travar (mantendo a LARGURA fixa em 432px)."""
        self._card.pack_propagate(True)
        self._card.update_idletasks()
        alt = self._card.winfo_reqheight()
        self._card.pack_propagate(False)
        self._card.configure(width=_LARGURA_CARD, height=alt)

    def _montar_tabs(self) -> None:
        tabs = ctk.CTkFrame(self._card, fg_color="transparent", corner_radius=0, height=42)
        tabs.pack(fill="x")
        tabs.pack_propagate(False)
        tabs.grid_columnconfigure((0, 1), weight=1)
        tabs.grid_rowconfigure(0, weight=1)

        self._btn_tab_login = ctk.CTkButton(
            tabs, text="⚜ CONVOCAÇÃO", font=theme.FONTES["corpo_pequeno"], corner_radius=0,
            fg_color=theme.Cores.BG_MEDIO, text_color=theme.Cores.DOURADO,
            hover_color=theme.Cores.BG_MEDIO, command=lambda: self._mostrar_aba("login"),
        )
        self._btn_tab_login.grid(row=0, column=0, sticky="nsew")
        self._btn_tab_registro = ctk.CTkButton(
            tabs, text="🜲 NOVO CORVO", font=theme.FONTES["corpo_pequeno"], corner_radius=0,
            fg_color=theme.TAB_INATIVA_BG, text_color=theme.Cores.MUTED,
            hover_color=theme.TAB_INATIVA_BG, command=lambda: self._mostrar_aba("registro"),
        )
        self._btn_tab_registro.grid(row=0, column=1, sticky="nsew")

        # borda inferior de 2px que marca a aba ativa (dourada) vs inativa
        marcadores = ctk.CTkFrame(self._card, fg_color="transparent", height=2, corner_radius=0)
        marcadores.pack(fill="x")
        marcadores.pack_propagate(False)
        marcadores.grid_columnconfigure((0, 1), weight=1)
        self._edge_login = ctk.CTkFrame(marcadores, height=2, fg_color=theme.Cores.DOURADO, corner_radius=0)
        self._edge_login.grid(row=0, column=0, sticky="ew")
        self._edge_registro = ctk.CTkFrame(marcadores, height=2, fg_color="transparent", corner_radius=0)
        self._edge_registro.grid(row=0, column=1, sticky="ew")

    def _montar_aba_login(self) -> None:
        self._aba_login = ctk.CTkFrame(self._area, fg_color="transparent")

        _label(self._aba_login, "⌂ SERVIDOR").pack(fill="x", pady=(0, 5))
        self._entry_servidor = _entry(self._aba_login)
        self._entry_servidor.insert(0, f"{config.SERVER_HOST}:{config.SERVER_PORT}")
        self._entry_servidor.pack(fill="x", pady=(0, 15))

        _label(self._aba_login, "🜲 NOME DO CORVO").pack(fill="x", pady=(0, 5))
        self._entry_login_user = _entry(self._aba_login, placeholder_text="teu nome na Ordem")
        self._entry_login_user.pack(fill="x", pady=(0, 15))

        _label(self._aba_login, "⚷ PALAVRA SELADA").pack(fill="x", pady=(0, 5))
        senha_frame = ctk.CTkFrame(self._aba_login, fg_color="transparent")
        senha_frame.pack(fill="x", pady=(0, 4))
        self._entry_login_senha = _entry(senha_frame, show="•")
        self._entry_login_senha.pack(side="left", fill="x", expand=True)
        self._btn_olho = ctk.CTkButton(
            senha_frame, text="👁", width=32, height=38, font=theme.FONTES["corpo_pequeno"],
            fg_color="transparent", text_color=theme.Cores.DOURADO, corner_radius=0,
            hover_color=theme.Cores.BG_MEDIO, command=self._alternar_visibilidade_senha,
        )
        self._btn_olho.pack(side="left", padx=(5, 0))

        ctk.CTkButton(
            self._aba_login, text="⚔ INICIAR CONVOCAÇÃO", font=theme.FONTES["corpo"], height=42,
            corner_radius=0, fg_color=theme.Cores.CRIMSON, text_color=theme.Cores.TEXTO,
            border_width=1, border_color=theme.Cores.ERRO, hover_color=theme.Cores.ERRO,
            command=self._submeter_login,
        ).pack(fill="x", pady=(15, 8))
        ctk.CTkButton(
            self._aba_login, text="Nunca fui convocado. Registrar novo Corvo →",
            font=theme.FONTES["corpo_pequeno"], fg_color="transparent", text_color=theme.Cores.MUTED,
            hover_color=theme.Cores.BG_PAINEL, command=lambda: self._mostrar_aba("registro"),
        ).pack()

    def _montar_aba_registro(self) -> None:
        self._aba_registro = ctk.CTkFrame(self._area, fg_color="transparent")

        _label(self._aba_registro, "🜲 NOME DO CORVO").pack(fill="x", pady=(0, 5))
        self._entry_reg_user = _entry(self._aba_registro, placeholder_text="como serás chamado na Ordem")
        self._entry_reg_user.pack(fill="x", pady=(0, 12))

        _label(self._aba_registro, "⚷ PALAVRA SELADA").pack(fill="x", pady=(0, 5))
        self._entry_reg_senha = _entry(self._aba_registro, show="•")
        self._entry_reg_senha.pack(fill="x", pady=(0, 8))
        self._entry_reg_senha.bind("<KeyRelease>", self._atualizar_forca_senha, add="+")

        forca_topo = ctk.CTkFrame(self._aba_registro, fg_color="transparent")
        forca_topo.pack(fill="x")
        ctk.CTkLabel(forca_topo, text="FORÇA DO SELO", font=theme.FONTES["label"],
                     text_color=theme.Cores.MUTED).pack(side="left")
        self._label_forca = ctk.CTkLabel(forca_topo, text=_STRENGTH_LEVELS[0][0],
                                         font=theme.FONTES["label"], text_color=_STRENGTH_LEVELS[0][1])
        self._label_forca.pack(side="right")

        segs = ctk.CTkFrame(self._aba_registro, fg_color="transparent")
        segs.pack(fill="x", pady=(5, 12))
        ctk.CTkLabel(segs, text="✧", font=theme.FONTES["label"], text_color=theme.Cores.MUTED).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(segs, text="✧", font=theme.FONTES["label"], text_color=theme.Cores.MUTED).pack(side="right", padx=(6, 0))
        self._segmentos_forca: list[ctk.CTkFrame] = []
        for _ in range(4):
            seg = ctk.CTkFrame(segs, height=6, fg_color=theme.Cores.BG_ELEVADO, corner_radius=0)
            seg.pack(side="left", expand=True, fill="x", padx=3)
            self._segmentos_forca.append(seg)

        _label(self._aba_registro, "⚷ CONFIRMAR PALAVRA SELADA").pack(fill="x", pady=(0, 5))
        self._entry_reg_senha2 = _entry(self._aba_registro, show="•")
        self._entry_reg_senha2.pack(fill="x", pady=(0, 4))
        self._entry_reg_senha2.bind("<KeyRelease>", self._checar_selos_coincidem, add="+")

        self._label_mismatch = ctk.CTkLabel(
            self._aba_registro, text="✗ Os selos não coincidem.", font=theme.FONTES["corpo_pequeno"],
            text_color=theme.Cores.ERRO, anchor="w",
        )

        self._btn_forjar = ctk.CTkButton(
            self._aba_registro, text="⚜ FORJAR NOVA IDENTIDADE", font=theme.FONTES["corpo"], height=42,
            corner_radius=0, fg_color=theme.Cores.DOURADO, text_color=theme.Cores.BG_PROFUNDO,
            border_width=1, border_color=theme.Cores.DOURADO, hover_color=theme.Cores.TEXTO,
            command=self._submeter_registro,
        )
        self._btn_forjar.pack(fill="x", pady=(12, 8))
        ctk.CTkButton(
            self._aba_registro, text="Já fui convocado. Retornar →", font=theme.FONTES["corpo_pequeno"],
            fg_color="transparent", text_color=theme.Cores.MUTED, hover_color=theme.Cores.BG_PAINEL,
            command=lambda: self._mostrar_aba("login"),
        ).pack()

    def _montar_caixa_erro(self) -> None:
        self._caixa_erro = ctk.CTkFrame(
            self._card, fg_color=theme.mix(theme.Cores.CRIMSON, theme.Cores.BG_PAINEL, 0.12),
            border_width=1, border_color=theme.mix(theme.Cores.ERRO, theme.Cores.BG_PAINEL, 0.45),
            corner_radius=0,
        )
        self._label_erro = ctk.CTkLabel(
            self._caixa_erro, text="✗ O astropata não reconhece esta assinatura.",
            font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.ERRO,
        )
        self._label_erro.pack(padx=14, pady=10, anchor="w")

    # --- navegacao entre abas -------------------------------------------------------

    def _mostrar_aba(self, aba: str) -> None:
        self._aba = aba
        self._esconder_erro()
        if aba == "login":
            self._aba_registro.pack_forget()
            self._aba_login.pack(fill="x")
            self._btn_tab_login.configure(fg_color=theme.Cores.BG_MEDIO, text_color=theme.Cores.DOURADO, hover_color=theme.Cores.BG_MEDIO)
            self._btn_tab_registro.configure(fg_color=theme.TAB_INATIVA_BG, text_color=theme.Cores.MUTED, hover_color=theme.TAB_INATIVA_BG)
            self._edge_login.configure(fg_color=theme.Cores.DOURADO)
            self._edge_registro.configure(fg_color="transparent")
        else:
            self._aba_login.pack_forget()
            self._aba_registro.pack(fill="x")
            self._btn_tab_registro.configure(fg_color=theme.Cores.BG_MEDIO, text_color=theme.Cores.DOURADO, hover_color=theme.Cores.BG_MEDIO)
            self._btn_tab_login.configure(fg_color=theme.TAB_INATIVA_BG, text_color=theme.Cores.MUTED, hover_color=theme.TAB_INATIVA_BG)
            self._edge_registro.configure(fg_color=theme.Cores.DOURADO)
            self._edge_login.configure(fg_color="transparent")
        if hasattr(self, "_card"):
            self.after(20, self._ajustar_altura_card)

    def _alternar_visibilidade_senha(self) -> None:
        self._pw_visivel = not self._pw_visivel
        self._entry_login_senha.configure(show="" if self._pw_visivel else "•")

    def _atualizar_forca_senha(self, _event=None) -> None:
        senha = self._entry_reg_senha.get()
        score = _score_senha(senha) if senha else 0
        label, cor = _STRENGTH_LEVELS[score]
        self._label_forca.configure(text=label, text_color=cor)
        for i, seg in enumerate(self._segmentos_forca):
            seg.configure(fg_color=cor if i < score else theme.Cores.BG_ELEVADO)

    def _checar_selos_coincidem(self, _event=None) -> None:
        senha = self._entry_reg_senha.get()
        confirmacao = self._entry_reg_senha2.get()
        if confirmacao and confirmacao != senha:
            self._label_mismatch.pack(fill="x", pady=(0, 4), before=self._btn_forjar)
        else:
            self._label_mismatch.pack_forget()

    def _mostrar_erro(self, mensagem: str) -> None:
        self._label_erro.configure(text=f"✗ {mensagem}")
        self._caixa_erro.pack(fill="x", padx=26, pady=(0, 20))

    def _esconder_erro(self) -> None:
        self._caixa_erro.pack_forget()

    # --- rede (identica a versao validada) ------------------------------------------

    def _parse_servidor(self) -> tuple[str, int]:
        texto = self._entry_servidor.get().strip()
        if ":" in texto:
            host, porta_str = texto.rsplit(":", 1)
            try:
                return host, int(porta_str)
            except ValueError:
                pass
        return config.SERVER_HOST, config.SERVER_PORT

    def _obter_bridge(self) -> ClientBridge:
        if self._bridge is None:
            host, porta = self._parse_servidor()
            self._bridge = ClientBridge(self, CorvoClient(host=host, port=porta))
            self._bridge.connect()
            self._bridge.start_polling()
        return self._bridge

    def _submeter_login(self) -> None:
        self._esconder_erro()
        username = self._entry_login_user.get().strip()
        senha = self._entry_login_senha.get()
        if not username or not senha:
            self._mostrar_erro("nome e palavra selada sao obrigatorios.")
            return
        try:
            bridge = self._obter_bridge()
        except OSError:
            self._tentar_login_offline(username, senha)
            return
        bridge.call(
            protocol.CMD_LOGIN, {"username": username, "password": senha},
            on_ok=lambda data: self._on_login_ok(username, senha, data),
            on_error=lambda msg: self._mostrar_erro("O astropata não reconhece esta assinatura."),
        )

    def _tentar_login_offline(self, username: str, senha: str) -> None:
        """Sem servidor alcancavel: so e possivel entrar se este usuario JA
        logou online alguma vez nesta maquina (o servidor e quem cria a
        conta/user_id — nao ha como se registrar offline). Reaproveita o
        key_vault existente como validador de senha: se load_private_key
        decifra sem erro, a senha esta correta (mesmo mecanismo de
        hash_password do servidor, so que local).
        """
        if not key_vault.has_vault(username):
            self._mostrar_erro("nao foi possivel alcancar o astropata (e este corvo nunca logou aqui antes).")
            return
        try:
            priv_pem = key_vault.load_private_key(username, senha)
        except Exception:
            self._mostrar_erro("O astropata não reconhece esta assinatura.")
            return

        from client.storage.local_db import LocalDB
        vault_dir = key_vault.VAULT_DIR.parent
        local_db = LocalDB(str(vault_dir / f"{username}_local.db"), senha)
        user_id = local_db.get_user_id()
        if user_id is None:
            self._mostrar_erro("nao foi possivel alcancar o astropata (sem sessao local salva ainda).")
            local_db.close()
            return

        self._state.username = username
        self._state.user_id = user_id
        self._state.private_key_pem = priv_pem
        self._state.local_db = local_db
        self._state.modo_lan = True

        bridge = ClientBridge(self, CorvoClient())  # sem conexao real — so pra ter a mesma interface
        self._bridge = bridge
        self._on_success(bridge, self._state)

    def _on_login_ok(self, username: str, senha: str, data: dict) -> None:
        self._state.username = username
        self._state.user_id = data.get("user_id")
        try:
            priv_pem = key_vault.load_private_key(username, senha)
        except (FileNotFoundError, ValueError):
            # FileNotFoundError: nunca logou nesta maquina. ValueError: vault
            # local existe mas nao decifra com esta senha (ex.: banco do
            # servidor foi recriado e o username voltou a ser aceito com
            # senha nova, mas o vault local antigo ainda esta em disco) —
            # nos dois casos, gera uma identidade nova e sobrescreve o vault.
            priv_pem, pub_pem = crypto_utils.generate_rsa_keypair()
            key_vault.save_private_key(username, priv_pem, senha)
        else:
            pub_pem = crypto_utils.public_key_from_private(priv_pem)
        self._state.private_key_pem = priv_pem

        from client.storage.local_db import LocalDB
        vault_dir = key_vault.VAULT_DIR.parent  # ~/.corvo_negro
        vault_dir.mkdir(parents=True, exist_ok=True)
        local_db = LocalDB(str(vault_dir / f"{username}_local.db"), senha)
        if self._state.user_id is not None:
            local_db.set_user_id(self._state.user_id)
        self._state.local_db = local_db

        bridge = self._obter_bridge()
        bridge.call(protocol.CMD_UPDATE_PUBKEY, {"public_key": pub_pem.decode("utf-8")})
        self._on_success(bridge, self._state)

    def _submeter_registro(self) -> None:
        self._esconder_erro()
        username = self._entry_reg_user.get().strip()
        senha = self._entry_reg_senha.get()
        senha2 = self._entry_reg_senha2.get()
        if not username or not senha:
            self._mostrar_erro("nome e palavra selada sao obrigatorios.")
            return
        if senha != senha2:
            self._mostrar_erro("Os selos não coincidem.")
            return
        try:
            bridge = self._obter_bridge()
        except OSError:
            self._mostrar_erro("nao foi possivel alcancar o astropata.")
            return
        bridge.call(
            protocol.CMD_REGISTER, {"username": username, "password": senha},
            on_ok=lambda data: self._on_registro_ok(username, senha),
            on_error=lambda msg: self._mostrar_erro(msg),
        )

    def _on_registro_ok(self, username: str, senha: str) -> None:
        if not key_vault.has_vault(username):
            priv_pem, _pub_pem = crypto_utils.generate_rsa_keypair()
            key_vault.save_private_key(username, priv_pem, senha)
        self._mostrar_aba("login")
        self._entry_login_user.delete(0, "end")
        self._entry_login_user.insert(0, username)
