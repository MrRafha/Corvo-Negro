"""Splash / rito de inicializacao (reconstrucao visual a partir de Splash.dc.html).

Selo do corvo (🜲) + "CORVO NEGRO" + frase em italico + divisor, seguido do
painel "▸ COGITATOR // RITO DE INICIALIZAÇÃO" com 4 etapas de boot que acendem
em sequencia (pendente -> ativa pulsante -> concluida com ✓), cursor de bloco
piscando, e ao final "Pacto selado." -> "ENTRANDO NA CRIPTA..." -> callback.

Etapa 2 ("⚜ Forjando chaves ancestrais...") gera de VERDADE um par RSA-2048
numa thread (crypto_utils.generate_rsa_keypair, que ja existe e e testado), sem
travar a UI — a etapa so avanca quando a geracao termina. As demais etapas usam
os timers do mock (1.3s / 1.6s / 1.3s).

Duracoes do mock: 1300 / 1800 / 1600 / 1300 ms. A etapa 2 substitui seu timer
pela conclusao real da thread.
"""

from __future__ import annotations

import queue
import threading
from typing import Callable

import customtkinter as ctk

from shared import crypto_utils
from client.ui import theme
from client.ui.ui_helpers import (
    CursorBloco,
    DivisorOrnamental,
    cantos_dourados,
    desenhar_scanlines,
    forcar_icone_taskbar,
    maximizar_sem_moldura,
    parar_pulso,
    pulsar,
)

_ETAPAS = [
    ("🜲", "Despertando os corvos..."),
    ("⚜", "Forjando chaves ancestrais..."),
    ("⚔", "Consultando o astropata..."),
    ("🜍", "Recuperando pergaminhos..."),
]
_DURACOES_MS = [1300, 1800, 1600, 1300]

OnDone = Callable[[], None]


