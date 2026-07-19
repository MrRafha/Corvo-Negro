"""Testes do ConnectionManager: decisao ONLINE vs LAN no boot (Sprint 3).

Cobre:
    - conexao inicial bem sucedida chama on_online, nao ativa modo LAN
    - falha na conexao inicial (OSError) chama on_lan e ativa o modo LAN
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from client.network.connection_manager import ConnectionManager
from client.ui.app_state import AppState


class _BridgeFalso:
    def __init__(self, falha: bool) -> None:
        self._falha = falha
        self.start_polling = MagicMock()

    def connect(self, timeout=None):
        if self._falha:
            raise OSError("servidor inacessivel")


class _TkRootFalso:
    def after(self, _ms, fn=None):
        return 1  # id falso, so precisa ser hashable/cancelavel

    def after_cancel(self, _id):
        pass


def test_conexao_inicial_bem_sucedida_nao_ativa_lan():
    bridge = _BridgeFalso(falha=False)
    state = AppState(username="alice", user_id=1)
    mgr = ConnectionManager(bridge, state, _TkRootFalso())

    chamado = {"online": False, "lan": False}
    with patch.object(mgr, "ativar_modo_lan") as ativar_mock:
        mgr.tentar_conexao_inicial(
            on_online=lambda: chamado.__setitem__("online", True),
            on_lan=lambda: chamado.__setitem__("lan", True),
        )
    assert chamado["online"] is True
    assert chamado["lan"] is False
    ativar_mock.assert_not_called()
    bridge.start_polling.assert_called_once()


def test_conexao_inicial_falha_ativa_modo_lan():
    bridge = _BridgeFalso(falha=True)
    state = AppState(username="alice", user_id=1)
    mgr = ConnectionManager(bridge, state, _TkRootFalso())

    chamado = {"online": False, "lan": False}
    with patch.object(mgr, "ativar_modo_lan") as ativar_mock:
        mgr.tentar_conexao_inicial(
            on_online=lambda: chamado.__setitem__("online", True),
            on_lan=lambda: chamado.__setitem__("lan", True),
        )
    assert chamado["online"] is False
    assert chamado["lan"] is True
    ativar_mock.assert_called_once()
