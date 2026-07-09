"""Estados de loading/vazio/sync (reconstrucao a partir de Estados.dc.html).

Widgets reutilizaveis, integrados pelas telas correspondentes:
    - SkeletonChat: placeholders pulsantes enquanto o historico carrega;
    - BannerSync: banner ambar "Sincronizando..." com barra de progresso, que
      vira o banner verde "✓ Sincronizado" e some apos 3s;
    - ToastReconexao: toast canto inferior-direito (place) sobre a MainWindow;
    - EmptyForuns: "Nenhum fórum reclama tua presença..." (primeiro login);
    - LanSemPeers: radar pulsante "buscando outros corvos... PORTA 9999";
    - AguardandoAprovacao: anel + "Aguardando o Corvo-Mor romper o selo...".

Anel giratorio SVG e scanlines CRT sao decorativos — como o IMPLEMENTACAO.md
autoriza, simplificamos (glifo pulsante no lugar do spin, sem overlay CRT).
"""

from __future__ import annotations

import customtkinter as ctk

from client.ui import theme
from client.ui.ui_helpers import CursorBloco, pulsar, pulsar_fg


# --- skeleton do chat ---------------------------------------------------------------

_SKEL_ROWS = [
    ("72", "86%", True, "54%"),
    ("54", "64%", False, "0"),
    ("88", "92%", True, "38%"),
    ("60", "47%", False, "0"),
]


class SkeletonChat(ctk.CTkFrame):
    def __init__(self, master, **kwargs) -> None:
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self._barras: list[ctk.CTkFrame] = []
        for name_w, line_w, second, line2_w in _SKEL_ROWS:
            linha = ctk.CTkFrame(self, fg_color="transparent")
            linha.pack(fill="x", pady=7)
            av = ctk.CTkFrame(linha, width=30, height=30, fg_color=theme.Cores.BG_MEDIO, corner_radius=0)
            av.pack(side="left")
            av.pack_propagate(False)
            self._barras.append(av)
            col = ctk.CTkFrame(linha, fg_color="transparent")
            col.pack(side="left", fill="x", expand=True, padx=(11, 0))
            top = ctk.CTkFrame(col, fg_color="transparent")
            top.pack(fill="x", anchor="w")
            b1 = ctk.CTkFrame(top, width=int(name_w), height=11, fg_color=theme.Cores.BG_MEDIO, corner_radius=0)
            b1.pack(side="left", pady=(0, 6))
            b1.pack_propagate(False)
            self._barras.append(b1)
            # linha de texto 1 (largura relativa)
            f1 = ctk.CTkFrame(col, height=11, fg_color=theme.Cores.BG_MEDIO, corner_radius=0)
            f1.pack(fill="x", pady=(0, 6))
            self._barras.append(f1)
            if second:
                f2 = ctk.CTkFrame(col, height=11, fg_color=theme.Cores.BG_MEDIO, corner_radius=0)
                f2.pack(anchor="w", pady=(0, 0))
                f2.configure(width=int(300 * (float(line2_w.strip('%')) / 100)) if line2_w.endswith('%') else 100)
                f2.pack_propagate(False)
                self._barras.append(f2)

        rodape = ctk.CTkFrame(self, fg_color="transparent")
        rodape.pack(pady=(4, 0))
        self._lbl = ctk.CTkLabel(rodape, text="Recuperando pergaminhos", font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.MUTED)
        self._lbl.pack(side="left")
        CursorBloco(rodape, cor=theme.Cores.MUTED, periodo_ms=550, cor_fundo=theme.CHAT_BG).pack(side="left", padx=(6, 0))

        pulsar(self._lbl, theme.Cores.MUTED, theme.mix(theme.Cores.MUTED, theme.CHAT_BG, 0.4), periodo_ms=800)
        self._animar()

    def _animar(self, claro=[False]) -> None:
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        cor = "#222222" if claro[0] else theme.Cores.BG_MEDIO
        for b in self._barras:
            try:
                b.configure(fg_color=cor)
            except Exception:
                pass
        claro[0] = not claro[0]
        self.after(1100, self._animar)


