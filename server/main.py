"""Entry point do servidor Corvo Negro.

Socket TCP threaded: bind, listen, uma thread por cliente, loop recv que
despacha para o router. O servidor apenas ROTEIA mensagens cifradas -
jamais tem acesso ao conteudo em claro.

Sobe em 0.0.0.0:9999 por padrao (ver config.py).
"""

# TODO(Sprint 1, Dia 2): socket TCP + threading + loop de despacho.


def main() -> None:
    raise NotImplementedError("Servidor ainda nao implementado (Sprint 1, Dia 2).")


if __name__ == "__main__":
    main()
