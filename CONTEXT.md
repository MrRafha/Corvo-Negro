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
- [ ] Repositório GitHub `corvo-negro` criado (público)
- [ ] Estrutura de pastas
- [ ] `.gitignore`, `requirements.txt`, `LICENSE`
- [ ] Primeiro commit: `chore: setup inicial do projeto`
- [ ] `shared/crypto_utils.py` + `tests/test_crypto.py`

---

## 🚀 Próximos passos imediatos (ordem)

1. **Criar o repo `corvo-negro` no GitHub** (público). ← *estamos aqui*
2. `git init` / clone local, mover `DEVELOPMENT.md` para `docs/`.
3. Criar a estrutura de pastas (árvore no `docs/DEVELOPMENT.md`).
4. `.gitignore` de Python (nunca commitar `.db`, `.env`, `venv/`, `__pycache__`, `*.key`, `*.pem`).
5. `requirements.txt` inicial: `cryptography`, `pytest`.
6. Setup do venv + primeiro commit.
7. Implementar `shared/crypto_utils.py` e os testes.

### Assinaturas alvo de `shared/crypto_utils.py` (Dia 1, tarde)

```python
hash_password(password: str) -> bytes            # salt 16B + PBKDF2-HMAC-SHA256, 100k
verify_password(password: str, stored: bytes) -> bool
generate_rsa_keypair() -> tuple[bytes, bytes]    # PEM (priv, pub)
rsa_encrypt(data: bytes, public_key_pem: bytes) -> bytes   # OAEP + SHA-256
rsa_decrypt(ciphertext: bytes, private_key_pem: bytes) -> bytes
aes_encrypt(plaintext: bytes, key: bytes) -> tuple[bytes, bytes]  # CBC -> (ciphertext, iv)
aes_decrypt(ciphertext: bytes, key: bytes, iv: bytes) -> bytes
generate_aes_key() -> bytes                      # 32 bytes = AES-256
derive_key_from_password(password: str, salt: bytes) -> bytes    # PBKDF2 p/ DB local
```

### Testes alvo (`tests/test_crypto.py`)

- Hash + verify (senha correta e errada)
- RSA round-trip
- AES round-trip
- PBKDF2 determinístico com mesmo salt

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
