"""Paleta grimdark, fontes e helpers visuais da GUI (Sprint 2, Dia 8).

Tokens de cor e tipografia extraidos do design ("Corvo Negro briefing design",
Claude Design) e do guia IMPLEMENTACAO.md do proprio usuario. Nunca use cores
fora da classe Cores — centraliza aqui para toda a GUI ficar consistente.

Regra geral do design: corner_radius=0 em tudo. Nada arredondado.
"""

from __future__ import annotations

import sys
from pathlib import Path

import customtkinter as ctk

# Rodando do codigo-fonte, ASSETS_DIR fica ao lado deste arquivo. Empacotado
# com PyInstaller (--onefile), os arquivos de dados sao extraidos para uma
# pasta temporaria exposta em sys._MEIPASS — sem esse desvio, o executavel
# nao acha fontes/imagens porque __file__ aponta pra dentro do zip embutido.
if hasattr(sys, "_MEIPASS"):
    ASSETS_DIR = Path(sys._MEIPASS) / "client" / "assets"
else:
    ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"


class Cores:
    BG_PROFUNDO = "#0a0a0a"   # fundo principal / janela
    BG_PAINEL = "#101010"     # sidebars, cabecalho, rodape de input
    BG_MEDIO = "#1a1a1a"      # inputs, cards de skeleton, item ativo
    BG_ELEVADO = "#2a2a2a"    # bordas de inputs, thumbs de scrollbar
    BG_MODAL = "#141414"      # corpo de modais

    CRIMSON = "#8b0000"       # botao de login, badges de nao-lidas, destrutivo
    DOURADO = "#c9a961"       # accent principal: titulos, bordas ativas, CTAs
    TEXTO = "#e5d4a1"         # texto principal
    MUTED = "#7a6d4a"         # texto secundario, labels, placeholders
    SUCESSO = "#4a7c3a"       # online, etapas concluidas
    ERRO = "#a83232"          # erros, modo LAN, dissolver ordem
    AVISO = "#b8860b"         # conectando, sync, rotacao de chave

    # cores de role (paleta do modal de Ordens)
    ROLE_DOURADO = "#c9a961"  # Corvo-Mor
    ROLE_PRATA = "#b0b0b8"    # Escriba
    ROLE_BEGE = "#c9b98a"     # Iniciado
    ROLE_CRIMSON = "#8b0000"
    ROLE_VERDE = "#4a7c3a"
    ROLE_ROXO = "#6b4a7c"


