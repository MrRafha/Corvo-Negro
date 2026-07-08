# 🜲 Arquitetura — Corvo Negro

> Diagramas e fluxos detalhados. A ser finalizado na Sprint 3 (Dia 13) com
> diagramas Excalidraw. Esqueleto inicial abaixo.

---

## Visão geral

Dois modos de operação:

- **Online:** clientes ⇄ servidor TCP central (roteador) ⇄ SQLite (ciphertext).
- **LAN:** ao cair a internet, clientes se descobrem via mDNS e conversam em mesh P2P.

## Camadas de criptografia

1. **Autenticação** — SHA-256 + PBKDF2 (salt por usuário).
2. **Troca de chaves** — RSA-2048 OAEP.
3. **Sessão** — AES-256-CBC (chave por fórum).

## Fluxo de uma mensagem em grupo

1. Remetente cifra com a AES do fórum → ciphertext.
2. Envia `{forum_id, ciphertext, iv, key_version}` ao servidor.
3. Servidor persiste o ciphertext (sem ler) e rotea aos membros online.
4. Cada destinatário decifra localmente com sua AES do fórum.

> A AES do fórum é entregue a cada membro cifrada com sua RSA pública; só a
> RSA privada (que nunca sai do dispositivo) a decifra.

## TODO (Sprint 3, Dia 13)

- [ ] Diagramas Excalidraw (online, LAN, fluxo criptográfico).
- [ ] Diagrama de sequência do sync LAN ↔ online.
