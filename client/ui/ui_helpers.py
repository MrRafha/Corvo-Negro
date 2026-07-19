"""Widgets e animacoes reutilizaveis da GUI (Sprint 2, reconstrucao visual).

Centraliza os efeitos "coracao do visual" descritos em IMPLEMENTACAO.md secao 4:
    - decodificacao de mensagens (hash -> texto revelando char a char);
    - pulso (etapa ativa do boot, CONECTANDO, textos em espera);
    - cursor de bloco piscando;
    - divisor ornamental ("linha ✦ linha");
    - cantos angulares dourados do card de login;
    - bolinha de status QUADRADA (os mocks usam quadrados de 7px, nao circulos).

Tkinter nao tem CSS transitions: tudo via widget.after(ms, fn). O ritmo do
design e lento e pesado (65ms por passo de decodificacao, 550-800ms de pulso).
Todas as animacoes se auto-cancelam quando o widget e destruido (checam
winfo_exists antes de reagendar), pra nao vazar callbacks after().
"""

from __future__ import annotations

import ctypes
import random
import string
from typing import Callable

import customtkinter as ctk

from client.ui import theme

# Alfabeto do scramble (mesmo do mock: base64 + alguns glifos alquimicos).
GLIFOS_SCRAMBLE = string.ascii_letters + string.digits + "+/=§🜲🜍☿⚜✦"

INTERVALO_DECODIFICACAO_MS = 65
PASSO_DECODIFICACAO = 2
MAX_SCRAMBLE = 140


def scramble(tamanho: int) -> str:
    """Gera `tamanho` (cap 140) caracteres aleatorios do alfabeto de cifra."""
    tamanho = max(0, min(tamanho, MAX_SCRAMBLE))
    return "".join(random.choice(GLIFOS_SCRAMBLE) for _ in range(tamanho))


def _vivo(widget) -> bool:
    try:
        return bool(widget.winfo_exists())
    except Exception:
        return False


class LabelDecodificavel(ctk.CTkLabel):
    """CTkLabel que revela um texto animando hash -> texto (a assinatura do app).

    A parte ja revelada fica em `cor_revelada`; o resto e scramble na cor
    `cor_cifra`. Como um unico CTkLabel so tem uma cor de texto, aproximamos
    concatenando os dois trechos e pintando o label inteiro com `cor_revelada`
    (o scramble e o "rastro" e some rapido — na pratica le como no mock).
    """

    def __init__(self, master, texto: str, *, cor_revelada: str = theme.Cores.TEXTO, **kwargs) -> None:
        kwargs.setdefault("font", theme.FONTES["corpo"])
        kwargs.setdefault("justify", "left")
        kwargs.setdefault("anchor", "w")
        super().__init__(master, text="", text_color=cor_revelada, **kwargs)
        self._texto_final = texto
        self._pos = 0

    def revelar(self) -> None:
        self._pos = 0
        self._tick()

    def _tick(self) -> None:
        if not _vivo(self):
            return
        self._pos = min(len(self._texto_final), self._pos + PASSO_DECODIFICACAO)
        resto = len(self._texto_final) - self._pos
        self.configure(text=self._texto_final[: self._pos] + scramble(resto))
        if self._pos < len(self._texto_final):
            self.after(INTERVALO_DECODIFICACAO_MS, self._tick)


def pulsar(widget, cor_a: str, cor_b: str, periodo_ms: int = 800) -> None:
    """Alterna text_color de `widget` entre cor_a/cor_b a cada periodo_ms.

    Guarda o id do after em widget._pulso; cancele com parar_pulso(widget).
    """
    estado = {"flag": True}

    def ciclo() -> None:
        if not _vivo(widget):
            return
        widget.configure(text_color=cor_a if estado["flag"] else cor_b)
        estado["flag"] = not estado["flag"]
        widget._pulso = widget.after(periodo_ms, ciclo)

    ciclo()


