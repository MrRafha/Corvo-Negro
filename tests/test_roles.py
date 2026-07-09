"""Testes de roles e permissoes bitmask (Sprint 1, Dia 7).

Cobre:
    - criar forum ja cria as 3 roles padrao e atribui Corvo-Mor ao dono
    - entrar num forum atribui a role Iniciado automaticamente
    - create_role exige MANAGE_ROLES (dono pode, membro comum nao)
    - assign_role exige MANAGE_ROLES e valida membro/role do mesmo forum
    - permissao concedida por uma role customizada e respeitada (pin_message)
    - membro sem DELETE_MESSAGE nao apaga mensagem alheia, mas apaga a propria
    - has_permission / combine_masks (shared/permissions.py) isolados
"""

import socket
import threading

import pytest

from shared import permissions, protocol
from server.main import CorvoServer
from client.network.client_socket import CorvoClient


# --- unidade: shared/permissions.py -------------------------------------------

def test_has_permission_flag_presente():
    mask = permissions.Permission.SEND_MESSAGE | permissions.Permission.PIN_MESSAGE
    assert permissions.has_permission(mask, permissions.Permission.SEND_MESSAGE)
    assert permissions.has_permission(mask, permissions.Permission.PIN_MESSAGE)
    assert not permissions.has_permission(mask, permissions.Permission.BAN_MEMBER)


def test_combine_masks():
    combined = permissions.combine_masks(
        [permissions.Permission.SEND_MESSAGE, permissions.Permission.KICK_MEMBER]
    )
    assert permissions.has_permission(combined, permissions.Permission.SEND_MESSAGE)
    assert permissions.has_permission(combined, permissions.Permission.KICK_MEMBER)
    assert not permissions.has_permission(combined, permissions.Permission.BAN_MEMBER)


def test_permission_all_contem_todas():
    for flag in [
        permissions.Permission.SEND_MESSAGE,
        permissions.Permission.DELETE_MESSAGE,
        permissions.Permission.PIN_MESSAGE,
        permissions.Permission.SEND_IMAGE,
        permissions.Permission.CREATE_CHANNEL,
        permissions.Permission.KICK_MEMBER,
        permissions.Permission.BAN_MEMBER,
        permissions.Permission.MANAGE_ROLES,
        permissions.Permission.MANAGE_FORUM,
    ]:
        assert permissions.has_permission(permissions.Permission.ALL, flag)


# --- fixture -----------------------------------------------------------------

@pytest.fixture
def servidor():
    server = CorvoServer(host="127.0.0.1", port=0, db_path=":memory:")
    server._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server._server_sock.bind(("127.0.0.1", 0))
    server.port = server._server_sock.getsockname()[1]
    server._server_sock.listen()
    server._running.set()

    def _accept():
        while server._running.is_set():
            try:
                sock, addr = server._server_sock.accept()
            except OSError:
                break
            threading.Thread(target=server._handle_client, args=(sock, addr), daemon=True).start()

    threading.Thread(target=_accept, daemon=True).start()
    yield server
    server.stop()


def _cliente(servidor) -> CorvoClient:
    c = CorvoClient(host="127.0.0.1", port=servidor.port)
    c.connect()
    return c


def _resp(client: CorvoClient, timeout: float = 2.0) -> dict:
    return client.inbox.get(timeout=timeout)


def _registrar_e_logar(client: CorvoClient, username: str, password: str) -> None:
    client.request(protocol.CMD_REGISTER, {"username": username, "password": password})
    _resp(client)
    client.request(protocol.CMD_LOGIN, {"username": username, "password": password})
    _resp(client)


def _criar_forum_com_membro(servidor):
    """Cria um forum com dono (alice) e um membro comum (bob) ja com Iniciado."""
    dono = _cliente(servidor)
    _registrar_e_logar(dono, "alice", "s3nh4A!")
    dono.request(protocol.CMD_CREATE_FORUM, {"name": "Corvos da Noite"})
    r = _resp(dono)
    forum_id, invite_code = r["data"]["forum_id"], r["data"]["invite_code"]

    membro = _cliente(servidor)
    _registrar_e_logar(membro, "bob", "s3nh4B!")
    membro.request(protocol.CMD_JOIN_FORUM, {"invite_code": invite_code})
    _resp(membro)
    _resp(dono)  # descarta MEMBER_JOINED

    return dono, membro, forum_id


# --- roles padrao ao criar/entrar no forum ------------------------------------

