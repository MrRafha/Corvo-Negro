"""CLI de teste do cliente Corvo Negro (Sprint 1, Dia 2).

Conecta ao servidor e permite enviar comandos crus para exercitar o protocolo
antes da GUI existir. Imprime tudo que chega na inbox.

Uso:
    python -m client.cli_test

Comandos interativos:
    /ping                    -> envia PING (espera PONG)
    /echo <texto>            -> envia ECHO com {"texto": ...}
    /raw <CMD> <json_data>   -> envia um request cru: cmd + data (JSON)
    /quit                    -> encerra
"""

from __future__ import annotations

import json
import threading
import time

from client.network.client_socket import CorvoClient


def _print_inbox(client: CorvoClient, stop: threading.Event) -> None:
    """Drena a inbox e imprime as mensagens recebidas."""
    while not stop.is_set():
        try:
            msg = client.inbox.get(timeout=0.2)
        except Exception:
            continue
        if msg.get("cmd") == "_DISCONNECTED":
            print("\n[!] desconectado do servidor")
            stop.set()
            break
        print(f"\n<< {json.dumps(msg, ensure_ascii=False)}")
        print("> ", end="", flush=True)


def main() -> None:
    client = CorvoClient()
    try:
        client.connect()
    except OSError as exc:
        print(f"[!] nao conectou: {exc}")
        return
    print("[Corvo Negro] conectado. Comandos: /ping /echo /raw /quit")

    stop = threading.Event()
    printer = threading.Thread(target=_print_inbox, args=(client, stop), daemon=True)
    printer.start()

    try:
        while not stop.is_set():
            line = input("> ").strip()
            if not line:
                continue
            if line == "/quit":
                break
            elif line == "/ping":
                client.request("PING")
            elif line.startswith("/echo "):
                client.request("ECHO", {"texto": line[len("/echo "):]})
            elif line.startswith("/raw "):
                _, cmd, *rest = line.split(" ", 2)
                data = json.loads(rest[0]) if rest else {}
                client.request(cmd, data)
            else:
                print("comandos: /ping /echo <txt> /raw <CMD> <json> /quit")
            time.sleep(0.05)
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        stop.set()
        client.close()
        print("\nate a proxima, corvo.")


if __name__ == "__main__":
    main()