def pulsar_fg(widget, cor_a: str, cor_b: str, periodo_ms: int = 800) -> None:
    """Como pulsar(), mas alterna fg_color — para frames/pontos de status."""
    estado = {"flag": True}

    def ciclo() -> None:
        if not _vivo(widget):
            return
        widget.configure(fg_color=cor_a if estado["flag"] else cor_b)
        estado["flag"] = not estado["flag"]
        widget._pulso = widget.after(periodo_ms, ciclo)

    ciclo()


def parar_pulso(widget) -> None:
    pulso = getattr(widget, "_pulso", None)
    if pulso is not None and _vivo(widget):
        try:
            widget.after_cancel(pulso)
        except Exception:
            pass
        widget._pulso = None


class CursorBloco(ctk.CTkLabel):
    """Cursor de bloco '█' dourado piscando (steps, sem fade) a cada 550ms.

    Alterna a COR do glifo entre `cor` e a cor do fundo (`cor_fundo`) — Tk/CTk
    nao aceita text_color="transparent", entao "apagamos" pintando com o fundo.
    """

    def __init__(self, master, cor: str = theme.Cores.DOURADO, periodo_ms: int = 550,
                 cor_fundo: str = theme.Cores.BG_PROFUNDO, **kwargs) -> None:
        kwargs.setdefault("font", theme.FONTES["corpo"])
        super().__init__(master, text="█", text_color=cor, **kwargs)
        self._cor = cor
        self._cor_fundo = cor_fundo
        self._visivel = True
        self._periodo = periodo_ms
        self._piscar()

    def _piscar(self) -> None:
        if not _vivo(self):
            return
        self._visivel = not self._visivel
        self.configure(text_color=self._cor if self._visivel else self._cor_fundo)
        self.after(self._periodo, self._piscar)


class DivisorOrnamental(ctk.CTkFrame):
    """Divisor '──── ✦ ────' com duas linhas de 1px e um glifo central."""

    def __init__(self, master, largura: int | None = None, glifo_central: str = "✦",
                 cor_linha: str = theme.DOURADO_30, cor_glifo: str = theme.Cores.MUTED, **kwargs) -> None:
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        esq = ctk.CTkFrame(self, height=1, fg_color=cor_linha, corner_radius=0)
        esq.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkLabel(self, text=glifo_central, font=theme.glifo(9), text_color=cor_glifo).pack(side="left")
        dir_ = ctk.CTkFrame(self, height=1, fg_color=cor_linha, corner_radius=0)
        dir_.pack(side="left", fill="x", expand=True, padx=(8, 0))
        if largura is not None:
            self.configure(width=largura)


def cantos_dourados(card: ctk.CTkFrame, tamanho: int = 13, espessura: int = 2,
                    cor: str = theme.Cores.DOURADO) -> None:
    """Desenha os 4 cantos angulares em L (dourados) por cima de `card`.

    Reproduz os 4 <div> com border-top/left etc. do Login.dc.html. Cada canto
    e um par de finas barras (uma horizontal, uma vertical) posicionadas com
    place() nos cantos absolutos do card.
    """
    def barra(w: int, h: int, relx: float, rely: float, anchor: str) -> None:
        f = ctk.CTkFrame(card, width=w, height=h, fg_color=cor, corner_radius=0)
        f.place(relx=relx, rely=rely, anchor=anchor)
        f.lift()

    for relx, rely, anchor in [(0, 0, "nw"), (1, 0, "ne"), (0, 1, "sw"), (1, 1, "se")]:
        barra(tamanho, espessura, relx, rely, anchor)  # perna horizontal
        barra(espessura, tamanho, relx, rely, anchor)  # perna vertical


class PontoStatus(ctk.CTkFrame):
    """Bolinha de status QUADRADA de 7px (os mocks usam quadrados, nao circulos)."""

    def __init__(self, master, cor: str, tamanho: int = 7, **kwargs) -> None:
        kwargs.setdefault("fg_color", cor)
        kwargs.setdefault("corner_radius", 0)
        super().__init__(master, width=tamanho, height=tamanho, **kwargs)
        self.pack_propagate(False)
        self.grid_propagate(False)