# --- banner de sync -----------------------------------------------------------------

class BannerSync(ctk.CTkFrame):
    def __init__(self, master, n_perdidas: int, on_fim=None, **kwargs) -> None:
        kwargs.setdefault("fg_color", theme.mix(theme.Cores.AVISO, theme.CHAT_BG, 0.07))
        kwargs.setdefault("corner_radius", 0)
        super().__init__(master, border_width=0, **kwargs)
        self._on_fim = on_fim or (lambda: None)

        linha = ctk.CTkFrame(self, fg_color="transparent")
        linha.pack(fill="x", padx=18, pady=8)
        self._icone = ctk.CTkLabel(linha, text="⟳", font=theme.FONTES["label"], text_color=theme.Cores.DOURADO)
        self._icone.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(linha, text=f"Sincronizando com o servidor — {n_perdidas} mensagens perdidas nas asas do warp",
                     font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.DOURADO).pack(side="left")

        trilho = ctk.CTkFrame(self, height=3, fg_color=theme.Cores.BG_MEDIO, corner_radius=0)
        trilho.pack(fill="x")
        trilho.pack_propagate(False)
        self._barra = ctk.CTkProgressBar(trilho, height=3, corner_radius=0,
                                         progress_color=theme.Cores.DOURADO, fg_color=theme.Cores.BG_MEDIO)
        self._barra.pack(fill="x")
        self._barra.set(0.06)
        self._progresso = 0.06
        self._girar()
        self._avancar()

    def _girar(self, ang=[0]) -> None:
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        simbolos = ["⟳", "⟲"]
        self._icone.configure(text=simbolos[ang[0] % 2])
        ang[0] += 1
        self.after(500, self._girar)

    def _avancar(self) -> None:
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self._progresso = min(1.0, self._progresso + 0.09)
        self._barra.set(self._progresso)
        if self._progresso >= 1.0:
            self._concluir()
        else:
            self.after(220, self._avancar)

    def _concluir(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        self.configure(fg_color=theme.mix(theme.Cores.SUCESSO, theme.CHAT_BG, 0.08))
        linha = ctk.CTkFrame(self, fg_color="transparent")
        linha.pack(fill="x", padx=18, pady=8)
        import datetime
        hora = datetime.datetime.now().strftime("%H:%M")
        ctk.CTkLabel(linha, text="✓", font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.SUCESSO).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(linha, text=f"Sincronizado às {hora}", font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.SUCESSO).pack(side="left")
        self.after(3000, self._sumir)

    def _sumir(self) -> None:
        try:
            self.destroy()
        finally:
            self._on_fim()


# --- toast de reconexao -------------------------------------------------------------

class ToastReconexao(ctk.CTkFrame):
    """Toast no canto inferior-direito (posicionar com place sobre a MainWindow)."""

    def __init__(self, master, texto: str, modo: str = "aviso", **kwargs) -> None:
        cor = theme.Cores.AVISO if modo == "aviso" else theme.Cores.SUCESSO
        kwargs.setdefault("fg_color", theme.Cores.BG_MODAL)
        kwargs.setdefault("corner_radius", 0)
        super().__init__(master, border_width=1, border_color=theme.mix(cor, theme.Cores.BG_MODAL, 0.45), **kwargs)
        dot = ctk.CTkFrame(self, width=8, height=8, fg_color=cor, corner_radius=0)
        dot.pack(side="left", padx=(14, 10), pady=9)
        dot.pack_propagate(False)
        ctk.CTkLabel(self, text=texto, font=theme.FONTES["corpo_pequeno"], text_color=cor).pack(side="left", padx=(0, 14))
        if modo == "aviso":
            pulsar_fg(dot, cor, theme.mix(cor, theme.Cores.BG_MODAL, 0.2), periodo_ms=700)

    @classmethod
    def exibir(cls, main_window, texto: str, modo: str = "aviso", segundos: int = 4) -> "ToastReconexao":
        toast = cls(main_window, texto, modo)
        toast.place(relx=1.0, rely=1.0, anchor="se", x=-14, y=-44)
        main_window.after(segundos * 1000, toast.destroy)
        return toast


# --- vazios / espera ----------------------------------------------------------------

class EmptyForuns(ctk.CTkFrame):
    def __init__(self, master, on_fundar=None, on_aceitar=None, **kwargs) -> None:
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text="🜲", font=theme.glifo(46), text_color=theme.mix(theme.Cores.DOURADO, theme.Cores.BG_PROFUNDO, 0.7)).pack(pady=(0, 12))
        ctk.CTkLabel(self, text="Nenhum fórum reclama tua presença.\nFunde um novo pacto ou aceita uma convocação.",
                     font=(theme.FAMILIA_SERIFADA, 18, "italic"), text_color=theme.Cores.TEXTO, justify="center").pack(pady=(0, 16))
        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack()
        ctk.CTkButton(botoes, text="＋ FUNDAR FÓRUM", font=theme.FONTES["corpo_pequeno"], corner_radius=0,
                      fg_color=theme.Cores.DOURADO, text_color=theme.Cores.BG_PROFUNDO, hover_color=theme.Cores.TEXTO,
                      command=on_fundar or (lambda: None)).pack(side="left", padx=(0, 10))
        ctk.CTkButton(botoes, text="❖ ACEITAR CONVOCAÇÃO", font=theme.FONTES["corpo_pequeno"], corner_radius=0,
                      fg_color="transparent", border_width=1, border_color=theme.DOURADO_45,
                      text_color=theme.Cores.DOURADO, hover_color=theme.Cores.BG_MEDIO,
                      command=on_aceitar or (lambda: None)).pack(side="left")