class SplashWindow(ctk.CTkToplevel):
    def __init__(self, master=None, on_done: OnDone | None = None, gerar_chaves: bool = True) -> None:
        if master is not None:
            super().__init__(master)
        else:
            # modo standalone (screenshot/teste): sobe como janela raiz propria
            ctk.set_appearance_mode("dark")
            super().__init__()
        self._on_done = on_done or (lambda: None)
        self._gerar_chaves = gerar_chaves
        self._keypair: tuple[bytes, bytes] | None = None
        self._fila_chaves: queue.Queue = queue.Queue()

        theme.carregar_fontes()
        self.title("Corvo Negro")
        self.geometry("900x640")
        self.configure(fg_color=theme.Cores.BG_PROFUNDO)
        self.overrideredirect(True)

        self._montar_fundo()
        self._montar_conteudo()

        self.after(10, lambda: maximizar_sem_moldura(self))
        self.after(20, lambda: forcar_icone_taskbar(self))
        self.after(300, self._iniciar_rito)

    @property
    def keypair(self) -> tuple[bytes, bytes] | None:
        """Par (private_pem, public_pem) gerado na etapa 2, ou None."""
        return self._keypair

    # --- fundo radial ---------------------------------------------------------------

    def _montar_fundo(self) -> None:
        self._canvas = ctk.CTkCanvas(self, highlightthickness=0, bd=0, bg=theme.Cores.BG_PROFUNDO)
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Configure>", self._pintar_fundo)

    def _pintar_fundo(self, event=None) -> None:
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        if w <= 1 or h <= 1:
            return
        self._canvas.delete("bg")
        cx, cy = w * 0.5, h * 0.38
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
            cor = "#" + "".join(f"{round(b + (c - b) * (1 - t_cor)):02x}" for c, b in zip(centro, borda))
            rx, ry = raio_max * t, raio_max * 0.78 * t
            self._canvas.create_oval(cx - rx, cy - ry, cx + rx, cy + ry, fill=cor, outline="", tags="bg")
        self._canvas.tag_lower("bg")
        desenhar_scanlines(self._canvas, w, h)

    # --- conteudo -------------------------------------------------------------------

    def _montar_conteudo(self) -> None:
        # card com borda dourada envolvendo TODO o conteudo (coroa, titulo,
        # lema, painel de boot) — sem isso o conteudo fica "solto" sobre o
        # fundo, e a transicao abrupta pro preto ao redor gera estranheza
        # (mesmo problema que o card do login ja resolve).
        card = ctk.CTkFrame(
            self._canvas, fg_color=theme.Cores.BG_PAINEL,
            border_width=1, border_color=theme.DOURADO_30, corner_radius=0,
        )
        card.place(relx=0.5, rely=0.5, anchor="center")
        cantos_dourados(card)

        col = ctk.CTkFrame(card, fg_color="transparent")
        col.pack(padx=48, pady=36)

        # selo do corvo
        ctk.CTkLabel(col, text="🜲", font=theme.glifo(46), text_color=theme.Cores.DOURADO).pack(pady=(0, 18))
        ctk.CTkLabel(col, text="C O R V O   N E G R O",
                     font=(theme.FAMILIA_SERIFADA, 42, "bold"), text_color=theme.Cores.DOURADO).pack()
        ctk.CTkLabel(col, text="Nas asas do corvo, a verdade voa em silêncio.",
                     font=(theme.FAMILIA_SERIFADA_MEDIUM, 16, "italic"), text_color=theme.Cores.MUTED).pack(pady=(8, 0))

        div = DivisorOrnamental(col, glifo_central="SILENTIUM IN AETERNUM",
                                cor_linha=theme.mix(theme.Cores.MUTED, theme.Cores.BG_PROFUNDO, 0.5))
        # divisor com texto ao inves de glifo central: reconstruimos manualmente
        for w in div.winfo_children():
            w.destroy()
        div.destroy()
        linha = ctk.CTkFrame(col, fg_color="transparent")
        linha.pack(pady=(10, 0))
        ctk.CTkFrame(linha, width=60, height=1, fg_color=theme.mix(theme.Cores.MUTED, theme.Cores.BG_PROFUNDO, 0.5), corner_radius=0).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(linha, text="SILENTIUM IN AETERNUM", font=theme.FONTES["label"], text_color=theme.Cores.MUTED).pack(side="left")
        ctk.CTkFrame(linha, width=60, height=1, fg_color=theme.mix(theme.Cores.MUTED, theme.Cores.BG_PROFUNDO, 0.5), corner_radius=0).pack(side="left", padx=(12, 0))

        # painel de etapas de boot
        painel = ctk.CTkFrame(col, width=410, fg_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_PROFUNDO, 0.02),
                              border_width=1, border_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_PROFUNDO, 0.28),
                              corner_radius=0)
        painel.pack(pady=(34, 0))
        painel.pack_propagate(False)
        painel.configure(height=196)

        faixa = ctk.CTkFrame(painel, fg_color=theme.CABECALHO_CARD, corner_radius=0, height=26)
        faixa.pack(fill="x")
        faixa.pack_propagate(False)
        ctk.CTkLabel(faixa, text="▸ COGITATOR // RITO DE INICIALIZAÇÃO", font=theme.FONTES["label"],
                     text_color=theme.Cores.MUTED).pack(side="left", padx=12)
        ctk.CTkLabel(faixa, text="RSA-2048", font=theme.FONTES["label"], text_color=theme.Cores.MUTED).pack(side="right", padx=12)

        corpo = ctk.CTkFrame(painel, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=16, pady=(14, 12))

        self._linhas_etapa: list[dict] = []
        for glifo_txt, texto in _ETAPAS:
            linha_e = ctk.CTkFrame(corpo, fg_color="transparent", height=22)
            linha_e.pack(fill="x", pady=3)
            lbl_glifo = ctk.CTkLabel(linha_e, text=glifo_txt, width=18, font=theme.glifo(14), text_color=theme.Cores.MUTED)
            lbl_glifo.pack(side="left")
            lbl_texto = ctk.CTkLabel(linha_e, text=texto, font=theme.FONTES["corpo"], text_color=theme.Cores.MUTED, anchor="w")
            lbl_texto.pack(side="left", fill="x", expand=True, padx=(12, 0))
            lbl_mark = ctk.CTkLabel(linha_e, text="", font=theme.FONTES["corpo"], text_color=theme.Cores.MUTED)
            lbl_mark.pack(side="right")
            linha_e.pack_propagate(False)
            self._linhas_etapa.append({"glifo": lbl_glifo, "texto": lbl_texto, "mark": lbl_mark, "linha": linha_e})
            # estado inicial: pendente (quase invisivel)
            self._set_pendente(len(self._linhas_etapa) - 1)

        # cursor > _
        cursor_linha = ctk.CTkFrame(corpo, fg_color="transparent")
        cursor_linha.pack(fill="x", anchor="w", pady=(2, 0))
        ctk.CTkLabel(cursor_linha, text=">", font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.DOURADO).pack(side="left")
        CursorBloco(cursor_linha, periodo_ms=550).pack(side="left", padx=(6, 0))

        # area de resultado (Pacto selado / falha)
        self._resultado = ctk.CTkFrame(col, fg_color="transparent", height=76)
        self._resultado.pack(pady=(10, 0))
        self._resultado.pack_propagate(False)

        ctk.CTkLabel(self._canvas, text="v1.0 · desenvolvido por MrRafha",
                     font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.MUTED).place(relx=0.5, rely=0.975, anchor="center")

    def _set_pendente(self, i: int) -> None:
        e = self._linhas_etapa[i]
        cor = theme.mix(theme.Cores.MUTED, theme.Cores.BG_PROFUNDO, 0.35)  # opacidade baixa
        e["glifo"].configure(text_color=cor)
        e["texto"].configure(text_color=cor)
        e["mark"].configure(text="", text_color=cor)

    def _set_ativa(self, i: int) -> None:
        e = self._linhas_etapa[i]
        e["glifo"].configure(text_color=theme.Cores.DOURADO)
        e["mark"].configure(text="")
        pulsar(e["texto"], theme.Cores.DOURADO, theme.mix(theme.Cores.DOURADO, theme.Cores.BG_PROFUNDO, 0.35), periodo_ms=750)

    def _set_concluida(self, i: int) -> None:
        e = self._linhas_etapa[i]
        parar_pulso(e["texto"])
        e["glifo"].configure(text_color=theme.Cores.SUCESSO)
        e["texto"].configure(text_color=theme.Cores.SUCESSO)
        e["mark"].configure(text="✓", text_color=theme.Cores.SUCESSO)

    def _set_falha(self, i: int) -> None:
        e = self._linhas_etapa[i]
        parar_pulso(e["texto"])
        e["glifo"].configure(text_color=theme.Cores.ERRO)
        e["texto"].configure(text_color=theme.Cores.ERRO)
        e["mark"].configure(text="✗", text_color=theme.Cores.ERRO)

    # --- sequencia do rito ----------------------------------------------------------

    def _iniciar_rito(self) -> None:
        self._executar_etapa(0)

    def _executar_etapa(self, i: int) -> None:
        if i >= len(_ETAPAS):
            return
        self._set_ativa(i)
        if i == 1 and self._gerar_chaves:
            # etapa real: gera RSA numa thread; avanca quando terminar.
            threading.Thread(target=self._gerar_rsa_thread, daemon=True).start()
            self._aguardar_chaves(i)
        else:
            if i == 1 and not self._gerar_chaves:
                self._keypair = None
            self.after(_DURACOES_MS[i], lambda: self._concluir_etapa(i))

    def _gerar_rsa_thread(self) -> None:
        try:
            priv, pub = crypto_utils.generate_rsa_keypair()
            self._fila_chaves.put(("ok", (priv, pub)))
        except Exception as exc:  # pragma: no cover
            self._fila_chaves.put(("erro", exc))

    def _aguardar_chaves(self, i: int) -> None:
        try:
            status, payload = self._fila_chaves.get_nowait()
        except queue.Empty:
            self.after(60, lambda: self._aguardar_chaves(i))
            return
        if status == "ok":
            self._keypair = payload
            self._concluir_etapa(i)
        else:
            self._set_falha(i)

    def _concluir_etapa(self, i: int) -> None:
        self._set_concluida(i)
        proxima = i + 1
        if proxima < len(_ETAPAS):
            self._executar_etapa(proxima)
        else:
            self._finalizar()

    def _finalizar(self) -> None:
        selado = ctk.CTkLabel(self._resultado, text="Pacto selado.",
                              font=(theme.FAMILIA_SERIFADA_MEDIUM, 19, "italic"), text_color=theme.Cores.SUCESSO)
        selado.pack(pady=(0, 4))
        entrando = ctk.CTkLabel(self._resultado, text="ENTRANDO NA CRIPTA...",
                                font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.MUTED)
        entrando.pack()
        pulsar(entrando, theme.Cores.MUTED, theme.mix(theme.Cores.MUTED, theme.Cores.BG_PROFUNDO, 0.4), periodo_ms=1100)
        self.after(1900, self._concluir)

    def _concluir(self) -> None:
        cb = self._on_done
        try:
            self.destroy()
        finally:
            cb()
