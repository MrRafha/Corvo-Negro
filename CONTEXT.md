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

**Data:** 07/07/2026 — **Dia 1 da Sprint 1 (Setup + Crypto Utils).**

- [x] `README.md` pronto
- [x] `DEVELOPMENT.md` pronto (guia de sprints)
- [x] `CONTEXT.md` (este arquivo)
- [x] Repositório GitHub `Corvo-Negro` criado (público) + remote conectado
- [x] Estrutura de pastas completa (bate com a árvore do DEVELOPMENT.md)
- [x] `.gitignore`, `requirements.txt` (raiz + por componente), `LICENSE`
- [x] Commit de setup inicial (feito pelo usuário)
- [x] **Dia 1 — `shared/crypto_utils.py` + `tests/test_crypto.py`** (16 testes ✅)
- [x] **Dia 2 — Socket TCP + Protocolo** (`protocol.py`, `session_manager.py`, `router.py`, `server/main.py`, `client_socket.py`, `cli_test.py`) — 9 testes ✅
- [x] venv de pé (Python **3.14.0**) com deps instaladas

**Ambiente rodando:** 25/25 testes passando (`.\venv\Scripts\python.exe -m pytest`).

---

## 🚀 Próximos passos imediatos (ordem)

**Estamos no início do Dia 3 — Autenticação.**

1. `server/database.py` — schema SQLite `users` + `create_user` / `get_user_by_username` / `update_public_key`.
2. `server/handlers/auth.py` — `handle_register`, `handle_login`, `handle_logout` (usa `crypto_utils.hash_password/verify_password`).
3. Registrar os handlers de auth no `router.py`.
4. Fluxo CLI de cadastro e login (estender `client/cli_test.py`).
5. `tests/test_auth.py` — usuário duplicado, senha errada, login sem cadastro.
6. **Commit alvo:** `feat: autenticação com SHA-256 + PBKDF2`.

### O que já está pronto e reutilizável

- `crypto_utils`: hash/verify de senha, RSA-2048 OAEP, AES-256-CBC, PBKDF2. **16 testes.**
- `protocol`: framing `[4B tamanho][JSON]`, constantes de todos os comandos, helpers `make_request/make_response/make_event`. **Testado.**
- `SessionManager`: mapa socket→sessão thread-safe, unicast/broadcast, autenticação de sessão.
- `Router`: despacho `cmd → handler` com `register()`; handlers embutidos `PING`/`ECHO`.
- `CorvoServer`: TCP threaded (1 thread/cliente), testado com 3 clientes simultâneos.
- `CorvoClient`: connect/send/close + thread de recv → `inbox` (queue).
- `cli_test`: `python -m client.cli_test` (`/ping`, `/echo`, `/raw`, `/quit`).

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
