"""Area central de mensagens (reconstrucao visual a partir de Janela Principal.dc.html).

Cada mensagem: avatar quadrado 30px com a inicial, linha autor/hora/botao-olho,
e o corpo do texto com a ANIMACAO DE DECODIFICACAO (hash -> texto revelando
char a char — a assinatura do app, receita da secao 4.1 do IMPLEMENTACAO.md).
Mensagem propria ganha borda esquerda dourada + fundo levemente dourado.

Ao trocar de forum: skeleton de carregamento, depois historico exibido de
uma vez (sem animacao) — so a ultima mensagem ganha a animacao de
decodificacao, pra nao obrigar o usuario a esperar o hash->texto de toda
a sala de novo a cada troca de forum. Banner de sync opcional no topo.
Input inferior: anexo, glifos, textarea, ENVIAR, contador N/2000.

Envio/recebimento cifram/decifram com a AES do forum atual (app_state) —
identico a versao validada; so o layout foi reescrito.
"""

from __future__ import annotations

import base64
import datetime
import uuid as uuid_mod

import customtkinter as ctk

from shared import crypto_utils, protocol
from client.network.gui_bridge import ClientBridge
from client.ui import theme
from client.ui.app_state import AppState
from client.ui.cipher_viewer import CipherViewer
from client.ui.ui_helpers import CursorBloco, scramble

_MAX_CHARS = 2000
_INTERVALO_DECODIFICACAO_MS = 65
_PASSO_DECODIFICACAO = 2


def _agora() -> str:
    return datetime.datetime.now().strftime("%H:%M")