ESPACAMENTO_SCANLINE = 3
_SCANLINE_ALPHA = 0.05  # bem sutil: mais que isso comeca a brigar com o texto por cima


def desenhar_scanlines(canvas: ctk.CTkCanvas, w: int, h: int,
                       cor: str = theme.Cores.DOURADO, cor_fundo: str = theme.Cores.BG_PROFUNDO) -> None:
    """Sobrepoe scanlines horizontais douradas (efeito CRT) num canvas ja pintado.

    Chame DEPOIS de pintar o gradiente de fundo (create_oval) e ANTES de criar
    qualquer conteudo com .place()/frames filhos — como scanlines sao itens do
    proprio Canvas (nao widgets), qualquer widget filho ja fica na frente delas
    automaticamente, sem precisar de tag_raise/lower entre as duas camadas.

    Linhas alternadas (1px dourado translucido / 1px vazio) a cada
    ESPACAMENTO_SCANLINE px imitam a varredura de um tubo CRT sem exigir canal
    alpha (Tk nao tem): pre-misturamos a cor contra o fundo escuro via mix().
    Estatico — redesenhado so no resize (mesmo bind de <Configure> do gradiente),
    nunca por frame, porque a tela nao anima constantemente.
    """
    canvas.delete("scanlines")
    cor_linha = theme.mix(cor, cor_fundo, _SCANLINE_ALPHA)
    for y in range(0, h, ESPACAMENTO_SCANLINE):
        canvas.create_line(0, y, w, y, fill=cor_linha, width=1, tags="scanlines")
    canvas.tag_raise("scanlines", "bg")


def tornar_arrastavel(faixa, janela: ctk.CTkToplevel | ctk.CTk) -> None:
    """Torna `janela` arrastavel pela `faixa` (necessario com overrideredirect,
    que remove a barra de titulo nativa do SO e o arraste que ela dava de graca).
    """
    estado = {"x": 0, "y": 0}

    def iniciar(event):
        estado["x"] = event.x
        estado["y"] = event.y

    def mover(event):
        x = janela.winfo_x() + (event.x - estado["x"])
        y = janela.winfo_y() + (event.y - estado["y"])
        janela.geometry(f"+{x}+{y}")

    faixa.bind("<ButtonPress-1>", iniciar)
    faixa.bind("<B1-Motion>", mover)


def barra_titulo_modal(
    pai, texto: str, on_fechar: Callable[[], None] | None = None,
    janela: ctk.CTkToplevel | ctk.CTk | None = None,
    on_minimizar: Callable[[], None] | None = None,
) -> ctk.CTkFrame:
    """Faixa superior '▸ RITUS // ...' + '✕' dos modais/janelas sem moldura do SO.

    Se `janela` for informada, a faixa vira arrastavel (arraste a "barra de
    titulo" customizada para mover a janela, ja que overrideredirect tira essa
    funcionalidade nativa). `on_minimizar`, se informado, adiciona um botao "─".
    """
    faixa = ctk.CTkFrame(pai, fg_color=theme.CABECALHO_MODAL, corner_radius=0, height=26)
    faixa.pack(fill="x")
    faixa.pack_propagate(False)
    label = ctk.CTkLabel(faixa, text=texto, font=theme.FONTES["label"], text_color=theme.Cores.MUTED)
    label.pack(side="left", padx=12, pady=5)

    fechar = ctk.CTkButton(
        faixa, text="✕", width=22, height=22, font=theme.FONTES["label"],
        fg_color="transparent", text_color=theme.Cores.MUTED, corner_radius=0,
        hover_color=theme.mix(theme.Cores.CRIMSON, theme.Cores.BG_MODAL, 0.2),
        command=on_fechar if on_fechar else lambda: None,
    )
    fechar.pack(side="right", padx=4, pady=2)

    if on_minimizar is not None:
        minimizar = ctk.CTkButton(
            faixa, text="─", width=22, height=22, font=theme.FONTES["label"],
            fg_color="transparent", text_color=theme.Cores.MUTED, corner_radius=0,
            hover_color=theme.Cores.BG_MEDIO, command=on_minimizar,
        )
        minimizar.pack(side="right", padx=0, pady=2)

    if janela is not None:
        tornar_arrastavel(faixa, janela)
        tornar_arrastavel(label, janela)

    return faixa


