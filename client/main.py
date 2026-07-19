"""Entry point da GUI do cliente Corvo Negro (Sprint 2).
m123
Fluxo: LoginWindow (janela raiz do Tk) -> SplashWindow (rito de boot, com
geracao real do par RSA na etapa 2) -> MainWindow.

No login/registro bem-sucedido a LoginWindow se esconde e sobe a Splash; ao
final do rito a Splash fecha e a MainWindow aparece. Ao fechar a MainWindow a
aplicacao encerra (reautenticar exige reiniciar o processo).

A LoginWindow ja carrega/gera o par RSA do usuario (do key_vault) antes de
chamar on_success — a etapa 2 da Splash serve de "cerimonia" visual e, quando
nenhuma chave existe ainda, tambem exercita a geracao real numa thread.
"""

from __future__ import annotations

import customtkinter as ctk

from client.network.gui_bridge import ClientBridge
from client.ui.app_state import AppState
from client.ui.login_window import LoginWindow
from client.ui.main_window import MainWindow
from client.ui.splash_window import SplashWindow
from client.ui.ui_helpers import instalar_atalho_destravar


def main() -> None:
    ctk.set_appearance_mode("dark")
    login = LoginWindow(on_success=_apos_login)
    instalar_atalho_destravar(login)  # Alt+R: destrava grab/foco preso por Alt+Tab, sem fechar a app
    login.mainloop()


def _apos_login(bridge: ClientBridge, state: AppState) -> None:
    login_window = bridge.tk_root  # a LoginWindow, que tambem e o Tk root
    login_window.withdraw()

    # A LoginWindow ja garantiu a chave privada em state.private_key_pem; a
    # Splash roda o rito de boot (e, se ainda faltasse chave, geraria — aqui
    # gerar_chaves=False porque ja temos). Ao terminar, abre a MainWindow.
    splash = SplashWindow(login_window, on_done=lambda: _abrir_main(login_window, bridge, state), gerar_chaves=False)
    splash.lift()


def _abrir_main(login_window, bridge: ClientBridge, state: AppState) -> None:
    main_window = MainWindow(login_window, bridge, state)
    main_window.lift()


if __name__ == "__main__":
    main()