class LanSemPeers(ctk.CTkFrame):
    def __init__(self, master, **kwargs) -> None:
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        alvo = ctk.CTkFrame(self, width=80, height=80, fg_color="transparent")
        alvo.pack(pady=(0, 15))
        alvo.pack_propagate(False)
        centro = ctk.CTkFrame(alvo, width=9, height=9, fg_color=theme.Cores.ERRO, corner_radius=0)
        centro.place(relx=0.5, rely=0.5, anchor="center")

        linha = ctk.CTkFrame(self, fg_color="transparent")
        linha.pack()
        ctk.CTkLabel(linha, text="LAN", font=theme.FONTES["label"], text_color=theme.Cores.ERRO,
                     fg_color=theme.mix(theme.Cores.CRIMSON, theme.Cores.BG_PROFUNDO, 0.1), corner_radius=0,
                     padx=8, pady=2).pack(side="left", padx=(0, 9))
        self._lbl = ctk.CTkLabel(linha, text="buscando outros corvos na rede local...", font=theme.FONTES["corpo_pequeno"], text_color=theme.Cores.TEXTO)
        self._lbl.pack(side="left")
        ctk.CTkLabel(self, text="O silêncio ecoa neste corredor.", font=(theme.FAMILIA_SERIFADA, 13, "italic"), text_color=theme.Cores.MUTED).pack(pady=(4, 0))

        info = ctk.CTkFrame(self, fg_color="transparent")
        info.pack(pady=(10, 0))
        ctk.CTkLabel(info, text="PORTA 9999", font=theme.FONTES["label"], text_color=theme.Cores.MUTED).pack(side="left", padx=8)
        ctk.CTkLabel(info, text="BROADCAST UDP", font=theme.FONTES["label"], text_color=theme.Cores.MUTED).pack(side="left", padx=8)
        self._varredura = ctk.CTkLabel(info, text="VARREDURA ATIVA", font=theme.FONTES["label"], text_color=theme.Cores.AVISO)
        self._varredura.pack(side="left", padx=8)
        pulsar(self._varredura, theme.Cores.AVISO, theme.mix(theme.Cores.AVISO, theme.Cores.BG_PROFUNDO, 0.3), periodo_ms=750)