def mix(fg: str, bg: str, alpha: float) -> str:
    """Pre-mistura `fg` sobre `bg` com opacidade `alpha` (0-1).

    Tkinter nao suporta cores com canal alpha (rgba); os mockups usam dourado
    translucido para bordas discretas, entao pre-misturamos a cor final aqui.
    """
    f = [int(fg[i : i + 2], 16) for i in (1, 3, 5)]
    b = [int(bg[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(a * alpha + c * (1 - alpha)):02x}" for a, c in zip(f, b))


DOURADO_30 = mix(Cores.DOURADO, Cores.BG_PROFUNDO, 0.30)  # bordas discretas
DOURADO_55 = mix(Cores.DOURADO, Cores.BG_PROFUNDO, 0.55)  # borda de foco
CRIMSON_10 = mix(Cores.CRIMSON, Cores.BG_PROFUNDO, 0.10)  # hover de item de lista

# Tokens derivados usados repetidamente pelas telas (pre-misturados sobre o
# fundo de cada painel, ja que Tk nao tem canal alpha).
DOURADO_18 = mix(Cores.DOURADO, Cores.BG_PROFUNDO, 0.18)   # bordas ainda mais discretas
DOURADO_45 = mix(Cores.DOURADO, Cores.BG_PROFUNDO, 0.45)   # bordas de botoes outline
CABECALHO_MODAL = mix(Cores.DOURADO, Cores.BG_MODAL, 0.05)   # faixa "▸ RITUS //" dos modais
CABECALHO_CARD = mix(Cores.DOURADO, Cores.BG_PAINEL, 0.05)   # faixa "▸ COGITATOR //"
MSG_PROPRIA_BG = mix(Cores.DOURADO, Cores.BG_PROFUNDO, 0.045)  # fundo da mensagem propria
ITEM_HOVER_CRIMSON = mix(Cores.CRIMSON, Cores.BG_PROFUNDO, 0.10)  # hover de item de forum
FIXADO_BG = mix(Cores.DOURADO, Cores.BG_PROFUNDO, 0.045)     # fundo da mensagem fixada
CHAT_BG = "#0d0d0d"                                          # fundo da area central de chat
TAB_INATIVA_BG = "#0d0d0d"                                   # aba nao selecionada no login
CIPHER_SCRAMBLE = "#8a7a4e"     # cor do texto ainda cifrado (scramble) nas mensagens
CIPHER_TEXTO = "#d9bd7e"        # cor do base64 no cipher viewer
MEMBRO_OFFLINE = "#4a4a4a"      # bolinha de status offline
MEMBRO_OFFLINE_TXT = "#6a6a70"  # nome de membro offline

# Fonte que cobre os glifos alquimicos (blocos U+1F7xx, U+2600). No Windows a
# "Segoe UI Symbol" cobre a maioria; centralizamos aqui para trocar num lugar so.
FAMILIA_GLIFOS = "Segoe UI Symbol"


def glifo(size: int) -> tuple[str, int]:
    """Fonte para glifos alquimicos unicode (🜲⚜⚔☿🜍...) num tamanho dado."""
    return (FAMILIA_GLIFOS, size)


# --- Tipografia -----------------------------------------------------------------
# VT323 para tudo que e "terminal/UI" (mensagens, botoes, labels, timestamps).
# Cormorant Garamond para titulos ritualisticos (nomes de forum, titulos de
# modal, "CORVO NEGRO"). VT323 precisa de tamanhos maiores que uma sans normal.
#
# Nota tecnica: cada peso estatico de Cormorant Garamond foi baixado como arquivo
# separado (nao a variable font) porque o Windows/Tk so alterna Regular<->Bold
# corretamente quando os dois pesos compartilham o MESMO nome de familia (nameID
# 1). Os pesos Medium/SemiBold vem em arquivos que se registram sob um nome de
# familia proprio ("Cormorant Garamond Medium"/"...SemiBold") — por isso useo
# nome completo abaixo para pedir esses pesos, e so "Cormorant Garamond" + bold=True
# para alternar entre Regular e Bold.

FAMILIA_SERIFADA = "Cormorant Garamond"
FAMILIA_SERIFADA_MEDIUM = "Cormorant Garamond Medium"
FAMILIA_SERIFADA_MEDIUM_ITALIC = "Cormorant Garamond Medium"  # slant="italic" junto

FONTES = {
    "titulo_splash": (FAMILIA_SERIFADA, 42, "bold"),
    "titulo_modal": (FAMILIA_SERIFADA, 24, "bold"),
    "titulo_forum": (FAMILIA_SERIFADA, 21, "bold"),
    "titulo_pequeno": (FAMILIA_SERIFADA, 15, "bold"),
    "subtitulo_medium": (FAMILIA_SERIFADA_MEDIUM, 16),  # ex.: frase em italico do splash
    "corpo": ("VT323", 17),
    "corpo_pequeno": ("VT323", 15),
    "label": ("VT323", 13),
    "mono_fallback": ("JetBrains Mono", 11),
}

_FONT_FILES = [
    "VT323-Regular.ttf",
    "CormorantGaramond-Regular.ttf",
    "CormorantGaramond-Medium.ttf",
    "CormorantGaramond-SemiBold.ttf",
    "CormorantGaramond-Bold.ttf",
    "CormorantGaramond-MediumItalic.ttf",
    "JetBrainsMono-Regular.ttf",
]

_fontes_carregadas = False


def carregar_fontes() -> None:
    """Registra os .ttf de assets/fonts no sistema de fontes do Tk.

    Idempotente. Deve ser chamada uma unica vez, antes de criar qualquer
    widget que use as fontes acima (senao o Tk cai no fallback do SO).
    """
    global _fontes_carregadas
    if _fontes_carregadas:
        return
    for filename in _FONT_FILES:
        path = FONTS_DIR / filename
        if path.exists():
            ctk.FontManager.load_font(str(path))
    _fontes_carregadas = True
