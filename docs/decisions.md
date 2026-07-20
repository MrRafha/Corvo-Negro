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

## 2026-07-19 — Sprint 3: modo LAN, cache local e sync

- **Cache local (`LocalDB`) não recifra `ciphertext`/`iv` das mensagens** — grava exatamente como chegaram (já cifradas com a AES do fórum, igual ao modo online).
  *Motivo:* recifrar com a chave derivada da senha (PBKDF2) seria dupla-cifragem sem ganho real de segurança — quem tem a chave AES do fórum já decifra o conteúdo de qualquer forma — e só complicaria o fluxo de sync (teria que decifrar/recifrar a cada ida e volta entre local e servidor). O que é cifrado campo-a-campo com a chave derivada da senha são os metadados em claro que identificam pessoas/conteúdo no DB local: `sender` (username), `forum.name`, `known_users.public_key_pem`.
- **Resolução de conflitos do sync LAN ↔ online: last-write-wins por `origin_timestamp`.**
  *Motivo:* mensagens têm `uuid` gerado uma única vez na origem e nunca são editadas — não há conteúdo para mesclar, só ordem de exibição a resolver quando o histórico local (recebido via mesh) e o histórico do servidor se combinam após a reconexão. Ordenar por `origin_timestamp` (não pelo `id` local, que é só ordem de chegada) garante que mensagens trocadas em modo LAN apareçam intercaladas corretamente com as que chegaram por outros caminhos, sem exigir merge de conteúdo. Aceitável para o escopo acadêmico do projeto — um sistema de produção com edição de mensagens exigiria uma estratégia mais robusta (vetores de versão, CRDTs).
