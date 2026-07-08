"""Protocolo TCP do Corvo Negro: constantes de comandos e framing.

Framing:
    [4 bytes big-endian: tamanho do payload][payload JSON UTF-8]

Funcoes previstas (Sprint 1, Dia 2):
    pack_message(dict) -> bytes      # 4 bytes de tamanho + JSON
    unpack_message(sock) -> dict     # le tamanho, depois o payload
"""

# TODO(Sprint 1, Dia 2): constantes de comandos (CMD_REGISTER, CMD_LOGIN, ...)
#                        e funcoes de framing pack_message / unpack_message.
