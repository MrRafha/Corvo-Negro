"""Protocolo TCP do Corvo Negro: constantes de comandos e framing.

Framing:
    [4 bytes big-endian: tamanho do payload em bytes][payload JSON UTF-8]

Estrutura das mensagens (ver docs/protocol_spec.md):
    Request  (C->S): {"cmd": "...", "session_token": "opcional", "data": {...}}
    Response (S->C): {"cmd": "..._RESPONSE", "status": "ok|error", "message": "...", "data": {...}}
    Broadcast(S->C): {"cmd": "EVENT_NAME", "data": {...}}

Funcoes de framing:
    pack_message(dict) -> bytes      # 4 bytes de tamanho + JSON
    unpack_message(sock) -> dict     # le tamanho, depois o payload (ou None se fechou)
"""

from __future__ import annotations

import json
import socket
import struct

# --- Framing ------------------------------------------------------------------

LENGTH_PREFIX_SIZE = 4               # bytes do cabecalho de tamanho (uint32 big-endian)
MAX_PAYLOAD_SIZE = 16 * 1024 * 1024  # 16 MiB: teto de sanidade contra payloads absurdos

STATUS_OK = "ok"
STATUS_ERROR = "error"

# --- Comandos Cliente -> Servidor ---------------------------------------------

CMD_REGISTER = "REGISTER"
CMD_LOGIN = "LOGIN"
CMD_LOGOUT = "LOGOUT"
CMD_GET_PUBKEY = "GET_PUBKEY"
CMD_UPDATE_PUBKEY = "UPDATE_PUBKEY"
CMD_MSG_1V1 = "MSG_1V1"
CMD_CREATE_FORUM = "CREATE_FORUM"
CMD_JOIN_FORUM = "JOIN_FORUM"
CMD_LEAVE_FORUM = "LEAVE_FORUM"
CMD_LIST_MY_FORUMS = "LIST_MY_FORUMS"
CMD_GET_FORUM_MEMBERS = "GET_FORUM_MEMBERS"
CMD_DISTRIBUTE_KEY = "DISTRIBUTE_KEY"
CMD_SEND_TO_FORUM = "SEND_TO_FORUM"
CMD_GET_HISTORY = "GET_HISTORY"
CMD_SYNC_MESSAGES = "SYNC_MESSAGES"
CMD_CREATE_ROLE = "CREATE_ROLE"
CMD_UPDATE_ROLE = "UPDATE_ROLE"
CMD_DELETE_ROLE = "DELETE_ROLE"
CMD_LIST_ROLES = "LIST_ROLES"
CMD_ASSIGN_ROLE = "ASSIGN_ROLE"
CMD_PIN_MESSAGE = "PIN_MESSAGE"
CMD_DELETE_MESSAGE = "DELETE_MESSAGE"
CMD_REGENERATE_INVITE = "REGENERATE_INVITE"
CMD_UPDATE_FORUM = "UPDATE_FORUM"
CMD_DELETE_FORUM = "DELETE_FORUM"
CMD_KICK_MEMBER = "KICK_MEMBER"
CMD_BAN_MEMBER = "BAN_MEMBER"

# --- Eventos Servidor -> Cliente (broadcast) ----------------------------------

EVT_NEW_MESSAGE = "NEW_MESSAGE"
EVT_NEW_DM = "NEW_DM"
EVT_MEMBER_JOINED = "MEMBER_JOINED"
EVT_MEMBER_LEFT = "MEMBER_LEFT"
EVT_MESSAGE_PINNED = "MESSAGE_PINNED"
EVT_MESSAGE_DELETED = "MESSAGE_DELETED"
EVT_KEY_ROTATED = "KEY_ROTATED"
EVT_FORUM_UPDATED = "FORUM_UPDATED"
EVT_FORUM_DELETED = "FORUM_DELETED"
EVT_MEMBER_KICKED = "MEMBER_KICKED"
EVT_MEMBER_BANNED = "MEMBER_BANNED"
EVT_INVITE_REGENERATED = "INVITE_REGENERATED"
EVT_ROLE_UPDATED = "ROLE_UPDATED"
EVT_ROLE_DELETED = "ROLE_DELETED"


class ProtocolError(Exception):
    """Erro de enquadramento/serializacao do protocolo."""


def pack_message(message: dict) -> bytes:
    """Serializa `message` (dict) para o formato de fio: [tamanho][JSON].

    O JSON e UTF-8 e o prefixo e um uint32 big-endian com o numero de bytes
    do payload.
    """
    try:
        payload = json.dumps(message, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProtocolError(f"payload nao serializavel em JSON: {exc}") from exc
    if len(payload) > MAX_PAYLOAD_SIZE:
        raise ProtocolError(f"payload excede o teto de {MAX_PAYLOAD_SIZE} bytes")
    return struct.pack(">I", len(payload)) + payload


def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
    """Le exatamente `n` bytes do socket. Retorna None se a conexao fechar."""
    chunks = bytearray()
    while len(chunks) < n:
        chunk = sock.recv(n - len(chunks))
        if not chunk:  # peer fechou a conexao
            return None
        chunks.extend(chunk)
    return bytes(chunks)


def unpack_message(sock: socket.socket) -> dict | None:
    """Le uma mensagem completa do socket. Retorna o dict, ou None se fechou.

    Le primeiro os 4 bytes de tamanho, depois exatamente esse tanto de payload.
    Lanca ProtocolError se o tamanho for invalido ou o JSON estiver corrompido.
    """
    header = _recv_exact(sock, LENGTH_PREFIX_SIZE)
    if header is None:
        return None
    (length,) = struct.unpack(">I", header)
    if length == 0 or length > MAX_PAYLOAD_SIZE:
        raise ProtocolError(f"tamanho de payload invalido: {length}")
    payload = _recv_exact(sock, length)
    if payload is None:
        return None
    try:
        return json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProtocolError(f"payload nao e JSON UTF-8 valido: {exc}") from exc


# --- Helpers para montar mensagens padronizadas -------------------------------

def make_request(cmd: str, data: dict | None = None, session_token: str | None = None) -> dict:
    """Monta um dict de request C->S."""
    msg: dict = {"cmd": cmd, "data": data or {}}
    if session_token is not None:
        msg["session_token"] = session_token
    return msg


def make_response(cmd: str, status: str, message: str = "", data: dict | None = None) -> dict:
    """Monta um dict de response S->C. `cmd` costuma ser CMD_X + '_RESPONSE'."""
    return {"cmd": cmd, "status": status, "message": message, "data": data or {}}


def make_event(event: str, data: dict | None = None) -> dict:
    """Monta um dict de broadcast/evento S->C."""
    return {"cmd": event, "data": data or {}}
