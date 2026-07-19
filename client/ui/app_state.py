"""Estado de sessao compartilhado entre as telas da GUI (Sprint 2, Dia 8).

Substitui o dict `_state` do client/cli_test.py por uma classe pequena e
testavel. Guarda a identidade do usuario logado, a chave privada RSA em
memoria, e as chaves AES de cada forum (por versao, ja que rotacionam).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AppState:
    username: str | None = None
    user_id: int | None = None
    private_key_pem: bytes | None = None
    # {(forum_id, key_version): aes_key} — chaves de forum decifradas em memoria.
    forum_keys: dict[tuple[int, int], bytes] = field(default_factory=dict)
    # {forum_id} — foruns onde este usuario e o dono.
    owned_forums: set[int] = field(default_factory=set)
    current_forum_id: int | None = None
    # Modo LAN (Sprint 3): True quando o servidor central esta inacessivel e o
    # cliente esta operando via mesh P2P direto com outros peers na rede local.
    modo_lan: bool = False
    # username -> lan_discovery.PeerInfo dos peers mesh atualmente conectados.
    peers_lan: dict[str, object] = field(default_factory=dict)
    # client.storage.local_db.LocalDB aberto apos o login (Fase 3) — None ate la.
    local_db: object | None = None

    def note_ownership(self, forum_id: int, owner_id: int | None) -> None:
        """Marca `forum_id` como possuido por este usuario, se `owner_id` bater."""
        if owner_id is not None and self.user_id == owner_id:
            self.owned_forums.add(forum_id)

    def current_key_version(self, forum_id: int) -> int:
        """Maior key_version conhecida em memoria para o forum (0 se nenhuma)."""
        versions = [v for (fid, v) in self.forum_keys if fid == forum_id]
        return max(versions) if versions else 0

    def current_forum_key(self) -> bytes | None:
        """AES key da versao mais recente do forum atualmente selecionado."""
        if self.current_forum_id is None:
            return None
        version = self.current_key_version(self.current_forum_id)
        return self.forum_keys.get((self.current_forum_id, version))
