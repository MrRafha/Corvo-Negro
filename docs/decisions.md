# 🜲 Log de Decisões Técnicas — Corvo Negro

> Registre decisões **enquanto as toma**, não depois. Um bullet basta.
> Formato: data + decisão + motivo curto.

---

## 2026-07-07 — Setup inicial

- **Estrutura de monorepo** com `shared/` (código comum), `server/`, `client/`, `tests/`, `docs/`.
  *Motivo:* server e client compartilham `crypto_utils`, `protocol` e `models` — evita duplicação.
- **`.gitignore` agressivo** para segredos: `*.db`, `*.key`, `*.pem`, `.env`, `key_vault/`.
  *Motivo:* nada sensível pode vazar no repositório público (critério de nota).
- **`requirements.txt` por componente** além do da raiz.
  *Motivo:* server não precisa de `customtkinter`/`zeroconf`; instalações mais enxutas.

---

## Decisões previstas (a preencher durante o desenvolvimento)

- Escolha de parâmetros PBKDF2 (iterações, tamanho de salt).
- Modo AES (CBC + IV aleatório por mensagem).
- Estratégia de resolução de conflitos do sync LAN ↔ online ("last-write-wins por timestamp — aceitável para escopo acadêmico").
