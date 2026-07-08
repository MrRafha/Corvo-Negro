# 🜲 Corvo Negro — Contexto do Projeto

> Arquivo de briefing. Ponto único de entrada para retomar o trabalho a qualquer momento.
> Leia isto + `README.md` + `docs/DEVELOPMENT.md` e você tem todo o contexto.

---

## 📌 Resumo em uma linha

Fórum criptografado ponta a ponta (E2E) em Python, com suporte híbrido **LAN + Online**, desenvolvido como projeto final da disciplina de Segurança da Informação (IFPI).

---

## 🎯 O que é

- **Servidor** TCP threaded que apenas **rotea** mensagens cifradas (nunca lê o conteúdo).
- **Cliente** GUI (CustomTkinter) que cifra/decifra localmente.
- Três camadas de proteção:
  1. **Autenticação** — SHA-256 + PBKDF2 (100k iterações, salt único por usuário).
  2. **Troca de chaves** — RSA-2048 com padding OAEP.
  3. **Criptografia de sessão** — AES-256-CBC.
- **E2E em grupo**: cada fórum tem uma chave AES, cifrada com a RSA pública de cada membro. Rotação de chave quando alguém sai.
- **Modo LAN autônomo**: se a internet cai, os clientes na mesma rede se descobrem via mDNS (zeroconf) e continuam a conversa em mesh P2P. Sync ao voltar online.

---

## 🏛 Stack

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.11+ |
| Criptografia | `cryptography` (RSA, AES, PBKDF2, SHA-256) |
| Rede | `socket` (TCP puro), `threading` |
| Descoberta LAN | `zeroconf` (mDNS) |
| Interface | `customtkinter` |
| Persistência | SQLite via `sqlite3` |
| Testes | `pytest` |

---

## 📅 Cronograma (prazo: 07/07 → 21/07)

| Fase | Período | Foco | Marco |
|---|---|---|---|
| **Sprint 1** | Seg 07 → Seg 13 | Núcleo criptográfico + backend | Chat E2E multi-sala em CLI |
| **Sprint 2** | Ter 14 → Sex 17 | Interface + Roles | Aplicação visual funcional |
| **Sprint 3** | Dom 19 → Ter 21 | LAN Mode + Entrega | Projeto completo entregue |

Sábados (11 e 18) = off (D&D).

---

## ✅ Estado atual

**Data:** 08/07/2026 — **Dia 6 da Sprint 1 (E2E em grupo) concluído.**

- [x] `README.md` pronto
- [x] `DEVELOPMENT.md` pronto (guia de sprints)
- [x] `CONTEXT.md` (este arquivo)
- [x] Repositório GitHub `Corvo-Negro` criado (público) + remote conectado
- [x] Estrutura de pastas completa (bate com a árvore do DEVELOPMENT.md)
- [x] `.gitignore`, `requirements.txt` (raiz + por componente), `LICENSE`
- [x] Commit de setup inicial (feito pelo usuário)
- [x] **Dia 1 — `shared/crypto_utils.py` + `tests/test_crypto.py`** (16 testes ✅)
- [x] **Dia 2 — Socket TCP + Protocolo** (`protocol.py`, `session_manager.py`, `router.py`, `server/main.py`, `client_socket.py`, `cli_test.py`) — 9 testes ✅
- [x] **Dia 3 — Autenticação** (`database.py` schema completo, `handlers/auth.py`, `Router` com `db`, `test_auth.py`) — 9 testes ✅
- [x] **Dia 4 — E2E 1:1** (`CMD_UPDATE_PUBKEY`/`CMD_GET_PUBKEY` em `handlers/key_exchange.py`, `CMD_MSG_1V1` em `handlers/message.py`, tabela `direct_messages`, `client/storage/key_vault.py`, `cli_test.py` com `/register /login /dm`, `tests/test_e2e.py` + `tests/test_key_vault.py`) — 15 testes ✅
- [x] **Dia 5 — Fóruns** (`handlers/forum.py` completo: `create_forum`/`join_forum`/`leave_forum`/`list_my_forums`, códigos `CORVO-XXXX-XXXX` com SHA-256 hash, métodos de DB `create_forum`/`get_forum_by_invite_hash`/`add_member`/`remove_member`/`is_member`/`get_forum_members`/`get_forums_for_user`, eventos `MEMBER_JOINED`/`MEMBER_LEFT`, `cli_test.py` com `/create /join /leave /list`, `tests/test_forum.py`) — 13 testes ✅
- [x] **Dia 6 — E2E em grupo** (`handle_distribute_key` em `handlers/key_exchange.py`, `handle_send_to_forum`/`handle_get_history` em `handlers/message.py`, tabelas `forum_keys`/`messages` com métodos de DB completos, rotação de chave ao sair via `MEMBER_LEFT` com `remaining_members`, `cli_test.py` com `/send /history` + distribuição/rotação automática quando o usuário logado é dono, `tests/test_group_e2e.py`) — 9 testes ✅
- [x] venv de pé (Python **3.14.0**) com deps instaladas

**Ambiente rodando:** 71/71 testes passando (`.\venv\Scripts\python.exe -m pytest`).
**Validado manualmente:** servidor real + múltiplos clientes TCP — DM cifrada ponta a ponta (Dia 4), ciclo completo de fórum (Dia 5), e fluxo de grupo com 3 membros: criar fórum → distribuir chave v1 → mensagens circulando → um membro sai → dono rotaciona pra v2 → só quem ficou decifra a nova mensagem (Dia 6).