class _MensagemWidget(ctk.CTkFrame):
    """Uma mensagem no chat, com animacao de decodificacao e botao de cipher viewer.

    O corpo usa dois labels lado a lado: `_lbl_done` (texto ja revelado, cor
    TEXTO) e `_lbl_cifra` (scramble restante, cor CIPHER_SCRAMBLE), como sugere
    o IMPLEMENTACAO.md ("2 labels lado a lado"). Como sao inline, envolvemos num
    frame que embrulha; para textos longos usamos wraplength no label revelado.
    """

    def __init__(self, master, *, autor: str, cor: str, timestamp: str, texto: str, own: bool,
                 ciphertext_b64: str, iv_hex: str, on_ver_cifra) -> None:
        fundo = theme.MSG_PROPRIA_BG if own else "transparent"
        super().__init__(master, height=1, fg_color=fundo, corner_radius=0, border_width=0)

        # borda esquerda de 2px (dourada na propria, transparente nas outras)
        borda_cor = theme.DOURADO_55 if own else theme.CHAT_BG
        self._borda = ctk.CTkFrame(self, width=2, height=1, fg_color=borda_cor, corner_radius=0)
        self._borda.pack(side="left", fill="y")

        interno = ctk.CTkFrame(self, fg_color="transparent")
        interno.pack(side="left", fill="x", expand=True, padx=(9, 10), pady=6)

        topo = ctk.CTkFrame(interno, fg_color="transparent")
        topo.pack(fill="x")

        # avatar quadrado 30px com a inicial
        av_borda = theme.DOURADO_55 if own else theme.mix(theme.Cores.ROLE_PRATA, theme.Cores.BG_PROFUNDO, 0.35)
        avatar = ctk.CTkFrame(topo, width=30, height=30, fg_color=theme.Cores.BG_MEDIO,
                              border_width=1, border_color=av_borda, corner_radius=0)
        avatar.pack(side="left")
        avatar.pack_propagate(False)
        ctk.CTkLabel(avatar, text=(autor[:1] or "?").upper(),
                     font=(theme.FAMILIA_SERIFADA, 16, "bold"), text_color=cor).place(relx=0.5, rely=0.5, anchor="center")

        corpo = ctk.CTkFrame(topo, fg_color="transparent")
        corpo.pack(side="left", fill="x", expand=True, padx=(11, 0))

        cabecalho = ctk.CTkFrame(corpo, fg_color="transparent")
        cabecalho.pack(fill="x")
        ctk.CTkLabel(cabecalho, text=autor, font=theme.FONTES["corpo"], text_color=cor).pack(side="left")
        ctk.CTkLabel(cabecalho, text=f"  {timestamp}", font=theme.FONTES["corpo_pequeno"],
                     text_color=theme.Cores.MUTED).pack(side="left")
        ctk.CTkButton(
            cabecalho, text="👁", width=24, height=22, font=theme.FONTES["corpo_pequeno"],
            fg_color="transparent", text_color=theme.Cores.DOURADO, corner_radius=0,
            hover_color=theme.Cores.BG_MEDIO,
            command=lambda: on_ver_cifra(ciphertext_b64, iv_hex, len(texto.encode("utf-8"))),
        ).pack(side="right")

        # corpo do texto: label revelado + label scramble
        linha_texto = ctk.CTkFrame(corpo, fg_color="transparent")
        linha_texto.pack(fill="x", anchor="w", pady=(3, 0))
        self._lbl_done = ctk.CTkLabel(linha_texto, text="", font=theme.FONTES["corpo"],
                                      text_color=theme.Cores.TEXTO, justify="left", anchor="w", wraplength=520)
        self._lbl_done.pack(side="left", anchor="w")
        self._lbl_cifra = ctk.CTkLabel(linha_texto, text="", font=theme.FONTES["corpo"],
                                       text_color=theme.CIPHER_SCRAMBLE, justify="left", anchor="w", wraplength=200)
        self._lbl_cifra.pack(side="left", anchor="w")

        self._texto_final = texto
        self._pos = 0

    def revelar(self) -> None:
        self._pos = 0
        self._tick()

    def mostrar_direto(self) -> None:
        """Exibe o texto final de uma vez, sem a animacao de decodificacao."""
        self._pos = len(self._texto_final)
        self._lbl_done.configure(text=self._texto_final)
        self._lbl_cifra.configure(text="")

    def _tick(self) -> None:
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self._pos = min(len(self._texto_final), self._pos + _PASSO_DECODIFICACAO)
        resto = len(self._texto_final) - self._pos
        self._lbl_done.configure(text=self._texto_final[: self._pos])
        self._lbl_cifra.configure(text=scramble(resto) if resto else "")
        if self._pos < len(self._texto_final):
            self.after(_INTERVALO_DECODIFICACAO_MS, self._tick)