class AguardandoAprovacao(ctk.CTkFrame):
    def __init__(self, master, on_cancelar=None, **kwargs) -> None:
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self._selo = ctk.CTkLabel(self, text="🜍", font=theme.glifo(27), text_color=theme.Cores.DOURADO)
        self._selo.pack(pady=(0, 14))
        pulsar(self._selo, theme.Cores.DOURADO, theme.mix(theme.Cores.DOURADO, theme.Cores.BG_PROFUNDO, 0.4), periodo_ms=900)
        ctk.CTkLabel(self, text="Aguardando o Corvo-Mor romper o selo...", font=(theme.FAMILIA_SERIFADA, 19, "italic"),
                     text_color=theme.Cores.TEXTO).pack()
        self._lbl = ctk.CTkLabel(self, text="CONVOCAÇÃO PENDENTE", font=theme.FONTES["label"], text_color=theme.Cores.MUTED)
        self._lbl.pack(pady=(4, 14))
        pulsar(self._lbl, theme.Cores.MUTED, theme.mix(theme.Cores.MUTED, theme.Cores.BG_PROFUNDO, 0.4), periodo_ms=1000)
        ctk.CTkButton(self, text="CANCELAR CONVOCAÇÃO", font=theme.FONTES["label"], corner_radius=0,
                      fg_color="transparent", border_width=1, border_color=theme.mix(theme.Cores.MUTED, theme.Cores.BG_PROFUNDO, 0.4),
                      text_color=theme.Cores.MUTED, hover_color=theme.Cores.BG_MEDIO,
                      command=on_cancelar or (lambda: None)).pack()


# --- janela de demonstracao (screenshot) --------------------------------------------

class EstadosDemo(ctk.CTk):
    """Grade com os estados lado a lado, so pra validacao visual/screenshot."""

    def __init__(self) -> None:
        ctk.set_appearance_mode("dark")
        super().__init__()
        theme.carregar_fontes()
        self.title("Corvo Negro — Estados")
        self.geometry("920x760")
        self.configure(fg_color=theme.Cores.BG_PROFUNDO)

        wrap = ctk.CTkScrollableFrame(self, fg_color=theme.Cores.BG_PROFUNDO, corner_radius=0)
        wrap.pack(fill="both", expand=True, padx=20, pady=20)
        grade = ctk.CTkFrame(wrap, fg_color="transparent")
        grade.pack(fill="both", expand=True)
        grade.grid_columnconfigure((0, 1), weight=1)

        def cartao(row, col, titulo, builder):
            c = ctk.CTkFrame(grade, fg_color=theme.CHAT_BG, border_width=1, border_color=theme.DOURADO_30, corner_radius=0)
            c.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)
            faixa = ctk.CTkFrame(c, fg_color=theme.CABECALHO_CARD, corner_radius=0, height=24)
            faixa.pack(fill="x")
            faixa.pack_propagate(False)
            ctk.CTkLabel(faixa, text=titulo, font=theme.FONTES["label"], text_color=theme.Cores.MUTED).pack(side="left", padx=12)
            corpo = ctk.CTkFrame(c, fg_color="transparent")
            corpo.pack(fill="both", expand=True, padx=16, pady=16)
            builder(corpo)

        cartao(0, 0, "A · SKELETON DO CHAT", lambda p: SkeletonChat(p).pack(fill="x"))
        cartao(0, 1, "B · SYNC AO RECONECTAR", lambda p: BannerSync(p, 47).pack(fill="x"))
        cartao(1, 0, "C · TOAST DE RECONEXÃO", self._build_toasts)
        cartao(1, 1, "D · AGUARDANDO APROVAÇÃO", lambda p: AguardandoAprovacao(p).pack(pady=10))
        cartao(2, 0, "E · SEM FÓRUNS", lambda p: EmptyForuns(p).pack(pady=10))
        cartao(2, 1, "F · MODO LAN SEM PEERS", lambda p: LanSemPeers(p).pack(pady=10))

    def _build_toasts(self, p) -> None:
        t1 = ToastReconexao(p, "Reconectando ao astropata... (tentativa 2/3)", "aviso")
        t1.pack(fill="x", pady=(10, 8))
        t2 = ToastReconexao(p, "Pacto restabelecido.", "sucesso")
        t2.pack(fill="x")
