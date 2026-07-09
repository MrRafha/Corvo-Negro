"""Ponte entre CorvoClient e a GUI orientada a eventos (Sprint 2, Dia 8).

client/cli_test.py resolve request->resposta com um `inbox.get(timeout=...)`
bloqueante logo apos cada `client.request(...)`, torcendo para que a proxima
mensagem da fila seja a resposta daquele comando. Isso quebra assim que um
evento de broadcast (ex.: NEW_MESSAGE) chega entre o request e a resposta —
e numa GUI orientada a eventos (loop `after()` do Tk) nao da pra bloquear a
thread principal esperando.

ClientBridge resolve isso separando cada item da inbox em duas categorias:
    - Response (cmd termina em "_RESPONSE", ou e "PONG"/"ECHO_RESPONSE"):
      resolve o callback mais antigo pendente para aquele comando base (FIFO
      por tipo de comando — seguro porque o servidor responde na ordem em que
      recebe, dentro de uma unica conexao).
    - Evento (qualquer outro cmd, incluindo "_DISCONNECTED"): despachado para
      os listeners registrados via `on(evt_name, callback)`.

Uso:
    bridge = ClientBridge(tk_root, client)
    bridge.start_polling()
    bridge.on(protocol.EVT_NEW_MESSAGE, handle_new_message)
    bridge.call(protocol.CMD_LOGIN, {"username": ..., "password": ...},
                on_ok=lambda data: ..., on_error=lambda msg: ...)
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Callable

from shared import protocol
from client.network.client_socket import CorvoClient

OkCallback = Callable[[dict], None]
ErrorCallback = Callable[[str], None]
EventCallback = Callable[[dict], None]

POLL_INTERVAL_MS = 30


def _base_command_from_response(cmd: str) -> str | None:
    """Deriva o comando base de um cmd de resposta (ex.: 'LOGIN_RESPONSE' -> 'LOGIN')."""
    if cmd.endswith("_RESPONSE"):
        return cmd[: -len("_RESPONSE")]
    if cmd == "PONG":
        return "PING"
    return None


class ClientBridge:
    """Encapsula um CorvoClient e drena a inbox sem bloquear a thread do Tk."""

    def __init__(self, tk_root, client: CorvoClient | None = None) -> None:
        self.tk_root = tk_root
        self.client = client if client is not None else CorvoClient()
        # comando base -> fila FIFO de (on_ok, on_error) pendentes.
        self._pending: dict[str, deque[tuple[OkCallback | None, ErrorCallback | None]]] = defaultdict(deque)
        # evento -> lista de listeners.
        self._listeners: dict[str, list[EventCallback]] = defaultdict(list)
        self._polling = False

    # --- ciclo de vida ----------------------------------------------------------

    def connect(self, timeout: float | None = None) -> None:
        if timeout is None:
            self.client.connect()
        else:
            self.client.connect(timeout)

    def start_polling(self) -> None:
        if self._polling:
            return
        self._polling = True
        self._poll()

    def stop_polling(self) -> None:
        self._polling = False

    def close(self) -> None:
        self.stop_polling()
        self.client.close()

    # --- registro de listeners de evento -----------------------------------------

    def on(self, event_name: str, callback: EventCallback) -> None:
        """Registra `callback` para ser chamado quando `event_name` chegar."""
        self._listeners[event_name].append(callback)

    # --- requests com callback assincrono -----------------------------------------

    def call(
        self,
        cmd: str,
        data: dict | None = None,
        on_ok: OkCallback | None = None,
        on_error: ErrorCallback | None = None,
    ) -> None:
        """Envia um request e registra callbacks para quando a resposta chegar.

        `on_ok(data)` e chamado se status == STATUS_OK; `on_error(message)`
        caso contrario. Nenhum dos dois bloqueia — sao invocados pelo poll
        loop na thread principal do Tk.
        """
        self._pending[cmd].append((on_ok, on_error))
        self.client.request(cmd, data)

    # --- drenagem da inbox --------------------------------------------------------

    def _poll(self) -> None:
        if not self._polling:
            return
        while True:
            try:
                message = self.client.inbox.get_nowait()
            except Exception:
                break
            self._dispatch(message)
        self.tk_root.after(POLL_INTERVAL_MS, self._poll)

    def _dispatch(self, message: dict) -> None:
        cmd = message.get("cmd", "")
        base_cmd = _base_command_from_response(cmd)

        if base_cmd is not None and self._pending.get(base_cmd):
            on_ok, on_error = self._pending[base_cmd].popleft()
            status = message.get("status")
            data = message.get("data", {}) or {}
            if status == protocol.STATUS_OK:
                if on_ok is not None:
                    on_ok(data)
            else:
                if on_error is not None:
                    on_error(message.get("message", ""))
            return

        # Nao e resposta a um request pendente: trata como evento (inclusive
        # "_DISCONNECTED" e respostas sem callback registrado, ex.: ECHO cru).
        for callback in self._listeners.get(cmd, []):
            callback(message.get("data", {}) or {})