class ChatView(ctk.CTkFrame):
    def __init__(self, master, bridge: ClientBridge, state: AppState, on_forum_nome=None,
                 mesh_manager=None) -> None:
        super().__init__(master, fg_color=theme.CHAT_BG, corner_radius=0)
        self._bridge = bridge
        self._state = state
        self._on_forum_nome = on_forum_nome or (lambda *a, **k: None)
        self._mesh_manager = mesh_manager
        self._skeleton = None
        self._banner_sync = None
        self._lan_sem_peers = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # slot 0: banner de sync (opcional). slot 1: area de mensagens. slot 2: input.
        self._slot_banner = ctk.CTkFrame(self, fg_color="transparent", height=0, corner_radius=0)
        self._slot_banner.grid(row=0, column=0, sticky="ew")

        self._area_mensagens = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self._area_mensagens.grid(row=1, column=0, sticky="nsew", padx=6, pady=(10, 4))

        self._montar_input()
        self._bridge.on(protocol.EVT_NEW_MESSAGE, self._on_new_message)

    def definir_mesh_manager(self, mesh_manager) -> None:
        """Injeta o MeshPeerManager apos a MainWindow subir (modo LAN e ativado
        so depois do login, quando o ConnectionManager decide o modo)."""
        self._mesh_manager = mesh_manager

    # --- input ----------------------------------------------------------------------

    def _montar_input(self) -> None:
        rodape = ctk.CTkFrame(self, fg_color=theme.Cores.BG_PAINEL, corner_radius=0)
        rodape.grid(row=2, column=0, sticky="ew")

        linha = ctk.CTkFrame(rodape, fg_color="transparent")
        linha.pack(fill="x", padx=16, pady=(11, 2))

        for glifo_txt in ("📎", "🜲"):
            ctk.CTkButton(
                linha, text=glifo_txt, width=34, height=34, font=theme.glifo(14),
                fg_color="transparent", border_width=1,
                border_color=theme.mix(theme.Cores.MUTED, theme.Cores.BG_PAINEL, 0.4),
                text_color=theme.Cores.MUTED, corner_radius=0, hover_color=theme.Cores.BG_MEDIO,
            ).pack(side="left", padx=(0, 9))

        self._textbox = ctk.CTkTextbox(
            linha, height=34, font=theme.FONTES["corpo"], fg_color=theme.Cores.BG_MEDIO,
            border_width=1, border_color=theme.Cores.BG_ELEVADO, corner_radius=0,
            text_color=theme.Cores.TEXTO,
        )
        self._textbox.pack(side="left", fill="x", expand=True)
        self._textbox.bind("<KeyRelease>", self._on_digitar)
        self._textbox.bind("<Return>", self._on_enter)
        self._textbox.bind("<Shift-Return>", lambda e: None)
        self._placeholder_ativo = True
        self._textbox.insert("1.0", "Escreva o seu pergaminho...")
        self._textbox.configure(text_color=theme.Cores.MUTED)
        self._textbox.bind("<FocusIn>", self._limpar_placeholder)
        self._textbox.bind("<FocusOut>", self._repor_placeholder)

        ctk.CTkButton(
            linha, text="➤ ENVIAR", font=theme.FONTES["corpo_pequeno"], corner_radius=0,
            fg_color=theme.Cores.DOURADO, text_color=theme.Cores.BG_PROFUNDO,
            hover_color=theme.Cores.TEXTO, width=96, height=34, command=self._enviar,
        ).pack(side="left", padx=(9, 0))

        contador_frame = ctk.CTkFrame(rodape, fg_color="transparent")
        contador_frame.pack(fill="x", padx=16, pady=(0, 8))
        self._label_contador = ctk.CTkLabel(
            contador_frame, text=f"0 / {_MAX_CHARS}", font=theme.FONTES["label"], text_color=theme.Cores.MUTED
        )
        self._label_contador.pack(side="right")
        self._label_aviso = ctk.CTkLabel(
            contador_frame, text="", font=theme.FONTES["label"], text_color=theme.Cores.CRIMSON
        )
        self._label_aviso.pack(side="left")

    def _mostrar_aviso(self, texto: str) -> None:
        self._label_aviso.configure(text=texto)
        self.after(4000, lambda: self._label_aviso.configure(text=""))

    def _limpar_placeholder(self, _e=None) -> None:
        if self._placeholder_ativo:
            self._textbox.delete("1.0", "end")
            self._textbox.configure(text_color=theme.Cores.TEXTO)
            self._placeholder_ativo = False

    def _repor_placeholder(self, _e=None) -> None:
        if not self._textbox.get("1.0", "end-1c").strip():
            self._placeholder_ativo = True
            self._textbox.delete("1.0", "end")
            self._textbox.insert("1.0", "Escreva o seu pergaminho...")
            self._textbox.configure(text_color=theme.Cores.MUTED)

    def _texto_input(self) -> str:
        if self._placeholder_ativo:
            return ""
        return self._textbox.get("1.0", "end-1c")

    def _on_digitar(self, _event=None) -> None:
        texto = self._texto_input()
        self._label_contador.configure(text=f"{len(texto)} / {_MAX_CHARS}")

    def _on_enter(self, event) -> str:
        self._enviar()
        return "break"

    def _enviar(self) -> None:
        texto = self._texto_input().strip()
        if not texto:
            return
        forum_id = self._state.current_forum_id
        if forum_id is None:
            self._mostrar_aviso("Selecione um fórum antes de enviar.")
            return
        key_version = self._state.current_key_version(forum_id)
        aes_key = self._state.forum_keys.get((forum_id, key_version))
        if aes_key is None:
            self._mostrar_aviso("Chave do fórum ainda não recebida — aguarde o dono estar online.")
            return
        ciphertext, iv = crypto_utils.aes_encrypt(texto.encode("utf-8"), aes_key)
        ciphertext_b64 = base64.b64encode(ciphertext).decode("ascii")
        iv_b64 = base64.b64encode(iv).decode("ascii")

        if self._state.modo_lan and self._mesh_manager is not None:
            msg_uuid = str(uuid_mod.uuid4())
            origin_timestamp = datetime.datetime.now().isoformat()
            self._mesh_manager.broadcast_to_forum(forum_id, {
                "uuid": msg_uuid,
                "ciphertext": ciphertext_b64,
                "iv": iv_b64,
                "key_version": key_version,
                "sender": self._state.username,
                "origin_timestamp": origin_timestamp,
            })
            local_db = self._state.local_db
            if local_db is not None:
                local_db.save_message(
                    msg_uuid, forum_id, self._state.username, ciphertext, iv,
                    key_version, origin_timestamp, synced=False,
                )
        else:
            self._bridge.call(
                protocol.CMD_SEND_TO_FORUM,
                {
                    "forum_id": forum_id,
                    "ciphertext": ciphertext_b64,
                    "iv": iv_b64,
                    "key_version": key_version,
                },
                on_error=self._mostrar_aviso,
            )
        self._adicionar_mensagem(
            autor=self._state.username or "eu", cor=theme.Cores.DOURADO, timestamp=_agora(),
            texto=texto, own=True,
            ciphertext_b64=base64.b64encode(ciphertext).decode("ascii"), iv_hex=iv.hex(),
        )
        self._textbox.delete("1.0", "end")
        self._placeholder_ativo = False
        self._on_digitar()

    # --- recebimento ------------------------------------------------------------------

    def _on_new_message(self, data: dict) -> None:
        if data.get("forum_id") != self._state.current_forum_id:
            return
        aes_key = self._state.forum_keys.get((data["forum_id"], data["key_version"]))
        if aes_key is None:
            return
        try:
            ciphertext = base64.b64decode(data["ciphertext"])
            iv = base64.b64decode(data["iv"])
            plaintext = crypto_utils.aes_decrypt(ciphertext, aes_key, iv).decode("utf-8")
        except Exception:
            return
        self._adicionar_mensagem(
            autor=data["sender"], cor=theme.Cores.ROLE_PRATA, timestamp=_agora(),
            texto=plaintext, own=False, ciphertext_b64=data["ciphertext"], iv_hex=iv.hex(),
        )

    def on_mesh_message(self, data: dict) -> None:
        """Mensagem recebida via mesh P2P (modo LAN) — mesmo formato de
        decifragem de _on_new_message, mas persiste no local_db tambem (o
        historico online passa pelo GET_HISTORY do servidor, o LAN nao tem
        essa rede de seguranca)."""
        forum_id = data.get("forum_id")
        aes_key = self._state.forum_keys.get((forum_id, data.get("key_version")))
        if aes_key is None:
            return
        try:
            ciphertext = base64.b64decode(data["ciphertext"])
            iv = base64.b64decode(data["iv"])
            plaintext = crypto_utils.aes_decrypt(ciphertext, aes_key, iv).decode("utf-8")
        except Exception:
            return
        local_db = self._state.local_db
        if local_db is not None:
            local_db.save_message(
                data["uuid"], forum_id, data.get("sender", "?"), ciphertext, iv,
                data.get("key_version", 1), data.get("origin_timestamp", _agora()), synced=False,
            )
        if forum_id != self._state.current_forum_id:
            return
        self._adicionar_mensagem(
            autor=data.get("sender", "?"), cor=theme.Cores.ROLE_PRATA, timestamp=_agora(),
            texto=plaintext, own=False, ciphertext_b64=data["ciphertext"], iv_hex=iv.hex(),
        )

    # --- forum atual / historico --------------------------------------------------------

    def carregar_forum(self, forum_id: int) -> None:
        self._state.current_forum_id = forum_id
        for widget in self._area_mensagens.winfo_children():
            widget.destroy()
        self._mostrar_skeleton()
        self._bridge.call(
            protocol.CMD_GET_HISTORY, {"forum_id": forum_id}, on_ok=self._on_historico_carregado,
        )
        # se a chave desta versao ainda nao esta em memoria (ex.: o dono
        # estava offline quando eu entrei no forum), pede ao servidor —
        # ele devolve na hora se ja tiver uma copia salva, ou avisa o dono
        # (se online) para redistribuir. Nao bloqueia o carregamento acima.
        key_version = self._state.current_key_version(forum_id)
        if self._state.forum_keys.get((forum_id, key_version)) is None:
            self._bridge.call(
                protocol.CMD_REQUEST_FORUM_KEY, {"forum_id": forum_id}, on_ok=self._on_forum_key_recebida,
            )

    def _on_forum_key_recebida(self, data: dict) -> None:
        priv_pem = self._state.private_key_pem
        if priv_pem is None:
            return
        try:
            encrypted_aes_key = base64.b64decode(data["encrypted_aes_key"])
            aes_key = crypto_utils.rsa_decrypt(encrypted_aes_key, priv_pem)
            self._state.forum_keys[(data["forum_id"], data["key_version"])] = aes_key
        except Exception:
            return
        if data["forum_id"] == self._state.current_forum_id:
            self.carregar_forum(data["forum_id"])

    def limpar(self) -> None:
        """Reseta a area de mensagens quando o forum atual deixa de existir
        para este usuario (deletado, kick, ban)."""
        for widget in self._area_mensagens.winfo_children():
            widget.destroy()

    def _on_historico_carregado(self, data: dict) -> None:
        if data.get("forum_id") != self._state.current_forum_id:
            return
        self._esconder_skeleton()
        mensagens = data.get("messages", [])
        ultimo_index = len(mensagens) - 1
        for i, msg in enumerate(mensagens):
            self._exibir_mensagem_historico(msg, animar=(i == ultimo_index))

    def _exibir_mensagem_historico(self, msg: dict, *, animar: bool) -> None:
        forum_id = self._state.current_forum_id
        aes_key = self._state.forum_keys.get((forum_id, msg["key_version"]))
        if aes_key is None:
            return
        try:
            ciphertext = base64.b64decode(msg["ciphertext"])
            iv = base64.b64decode(msg["iv"])
            plaintext = crypto_utils.aes_decrypt(ciphertext, aes_key, iv).decode("utf-8")
        except Exception:
            return
        own = msg["sender"] == self._state.username
        cor = theme.Cores.DOURADO if own else theme.Cores.ROLE_PRATA
        ts = msg["timestamp"][-8:-3] if len(msg.get("timestamp", "")) >= 5 else msg.get("timestamp", "")
        self._adicionar_mensagem(
            autor=msg["sender"], cor=cor, timestamp=ts, texto=plaintext, own=own,
            ciphertext_b64=msg["ciphertext"], iv_hex=iv.hex(), animar=animar,
        )

    # --- skeleton / banner ------------------------------------------------------------

    def _mostrar_skeleton(self) -> None:
        from client.ui.estados import SkeletonChat
        self._esconder_skeleton()
        self._skeleton = SkeletonChat(self._area_mensagens)
        self._skeleton.pack(fill="x", padx=6, pady=6)

    def _esconder_skeleton(self) -> None:
        if self._skeleton is not None:
            self._skeleton.destroy()
            self._skeleton = None

    def mostrar_banner_sync(self, n_perdidas: int) -> None:
        from client.ui.estados import BannerSync
        if self._banner_sync is not None:
            self._banner_sync.destroy()
        self._banner_sync = BannerSync(self._slot_banner, n_perdidas)
        self._banner_sync.pack(fill="x")

    def atualizar_lan_sem_peers(self, mostrar: bool) -> None:
        """Mostra/esconde o card 'buscando outros corvos...' sobre a area de
        mensagens, quando em modo LAN sem nenhum peer conectado ainda."""
        if mostrar and self._lan_sem_peers is None:
            from client.ui.estados import LanSemPeers
            self._lan_sem_peers = LanSemPeers(self._area_mensagens)
            self._lan_sem_peers.pack(pady=40)
        elif not mostrar and self._lan_sem_peers is not None:
            self._lan_sem_peers.destroy()
            self._lan_sem_peers = None

    # --- helper --------------------------------------------------------------------

    def _adicionar_mensagem(self, *, autor: str, cor: str, timestamp: str, texto: str, own: bool,
                            ciphertext_b64: str, iv_hex: str, animar: bool = True) -> None:
        widget = _MensagemWidget(
            self._area_mensagens, autor=autor, cor=cor, timestamp=timestamp, texto=texto, own=own,
            ciphertext_b64=ciphertext_b64, iv_hex=iv_hex, on_ver_cifra=self._abrir_cipher_viewer,
        )
        widget.pack(fill="x", pady=2)
        if animar:
            widget.revelar()
        else:
            widget.mostrar_direto()
        self.after(30, lambda: self._area_mensagens._parent_canvas.yview_moveto(1.0))

    def adicionar_mensagem_fixada(self, autor: str, timestamp: str, texto: str, ciphertext_b64: str = "", iv_hex: str = "") -> None:
        """Card de mensagem fixada (⚑ FIXADO PELO CORVO-MOR) no topo do chat."""
        card = ctk.CTkFrame(self._area_mensagens, fg_color=theme.FIXADO_BG, border_width=1,
                            border_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_PROFUNDO, 0.2), corner_radius=0)
        card.pack(fill="x", padx=6, pady=(0, 8))
        ctk.CTkLabel(card, text="⚑ FIXADO PELO CORVO-MOR", font=theme.FONTES["label"],
                     text_color=theme.Cores.DOURADO).pack(anchor="w", padx=12, pady=(10, 2))
        cab = ctk.CTkFrame(card, fg_color="transparent")
        cab.pack(fill="x", padx=12)
        ctk.CTkLabel(cab, text=autor, font=theme.FONTES["corpo"], text_color=theme.Cores.DOURADO).pack(side="left")
        ctk.CTkLabel(cab, text=f"  {timestamp}", font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.MUTED).pack(side="left")
        ctk.CTkLabel(card, text=texto, font=theme.FONTES["corpo"], text_color=theme.Cores.TEXTO,
                     justify="left", anchor="w", wraplength=560).pack(fill="x", anchor="w", padx=12, pady=(2, 10))

    def adicionar_divisor_dia(self, texto: str) -> None:
        div = ctk.CTkFrame(self._area_mensagens, fg_color="transparent")
        div.pack(fill="x", padx=6, pady=(6, 10))
        ctk.CTkFrame(div, height=1, fg_color=theme.mix(theme.Cores.MUTED, theme.CHAT_BG, 0.4), corner_radius=0).pack(side="left", fill="x", expand=True, padx=(0, 12))
        ctk.CTkLabel(div, text=f"✦ {texto} ✦", font=(theme.FAMILIA_SERIFADA, 12, "italic"), text_color=theme.Cores.MUTED).pack(side="left")
        ctk.CTkFrame(div, height=1, fg_color=theme.mix(theme.Cores.MUTED, theme.CHAT_BG, 0.4), corner_radius=0).pack(side="left", fill="x", expand=True, padx=(12, 0))

    def _abrir_cipher_viewer(self, ciphertext_b64: str, iv_hex: str, payload_bytes: int) -> None:
        CipherViewer(self.winfo_toplevel(), ciphertext_b64=ciphertext_b64, iv_hex=iv_hex, payload_bytes=payload_bytes)
