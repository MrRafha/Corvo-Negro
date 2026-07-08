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

**Data:** 08/07/2026 — **Dia 4 da Sprint 1 (E2E 1:1) concluído.**

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
- [x] venv de pé (Python **3.14.0**) com deps instaladas

**Ambiente rodando:** 49/49 testes passando (`.\venv\Scripts\python.exe -m pytest`).
**Validado manualmente:** servidor real + 2 clientes TCP trocando DM cifrada ponta a ponta (Alice cifra com a pubkey do Bob, servidor só roteia, Bob decifra e recupera o texto original).

---

## 🚀 Próximos passos imediatos (ordem)

**Próximo: Dia 5 — Fóruns (criação, convite por hash, membership).**

1. `shared/models.py`: dataclasses `Forum`, `ForumMember` (ainda vazio, previsto pra este dia).
2. Handler `create_forum`: cliente envia nome → servidor gera código de convite (`CORVO-XXXX-XXXX`), guarda `SHA-256(código)` em `forums.invite_hash`, devolve o código em claro pro dono compartilhar.
3. Handler `join_forum`: cliente envia código → servidor compara hash → insere em `forum_members`.
4. Handler `list_my_forums` e `leave_forum`.
5. Registrar os 4 comandos no router (`CMD_CREATE_FORUM`, `CMD_JOIN_FORUM`, `CMD_LEAVE_FORUM`, `CMD_LIST_MY_FORUMS` já existem em `protocol.py`).
6. CLI: comandos `/create`, `/join`, `/list`, `/leave`.
7. **Commit alvo:** `feat: sistema de fóruns com convites por hash`.

Tabelas `forums`/`forum_members` já existem no schema (`server/database.py`), faltam os métodos de acesso (`create_forum`, `get_forum_by_invite_hash`, `add_member`, etc.) e os handlers.

### O que já está pronto e reutilizável

- `crypto_utils`: hash/verify de senha, RSA-2048 OAEP, AES-256-CBC, PBKDF2, `public_key_from_private`. **16 testes.**
- `protocol`: framing `[4B tamanho][JSON]`, constantes de todos os comandos (`CMD_GET_PUBKEY`, `CMD_UPDATE_PUBKEY`, `CMD_MSG_1V1`, `EVT_NEW_DM` inclusos), helpers `make_request/make_response/make_event`. **Testado.**
- `SessionManager`: mapa socket→sessão thread-safe, unicast/broadcast, `send_to_user` (roteia só se online), autenticação de sessão.
- `Router`: despacho `cmd → handler` com `register()`; handlers embutidos `PING`/`ECHO` + auth + key_exchange + message.
- `CorvoServer`: TCP threaded (1 thread/cliente), testado com múltiplos clientes simultâneos.
- `CorvoClient`: connect/send/close + thread de recv → `inbox` (queue).
- `key_vault`: salva/carrega a private key RSA cifrada (PBKDF2 → AES-256) em `~/.corvo_negro/keys/<user>.key`.
- Mensagens 1:1 (`MSG_1V1`): fluxo híbrido RSA+AES completo, servidor só persiste/roteia ciphertext em `direct_messages`.
- `cli_test`: `python -m client.cli_test` (`/register`, `/login`, `/dm`, `/ping`, `/echo`, `/raw`, `/quit`) — decifra `NEW_DM` automaticamente se a chave privada estiver carregada.

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
