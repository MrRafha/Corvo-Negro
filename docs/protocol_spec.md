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
| `CREATE_FORUM` | C→S | Criar fórum |
| `JOIN_FORUM` | C→S | Entrar via código de convite |
| `LEAVE_FORUM` | C→S | Sair do fórum |
| `LIST_MY_FORUMS` | C→S | Listar fóruns do usuário |
| `DISTRIBUTE_KEY` | C→S | Enviar AES cifrada para membro novo |
| `SEND_TO_FORUM` | C→S | Enviar mensagem cifrada |
| `GET_HISTORY` | C→S | Puxar histórico do fórum |
| `SYNC_MESSAGES` | C→S | Sync após modo LAN |
| `CREATE_ROLE` | C→S | Criar role |
| `ASSIGN_ROLE` | C→S | Atribuir role a membro |
| `NEW_MESSAGE` | S→C | Broadcast de nova mensagem |
| `MEMBER_JOINED` | S→C | Notifica novo membro |
| `MEMBER_LEFT` | S→C | Notifica saída (dispara rotação de chave) |
| `KEY_ROTATED` | S→C | Notifica nova chave AES do fórum |