def centralizar_toplevel(top: ctk.CTkToplevel, master, largura: int, altura: int) -> None:
    """Dimensiona e centraliza um CTkToplevel sobre a janela `master`.

    Se a `altura` pedida nao couber na tela (menos uma margem de folga), usa a
    altura disponivel — evita botoes cortados fora da area visivel quando o
    conteudo de um modal e mais alto do que o valor fixo original previa.
    """
    top.update_idletasks()
    altura_disponivel = top.winfo_screenheight() - 80
    altura = min(altura, altura_disponivel) if altura_disponivel > 200 else altura
    top.geometry(f"{largura}x{altura}")
    top.update_idletasks()
    x = master.winfo_rootx() + (master.winfo_width() - largura) // 2
    y = master.winfo_rooty() + (master.winfo_height() - altura) // 2
    top.geometry(f"+{max(x, 0)}+{max(y, 0)}")


def maximizar_sem_moldura(janela: ctk.CTkToplevel | ctk.CTk) -> None:
    """Ocupa a tela inteira numa janela com overrideredirect (sem moldura do SO).

    `state('zoomed')` do Tk nao funciona com overrideredirect no Windows —
    por isso posicionamos manualmente com a geometria da area de trabalho.
    """
    janela.update_idletasks()
    w = janela.winfo_screenwidth()
    h = janela.winfo_screenheight()
    janela.geometry(f"{w}x{h}+0+0")


_GWL_EXSTYLE = -20
_WS_EX_APPWINDOW = 0x00040000
_WS_EX_TOOLWINDOW = 0x00000080


def forcar_icone_taskbar(janela: ctk.CTkToplevel | ctk.CTk) -> None:
    """Garante icone na barra de tarefas do Windows para janelas overrideredirect.

    overrideredirect(True) tira a janela do gerenciamento do Explorer, que por
    padrao a trata como WS_EX_TOOLWINDOW (sem entrada na taskbar). Trocamos o
    extended style via user32 para WS_EX_APPWINDOW, que forca a entrada normal.
    """
    try:
        hwnd = ctypes.windll.user32.GetParent(janela.winfo_id())
        estilo = ctypes.windll.user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
        estilo = (estilo & ~_WS_EX_TOOLWINDOW) | _WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, estilo)
        janela.withdraw()
        janela.after(10, janela.deiconify)
    except Exception:
        pass


_GRAB_POLL_MS = 250


def grab_seguro(janela: ctk.CTkToplevel) -> None:
    """grab_set() que se solta sozinho quando o SO tira o foco da aplicacao
    inteira (Alt+Tab) e recaptura quando ele volta.

    Janelas overrideredirect nao participam do gerenciamento normal do
    Explorer, entao os eventos <FocusOut>/<FocusIn> do Tk (que tambem disparam
    ao trocar foco ENTRE WIDGETS FILHOS, ex.: clicar num Entry) nao dao pra
    usar diretamente sem falsos positivos. Comparar HWNDs via ctypes
    (GetForegroundWindow) tambem se mostrou fragil (GetParent/GetAncestor nao
    batem de forma confiavel com o HWND top-level do Tk em todas as
    configuracoes). `focus_displayof()` do proprio Tk resolve isso: retorna
    o widget em foco enquanto a aplicacao tem foco do SO, e None assim que
    QUALQUER outra aplicacao (nao so widgets internos) rouba o foco.
    """
    estado = {"solto": False}

    def _checar():
        if not _vivo(janela):
            return
        em_foco = janela.focus_displayof() is not None
        try:
            if em_foco and estado["solto"]:
                janela.grab_set()
                # janelas overrideredirect nao voltam pra frente sozinhas
                # quando o SO devolve o foco via Alt+Tab (o Windows traz o
                # processo de volta, mas o Toplevel "transient" pode ficar
                # visualmente atras da janela-mae, ainda que continue
                # recebendo eventos de teclado por causa do grab).
                janela.lift()
                janela.focus_force()
                estado["solto"] = False
            elif not em_foco and not estado["solto"]:
                janela.grab_release()
                estado["solto"] = True
        except Exception:
            pass
        janela.after(_GRAB_POLL_MS, _checar)

    janela.grab_set()
    janela.after(_GRAB_POLL_MS, _checar)


