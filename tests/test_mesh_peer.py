"""Testes do mesh P2P do modo LAN (Sprint 3, Dia 11-12).

Cobre a camada de conexao/handshake/roteamento isoladamente, sem depender de
mDNS real (lan_discovery.PeerInfo e montado manualmente com 127.0.0.1) —
descoberta via zeroconf nao e exercitada aqui, so a conexao TCP direta e a
troca de mensagens cifradas entre peers ja "descobertos".

Cobre:
    - handshake bem sucedido quando os peers compartilham pelo menos 1 forum
    - peer sem forum em comum e desconectado (nao fica na lista de conexoes)
    - broadcast_to_forum so entrega a peers que sao membros daquele forum
    - round-trip completo: cifra com AES do forum -> broadcast -> peer recebe
      -> decifra com a mesma chave -> texto bate
"""

from __future__ import annotations

import time

import pytest

from client.network.lan_discovery import PeerInfo
from client.network.mesh_peer import MeshPeerManager
from shared import crypto_utils

_ESPERA = 1.2  # handshake/roteamento roda em threads; dar tempo de propagar
# (folga maior que o minimo observado — sob contencao de CPU, quando a suite
# inteira roda em paralelo, 0.6s ocasionalmente nao bastava e gerava flaky).


def _novo_manager(user_id: int, username: str, foruns: set[int], on_message=None, on_peers_changed=None):
    priv, pub = crypto_utils.generate_rsa_keypair()
    mgr = MeshPeerManager(
        my_user_id=user_id,
        my_username=username,
        private_key_pem=priv,
        public_key_pem=pub,
        meus_foruns=lambda: foruns,
        on_message=on_message or (lambda m: None),
        on_peers_changed=on_peers_changed or (lambda n: None),
    )
    porta = mgr.start_listening()
    return mgr, porta


def _peer_de(mgr: MeshPeerManager, user_id: int, username: str, foruns: set[int], porta: int) -> PeerInfo:
    return PeerInfo(user_id=user_id, username=username, forum_ids=foruns, host="127.0.0.1", port=porta)


@pytest.fixture
def dois_peers_com_forum_comum():
    mgr_a, porta_a = _novo_manager(1, "alice", {10, 20})
    mgr_b, porta_b = _novo_manager(2, "bob", {20, 30})
    yield mgr_a, porta_a, mgr_b, porta_b
    mgr_a.stop()
    mgr_b.stop()


def test_handshake_conecta_quando_compartilham_forum(dois_peers_com_forum_comum):
    mgr_a, porta_a, mgr_b, porta_b = dois_peers_com_forum_comum
    peer_b = _peer_de(mgr_b, 2, "bob", {20, 30}, porta_b)

    mgr_a.connect_to_peer(peer_b)
    time.sleep(_ESPERA)

    assert mgr_a.peer_count() == 1
    assert mgr_b.peer_count() == 1


def test_peer_sem_forum_em_comum_e_desconectado():
    mgr_a, porta_a = _novo_manager(1, "alice", {10})
    mgr_b, porta_b = _novo_manager(2, "bob", {99})
    try:
        peer_b = _peer_de(mgr_b, 2, "bob", {99}, porta_b)
        mgr_a.connect_to_peer(peer_b)
        time.sleep(_ESPERA)

        assert mgr_a.peer_count() == 0
        assert mgr_b.peer_count() == 0
    finally:
        mgr_a.stop()
        mgr_b.stop()


def test_broadcast_so_entrega_a_peer_do_mesmo_forum():
    recebidas_a: list[dict] = []
    recebidas_c: list[dict] = []

    mgr_a, porta_a = _novo_manager(1, "alice", {10, 20}, on_message=recebidas_a.append)
    mgr_b, porta_b = _novo_manager(2, "bob", {20})
    mgr_c, porta_c = _novo_manager(3, "carol", {30}, on_message=recebidas_c.append)
    try:
        mgr_b.connect_to_peer(_peer_de(mgr_a, 1, "alice", {10, 20}, porta_a))
        # carol nao compartilha forum com ninguem aqui — handshake deve falhar/desconectar.
        mgr_c.connect_to_peer(_peer_de(mgr_a, 1, "alice", {10, 20}, porta_a))
        time.sleep(_ESPERA)

        assert mgr_c.peer_count() == 0  # sem forum em comum com alice

        mgr_b.broadcast_to_forum(20, {"uuid": "msg-1", "ciphertext": "xx", "iv": "yy"})
        time.sleep(_ESPERA)

        assert len(recebidas_a) == 1
        assert recebidas_a[0]["data"]["uuid"] == "msg-1"
        assert len(recebidas_c) == 0
    finally:
        mgr_a.stop()
        mgr_b.stop()
        mgr_c.stop()


def test_round_trip_mensagem_cifrada_via_mesh():
    mgr_x, porta_x = _novo_manager(10, "corvo-x", {20})
    recebidas2: list[dict] = []
    mgr_y, porta_y = _novo_manager(11, "corvo-y", {20}, on_message=recebidas2.append)
    try:
        aes_key = crypto_utils.generate_aes_key()
        texto_original = b"a palavra selada viaja em asas negras"
        ciphertext, iv = crypto_utils.aes_encrypt(texto_original, aes_key)

        mgr_x.connect_to_peer(_peer_de(mgr_y, 11, "corvo-y", {20}, porta_y))
        time.sleep(_ESPERA)
        assert mgr_x.peer_count() == 1

        mgr_x.broadcast_to_forum(20, {
            "uuid": "msg-round-trip",
            "ciphertext": ciphertext.hex(),
            "iv": iv.hex(),
            "key_version": 1,
        })
        time.sleep(_ESPERA)

        assert len(recebidas2) == 1
        recebida = recebidas2[0]["data"]
        decifrado = crypto_utils.aes_decrypt(
            bytes.fromhex(recebida["ciphertext"]), aes_key, bytes.fromhex(recebida["iv"])
        )
        assert decifrado == texto_original
    finally:
        mgr_x.stop()
        mgr_y.stop()