---

## 🚀 Próximos passos imediatos (ordem)

**Próximo: Dia 7 — Sistema de Roles (permissões bitmask).**

1. `shared/permissions.py`: classe `Permission` com bitmask (`SEND_MESSAGE=1`, `DELETE_MESSAGE=2`, `PIN_MESSAGE=4`, `SEND_IMAGE=8`, `CREATE_CHANNEL=16`, `KICK_MEMBER=32`, `BAN_MEMBER=64`, `MANAGE_ROLES=128`, `MANAGE_FORUM=256`, `ALL=511`) — arquivo ainda vazio.
2. Tabelas `roles`/`member_roles` já existem no schema (`server/database.py`); faltam os métodos de acesso (`create_role`, `get_roles_for_forum`, `assign_role`, `get_member_permissions`, etc.).
3. Roles padrão ao criar um fórum: `Corvo-Mor` (ALL, automática pro dono), `Escriba` (SEND+DELETE+PIN+KICK), `Iniciado` (SEND).
4. Handlers em `handlers/role.py` (hoje só esqueleto): `create_role`, `edit_role`, `delete_role`, `assign_role`, `revoke_role`.
5. Toda ação sensível (pin/delete de mensagem, kick, etc.) deve checar a permissão bitmask no servidor **antes** de executar — inclusive retroativo aos TODOs deixados em `handlers/message.py` (pin/delete).
6. Testes: dono edita role com sucesso; membro sem `MANAGE_ROLES` tenta e é negado.
7. **Commit alvo:** `feat: sistema de roles customizáveis com permissões bitmask`.

**🏁 Isso fecha a Sprint 1** (marco: chat E2E multi-sala funcionando em CLI). Depois disso começa a Sprint 2 (interface) — ver a nota sobre o design de UI já feito no Claude Design, a ser revisitado no Dia 8.

### O que já está pronto e reutilizável

- `crypto_utils`: hash/verify de senha, RSA-2048 OAEP, AES-256-CBC, PBKDF2, `public_key_from_private`. **16 testes.**
- `protocol`: framing `[4B tamanho][JSON]`, constantes de todos os comandos (`CMD_GET_PUBKEY`, `CMD_UPDATE_PUBKEY`, `CMD_MSG_1V1`, `CMD_DISTRIBUTE_KEY`, `CMD_SEND_TO_FORUM`, `CMD_GET_HISTORY`, `EVT_NEW_DM`, `EVT_KEY_ROTATED` inclusos), helpers `make_request/make_response/make_event`. **Testado.**
- `SessionManager`: mapa socket→sessão thread-safe, unicast/broadcast, `send_to_user` (roteia só se online), autenticação de sessão.
- `Router`: despacho `cmd → handler` com `register()`; handlers embutidos `PING`/`ECHO` + auth + key_exchange + message + forum.
- `CorvoServer`: TCP threaded (1 thread/cliente), testado com múltiplos clientes simultâneos.
- `CorvoClient`: connect/send/close + thread de recv → `inbox` (queue).
- `key_vault`: salva/carrega a private key RSA cifrada (PBKDF2 → AES-256) em `~/.corvo_negro/keys/<user>.key`.
- Mensagens 1:1 (`MSG_1V1`): fluxo híbrido RSA+AES completo, servidor só persiste/roteia ciphertext em `direct_messages`.
- Fóruns: criação com convite `CORVO-XXXX-XXXX` (hash SHA-256, código nunca fica em claro no DB), join/leave/list, notificações `MEMBER_JOINED`/`MEMBER_LEFT` (com `owner_id`/`remaining_members`) só pros membros online.
- E2E em grupo: chave AES por fórum controlada pelo dono (`DISTRIBUTE_KEY`), mensagens de fórum via `SEND_TO_FORUM`/`NEW_MESSAGE`, histórico via `GET_HISTORY` com `key_version` por mensagem, rotação de chave automática ao alguém sair.
- `cli_test`: `python -m client.cli_test` (`/register`, `/login`, `/dm`, `/create`, `/join`, `/leave`, `/list`, `/send`, `/history`, `/ping`, `/echo`, `/raw`, `/quit`) — decifra `NEW_DM`/`NEW_MESSAGE` automaticamente e cuida da distribuição/rotação de chave quando o usuário logado é dono do fórum.

---

## 🧭 Princípios de execução (não esquecer)

1. **Nunca pule os testes da Sprint 1.** Cripto bugada só aparece dias depois.
2. **Commits pequenos e semânticos** (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`). Meta: 40+ commits.
3. **Um branch por feature grande** (`feat/e2e-groups`, `feat/lan-mode`). Merge no main quando funcional.
4. **Documente decisões** em `docs/decisions.md` enquanto toma, não depois.
5. **Grave clipes curtos** de features prontas durante o dev (economiza na hora do vídeo).
6. **Checkpoint diário:** o que estiver no `main` ao fim do dia precisa **rodar**. Se quebrou, reverte antes de dormir.
7. **Nunca commitar depois das 22h.**

---

## 🔗 Referências internas

- `README.md` — visão do produto, funcionalidades, instalação, uso.
- `docs/DEVELOPMENT.md` — plano dia-a-dia das 3 sprints, protocolo TCP, checklist de entrega.
- Repo GitHub: `https://github.com/MrRafha/corvo-negro` *(a criar)*

> *"As palavras dos mortos viajam em asas negras. Nenhum ouvido profano as escutará."*