_TELA_RECARREGAMENTO_MS = 400


class TelaRecarregamento(ctk.CTkToplevel):
    """Overlay full-screen "Recarregando..." mostrado durante destravar_ui().

    Cobre a tela inteira por cima de qualquer janela presa/invisivel, dando
    feedback visual de que algo esta acontecendo, e se fecha sozinho quando
    `destravar_ui` termina de recapturar grab/foco — nao antes de um tempo
    minimo (`_TELA_RECARREGAMENTO_MS`), pra nao soh "piscar" quando a
    destravagem e instantanea.
    """

    def __init__(self, master: ctk.CTk) -> None:
        super().__init__(master)
        self.overrideredirect(True)
        self.configure(fg_color=theme.Cores.BG_PROFUNDO)
        self.attributes("-alpha", 0.96)
        self.after(10, lambda: maximizar_sem_moldura(self))

        centro = ctk.CTkFrame(self, fg_color="transparent")
        centro.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(centro, text="🜲", font=theme.glifo(34), text_color=theme.Cores.DOURADO).pack()
        linha = ctk.CTkFrame(centro, fg_color="transparent")
        linha.pack(pady=(14, 0))
        lbl = ctk.CTkLabel(linha, text="Recarregando a interface...", font=theme.FONTES["corpo"], text_color=theme.Cores.MUTED)
        lbl.pack(side="left")
        CursorBloco(linha, periodo_ms=400, cor_fundo=theme.Cores.BG_PROFUNDO).pack(side="left", padx=(6, 0))
        pulsar(lbl, theme.Cores.MUTED, theme.mix(theme.Cores.MUTED, theme.Cores.BG_PROFUNDO, 0.4), periodo_ms=700)

        self.lift()
        self.focus_force()

    def fechar(self) -> None:
        if _vivo(self):
            try:
                self.destroy()
            except Exception:
                pass


def destravar_ui(raiz: ctk.CTk) -> None:
    """Atalho de emergencia (Alt+R): solta qualquer grab_set() preso e traz
    a janela correta de volta ao topo/foco, sem destruir nenhum widget nem
    tocar em sessao/conexao de rede.

    Cobre a classe de bug de janelas overrideredirect que ficam "presas"
    (grab ativo mas invisivel, ou grab nunca solto) apos um Alt+Tab em
    timing ruim — mesmo com grab_seguro() aplicado nos modais, o polling de
    250ms pode nao pegar todo caso. Isto e a rede de seguranca manual.

    Mostra uma `TelaRecarregamento` por cima de tudo enquanto o destravamento
    acontece, pra dar feedback visual do processo mesmo quando a janela alvo
    ainda esta invisivel no momento do Alt+R.

    `raiz` e o Tk root (a LoginWindow, que fica viva e escondida durante
    toda a sessao) — todos os Toplevel da aplicacao (Splash, MainWindow,
    modais) aparecem em `raiz.winfo_children()`, independente de quao
    aninhados estejam visualmente via `transient()`.
    """
    try:
        toplevels = [w for w in raiz.winfo_children() if isinstance(w, (ctk.CTkToplevel,))]
    except Exception:
        return

    overlay = TelaRecarregamento(raiz)

    for tl in toplevels:
        if tl is overlay or not _vivo(tl):
            continue
        try:
            tl.grab_release()
        except Exception:
            pass

    # a ultima janela viva na ordem de criacao (exceto o proprio overlay) e a
    # que provavelmente deveria estar no topo (modal mais recente, ou a
    # MainWindow se nao ha modal).
    vivas = [tl for tl in toplevels if tl is not overlay and _vivo(tl)]
    alvo = vivas[-1] if vivas else (raiz if _vivo(raiz) else None)

    def _concluir():
        if alvo is not None:
            try:
                alvo.lift()
                alvo.focus_force()
                if isinstance(alvo, ctk.CTkToplevel) and alvo.winfo_viewable():
                    alvo.grab_set()
            except Exception:
                pass
        overlay.fechar()

    raiz.after(_TELA_RECARREGAMENTO_MS, _concluir)