def test_dono_recebe_corvo_mor_ao_criar_forum(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)

    mask = servidor.db.get_member_permission_mask(forum_id, servidor.db.get_user_by_username("alice")["id"])
    assert permissions.has_permission(mask, permissions.Permission.ALL)

    dono.close()
    membro.close()


def test_novo_membro_recebe_iniciado(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)

    mask = servidor.db.get_member_permission_mask(forum_id, servidor.db.get_user_by_username("bob")["id"])
    assert permissions.has_permission(mask, permissions.Permission.SEND_MESSAGE)
    assert not permissions.has_permission(mask, permissions.Permission.MANAGE_ROLES)
    assert not permissions.has_permission(mask, permissions.Permission.DELETE_MESSAGE)

    dono.close()
    membro.close()


def test_roles_padrao_criadas_com_forum(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)

    nomes = {row["name"] for row in servidor.db.get_roles_for_forum(forum_id)}
    assert nomes == {"Corvo-Mor", "Escriba", "Iniciado"}

    dono.close()
    membro.close()


# --- create_role -----------------------------------------------------------------

def test_create_role_dono_pode(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)

    dono.request(
        protocol.CMD_CREATE_ROLE,
        {"forum_id": forum_id, "name": "Guardiao", "permissions": permissions.Permission.KICK_MEMBER},
    )
    r = _resp(dono)
    assert r["status"] == protocol.STATUS_OK
    assert r["data"]["name"] == "Guardiao"

    dono.close()
    membro.close()


def test_create_role_membro_comum_e_negado(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)

    membro.request(
        protocol.CMD_CREATE_ROLE,
        {"forum_id": forum_id, "name": "Golpe de Estado", "permissions": permissions.Permission.ALL},
    )
    r = _resp(membro)
    assert r["status"] == protocol.STATUS_ERROR
    assert "permissao negada" in r["message"]

    dono.close()
    membro.close()


def test_create_role_sem_autenticacao(servidor):
    c = _cliente(servidor)
    c.request(protocol.CMD_CREATE_ROLE, {"forum_id": 1, "name": "X", "permissions": 1})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao autenticado" in r["message"]
    c.close()


# --- assign_role -----------------------------------------------------------------

def test_assign_role_dono_pode(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)

    dono.request(
        protocol.CMD_CREATE_ROLE,
        {"forum_id": forum_id, "name": "Escriba-Chefe", "permissions": permissions.Permission.PIN_MESSAGE},
    )
    role_id = _resp(dono)["data"]["role_id"]

    dono.request(protocol.CMD_ASSIGN_ROLE, {"forum_id": forum_id, "username": "bob", "role_id": role_id})
    r = _resp(dono)
    assert r["status"] == protocol.STATUS_OK

    mask = servidor.db.get_member_permission_mask(forum_id, servidor.db.get_user_by_username("bob")["id"])
    assert permissions.has_permission(mask, permissions.Permission.PIN_MESSAGE)

    dono.close()
    membro.close()


def test_assign_role_membro_comum_e_negado(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)

    corvo_mor = next(r for r in servidor.db.get_roles_for_forum(forum_id) if r["name"] == "Corvo-Mor")
    membro.request(
        protocol.CMD_ASSIGN_ROLE, {"forum_id": forum_id, "username": "bob", "role_id": corvo_mor["id"]}
    )
    r = _resp(membro)
    assert r["status"] == protocol.STATUS_ERROR
    assert "permissao negada" in r["message"]

    dono.close()
    membro.close()


def test_assign_role_usuario_nao_membro(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)

    fora = _cliente(servidor)
    _registrar_e_logar(fora, "fantasma", "s3nh4F!")

    corvo_mor = next(r for r in servidor.db.get_roles_for_forum(forum_id) if r["name"] == "Corvo-Mor")
    dono.request(
        protocol.CMD_ASSIGN_ROLE, {"forum_id": forum_id, "username": "fantasma", "role_id": corvo_mor["id"]}
    )
    r = _resp(dono)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao e membro" in r["message"]

    dono.close()
    membro.close()
    fora.close()


def test_assign_role_de_outro_forum_falha(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)

    dono.request(protocol.CMD_CREATE_FORUM, {"name": "Outro Forum"})
    r = _resp(dono)
    outro_forum_id = r["data"]["forum_id"]
    role_de_outro_forum = next(
        row for row in servidor.db.get_roles_for_forum(outro_forum_id) if row["name"] == "Iniciado"
    )

    dono.request(
        protocol.CMD_ASSIGN_ROLE,
        {"forum_id": forum_id, "username": "bob", "role_id": role_de_outro_forum["id"]},
    )
    r = _resp(dono)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao encontrada" in r["message"]

    dono.close()
    membro.close()


