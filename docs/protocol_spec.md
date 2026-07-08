# 🜲 Especificação do Protocolo TCP — Corvo Negro

> A ser preenchido ao longo da Sprint 1 e finalizado no Dia 13.

---

## Framing

```
[4 bytes big-endian: tamanho do payload em bytes][payload JSON UTF-8]
```

## Estrutura das mensagens

**Request (cliente → servidor):**
```json
{ "cmd": "COMMAND_NAME", "session_token": "opcional", "data": { } }
```

**Response (servidor → cliente):**
```json
{ "cmd": "COMMAND_NAME_RESPONSE", "status": "ok|error", "message": "...", "data": { } }
```

**Broadcast (servidor → cliente):**
```json
{ "cmd": "EVENT_NAME", "data": { } }
```

## Comandos

| Comando | Direção | Propósito |
|---|---|---|
| `REGISTER` | C→S | Cadastro de novo usuário |
| `LOGIN` | C→S | Autenticação + session_token |
| `LOGOUT` | C→S | Encerrar sessão |
| `GET_PUBKEY` | C→S | Obter public key de outro user |
| `UPDATE_PUBKEY` | C→S | Atualizar a própria public key RSA (pós-login) |
| `MSG_1V1` | C→S | Enviar mensagem direta cifrada (híbrido RSA+AES) |
| `CREATE_FORUM` | C→S | Criar fórum |
| `JOIN_FORUM` | C→S | Entrar via código de convite |
| `LEAVE_FORUM` | C→S | Sair do fórum |
| `LIST_MY_FORUMS` | C→S | Listar fóruns do usuário |
| `DISTRIBUTE_KEY` | C→S | Dono envia a AES do fórum cifrada para um membro |
| `SEND_TO_FORUM` | C→S | Enviar mensagem cifrada com a AES do fórum |
| `GET_HISTORY` | C→S | Puxar histórico do fórum |
| `SYNC_MESSAGES` | C→S | Sync após modo LAN |
| `CREATE_ROLE` | C→S | Criar role |
| `ASSIGN_ROLE` | C→S | Atribuir role a membro |
| `NEW_MESSAGE` | S→C | Broadcast de nova mensagem de fórum |
| `NEW_DM` | S→C | Notifica mensagem direta recebida |
| `MEMBER_JOINED` | S→C | Notifica novo membro (inclui `owner_id`) |
| `MEMBER_LEFT` | S→C | Notifica saída — inclui `owner_id` e `remaining_members` p/ o dono rotacionar a chave |
| `KEY_ROTATED` | S→C | Entrega/rotação da AES do fórum, cifrada com a RSA do destinatário |

## E2E em grupo (chave por fórum)

O servidor nunca gera nem decifra a chave AES de um fórum — quem controla a
distribuição é sempre o **dono**:

1. Ao criar o fórum, o dono gera a AES da sala, cifra com a própria pubkey e
   chama `DISTRIBUTE_KEY {forum_id, recipient: <ele mesmo>, encrypted_aes_key, key_version: 1}`.
2. Quando alguém entra (`JOIN_FORUM`), o servidor notifica todos os membros
   online via `MEMBER_JOINED` (inclui `owner_id`). O cliente do dono, ao
   reconhecer que é dono daquele fórum, busca a pubkey do novo membro
   (`GET_PUBKEY`) e distribui a chave atual para ele.
3. Quando alguém sai (`LEAVE_FORUM`), o servidor notifica os membros restantes
   via `MEMBER_LEFT`, que já inclui `remaining_members`. O cliente do dono
   gera uma nova AES, incrementa `key_version` e redistribui para cada membro
   restante via `DISTRIBUTE_KEY`.
4. Mensagens de fórum (`SEND_TO_FORUM`) trafegam com `{forum_id, ciphertext,
   iv, key_version}` — o servidor persiste e roteia para os membros online
   (`NEW_MESSAGE`), sem decifrar. O histórico (`GET_HISTORY`) devolve as
   mensagens com a `key_version` de cada uma, para o cliente decifrar
   localmente com a chave correspondente.