def instalar_atalho_destravar(raiz: ctk.CTk, tecla: str = "<Alt-r>") -> None:
    """Registra o atalho global (default Alt+R) que chama `destravar_ui`."""
    raiz.bind_all(tecla, lambda _e: destravar_ui(raiz))


def montar_janela_sem_moldura(
    janela: ctk.CTkToplevel | ctk.CTk, titulo_texto: str, on_fechar: Callable[[], None], row: int = 0, coluna: int = 0,
) -> None:
    """Barra de titulo customizada completa para uma janela de nivel superior
    (MainWindow/LoginWindow): faixa arrastavel com titulo + minimizar + fechar,
    maximiza sem moldura e forca o icone na barra de tarefas do Windows.

    `janela` precisa ja ter overrideredirect(True) e um grid configurado; esta
    funcao ocupa `row`/`coluna` da grade com a faixa de 28px.
    """
    barra = ctk.CTkFrame(janela, height=28, fg_color=theme.CABECALHO_CARD, corner_radius=0)
    barra.grid(row=row, column=coluna, sticky="ew")
    barra.grid_propagate(False)

    titulo = ctk.CTkLabel(barra, text=titulo_texto, font=theme.FONTES["label"], text_color=theme.Cores.MUTED)
    titulo.pack(side="left", padx=12)

    def _minimizar() -> None:
        # overrideredirect esconde a janela do gerenciador de tarefas nativo;
        # 'iconify' ainda funciona, mas precisa desligar overrideredirect um
        # instante (limitacao conhecida do Tk no Windows).
        janela.overrideredirect(False)
        janela.iconify()

        def _restaurar(_event=None):
            if janela.state() == "normal":
                janela.overrideredirect(True)
                janela.unbind("<Map>")
                forcar_icone_taskbar(janela)

        janela.bind("<Map>", _restaurar, add="+")

    ctk.CTkButton(
        barra, text="✕", width=32, height=24, font=theme.FONTES["label"],
        fg_color="transparent", text_color=theme.Cores.MUTED, corner_radius=0,
        hover_color=theme.mix(theme.Cores.CRIMSON, theme.Cores.BG_PAINEL, 0.3),
        command=on_fechar,
    ).pack(side="right", padx=(0, 2), pady=2)
    ctk.CTkButton(
        barra, text="─", width=32, height=24, font=theme.FONTES["label"],
        fg_color="transparent", text_color=theme.Cores.MUTED, corner_radius=0,
        hover_color=theme.Cores.BG_MEDIO, command=_minimizar,
    ).pack(side="right", padx=0, pady=2)

    tornar_arrastavel(barra, janela)
    tornar_arrastavel(titulo, janela)

    janela.overrideredirect(True)
    janela.after(10, lambda: maximizar_sem_moldura(janela))
    janela.after(20, lambda: forcar_icone_taskbar(janela))