# --- permissao aplicada a acoes sensiveis (pin / delete) --------------------------

def _enviar_mensagem_de_teste(client, forum_id):
    from shared import crypto_utils
    import base64

    aes_key = crypto_utils.generate_aes_key()
    ciphertext, iv = crypto_utils.aes_encrypt(b"mensagem de teste", aes_key)
    client.request(
        protocol.CMD_SEND_TO_FORUM,
        {
            "forum_id": forum_id,
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "iv": base64.b64encode(iv).decode("ascii"),
            "key_version": 1,
        },
    )
    r = _resp(client)
    return r["data"]["uuid"]


def test_pin_message_negado_para_iniciado(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)
    msg_uuid = _enviar_mensagem_de_teste(dono, forum_id)
    _resp(membro)  # NEW_MESSAGE

    membro.request(protocol.CMD_PIN_MESSAGE, {"uuid": msg_uuid, "pinned": True})
    r = _resp(membro)
    assert r["status"] == protocol.STATUS_ERROR
    assert "permissao negada" in r["message"]

    dono.close()
    membro.close()


def test_pin_message_permitido_apos_assign_role(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)
    msg_uuid = _enviar_mensagem_de_teste(dono, forum_id)
    _resp(membro)  # NEW_MESSAGE

    dono.request(
        protocol.CMD_CREATE_ROLE,
        {"forum_id": forum_id, "name": "Fixador", "permissions": permissions.Permission.PIN_MESSAGE},
    )
    role_id = _resp(dono)["data"]["role_id"]
    dono.request(protocol.CMD_ASSIGN_ROLE, {"forum_id": forum_id, "username": "bob", "role_id": role_id})
    _resp(dono)

    membro.request(protocol.CMD_PIN_MESSAGE, {"uuid": msg_uuid, "pinned": True})
    r = _resp(membro)
    assert r["status"] == protocol.STATUS_OK

    evt_dono = _resp(dono)
    assert evt_dono["cmd"] == protocol.EVT_MESSAGE_PINNED
    assert evt_dono["data"]["pinned"] is True

    dono.close()
    membro.close()


def test_delete_message_autor_pode_apagar_a_propria(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)
    msg_uuid = _enviar_mensagem_de_teste(dono, forum_id)
    _resp(membro)  # NEW_MESSAGE

    dono.request(protocol.CMD_DELETE_MESSAGE, {"uuid": msg_uuid})
    r = _resp(dono)
    assert r["status"] == protocol.STATUS_OK
    assert servidor.db.get_message_by_uuid(msg_uuid) is None

    dono.close()
    membro.close()


def test_delete_message_iniciado_nao_apaga_mensagem_alheia(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)
    msg_uuid = _enviar_mensagem_de_teste(dono, forum_id)
    _resp(membro)  # NEW_MESSAGE

    membro.request(protocol.CMD_DELETE_MESSAGE, {"uuid": msg_uuid})
    r = _resp(membro)
    assert r["status"] == protocol.STATUS_ERROR
    assert "permissao negada" in r["message"]
    assert servidor.db.get_message_by_uuid(msg_uuid) is not None

    dono.close()
    membro.close()


def test_delete_message_com_permissao_apaga_mensagem_alheia(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)
    msg_uuid = _enviar_mensagem_de_teste(dono, forum_id)
    _resp(membro)  # NEW_MESSAGE

    escriba = next(r for r in servidor.db.get_roles_for_forum(forum_id) if r["name"] == "Escriba")
    dono.request(
        protocol.CMD_ASSIGN_ROLE, {"forum_id": forum_id, "username": "bob", "role_id": escriba["id"]}
    )
    _resp(dono)

    membro.request(protocol.CMD_DELETE_MESSAGE, {"uuid": msg_uuid})
    r = _resp(membro)
    assert r["status"] == protocol.STATUS_OK
    assert servidor.db.get_message_by_uuid(msg_uuid) is None

    dono.close()
    membro.close()


# --- list_roles ----------------------------------------------------------------

def test_list_roles_inclui_ordem_sem_portadores(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)

    dono.request(
        protocol.CMD_CREATE_ROLE,
        {"forum_id": forum_id, "name": "Vigia", "color": "#4a7c3a", "permissions": permissions.Permission.SEND_MESSAGE},
    )
    r = _resp(dono)
    assert r["status"] == protocol.STATUS_OK

    dono.request(protocol.CMD_LIST_ROLES, {"forum_id": forum_id})
    r = _resp(dono)
    assert r["status"] == protocol.STATUS_OK
    nomes = {role["name"] for role in r["data"]["roles"]}
    assert {"Corvo-Mor", "Escriba", "Iniciado", "Vigia"} <= nomes
    vigia = next(role for role in r["data"]["roles"] if role["name"] == "Vigia")
    assert vigia["members"] == []

    dono.close()
    membro.close()


def test_list_roles_sem_autenticacao(servidor):
    c = _cliente(servidor)
    c.request(protocol.CMD_LIST_ROLES, {"forum_id": 1})
    r = _resp(c)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao autenticado" in r["message"]
    c.close()


def test_list_roles_nao_membro(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)

    fora = _cliente(servidor)
    _registrar_e_logar(fora, "fantasma", "s3nh4F!")
    fora.request(protocol.CMD_LIST_ROLES, {"forum_id": forum_id})
    r = _resp(fora)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao e membro" in r["message"]

    dono.close()
    membro.close()
    fora.close()


# --- update_role -----------------------------------------------------------------

def test_update_role_dono_sucesso(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)
    iniciado = next(r for r in servidor.db.get_roles_for_forum(forum_id) if r["name"] == "Iniciado")

    dono.request(
        protocol.CMD_UPDATE_ROLE,
        {"role_id": iniciado["id"], "name": "Aprendiz", "color": "#6b4a7c"},
    )
    # o dono tambem e destinatario do broadcast EVT_ROLE_UPDATED (ele quer ver
    # a propria sidebar de membros atualizar), entao a ordem entre a response
    # e o evento nao e garantida — descarta o que nao for a response.
    r = _resp(dono)
    if r["cmd"] == protocol.EVT_ROLE_UPDATED:
        r = _resp(dono)
    assert r["status"] == protocol.STATUS_OK
    assert r["data"]["name"] == "Aprendiz"
    assert r["data"]["color"] == "#6b4a7c"

    dono.close()
    membro.close()


def test_update_role_sem_permissao(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)
    iniciado = next(r for r in servidor.db.get_roles_for_forum(forum_id) if r["name"] == "Iniciado")

    membro.request(protocol.CMD_UPDATE_ROLE, {"role_id": iniciado["id"], "name": "Hackeado"})
    r = _resp(membro)
    assert r["status"] == protocol.STATUS_ERROR
    assert "permissao negada" in r["message"]

    dono.close()
    membro.close()


def test_update_role_inexistente(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)
    dono.request(protocol.CMD_UPDATE_ROLE, {"role_id": 9999, "name": "Fantasma"})
    r = _resp(dono)
    assert r["status"] == protocol.STATUS_ERROR
    assert "nao encontrada" in r["message"]
    dono.close()
    membro.close()


# --- delete_role -----------------------------------------------------------------

def test_delete_role_dono_sucesso(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)
    iniciado = next(r for r in servidor.db.get_roles_for_forum(forum_id) if r["name"] == "Iniciado")

    dono.request(protocol.CMD_DELETE_ROLE, {"role_id": iniciado["id"]})
    r = _resp(dono)
    if r["cmd"] == protocol.EVT_ROLE_DELETED:
        r = _resp(dono)
    assert r["status"] == protocol.STATUS_OK
    assert servidor.db.get_role_by_id(iniciado["id"]) is None

    dono.close()
    membro.close()


def test_delete_role_corvo_mor_protegida(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)
    corvo_mor = next(r for r in servidor.db.get_roles_for_forum(forum_id) if r["name"] == "Corvo-Mor")

    dono.request(protocol.CMD_DELETE_ROLE, {"role_id": corvo_mor["id"]})
    r = _resp(dono)
    assert r["status"] == protocol.STATUS_ERROR
    assert "Corvo-Mor" in r["message"]
    assert servidor.db.get_role_by_id(corvo_mor["id"]) is not None

    dono.close()
    membro.close()


def test_delete_role_sem_permissao(servidor):
    dono, membro, forum_id = _criar_forum_com_membro(servidor)
    iniciado = next(r for r in servidor.db.get_roles_for_forum(forum_id) if r["name"] == "Iniciado")

    membro.request(protocol.CMD_DELETE_ROLE, {"role_id": iniciado["id"]})
    r = _resp(membro)
    assert r["status"] == protocol.STATUS_ERROR
    assert "permissao negada" in r["message"]

    dono.close()
    membro.close()
