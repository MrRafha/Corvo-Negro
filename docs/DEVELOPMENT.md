# 🜲 Corvo Negro — Guia de Desenvolvimento

> Documento norteador de sprints, estrutura e execução técnica do projeto.
> **Prazo:** 07/07 a 21/07 (14 dias, ~12 dias úteis descontando sábados de D&D)
> **Dedicação prevista:** 8-10h/dia
> **Orçamento total:** ~100-120h

---

## 📅 Visão geral do cronograma

| Fase | Período | Foco | Marco |
|---|---|---|---|
| **Sprint 1** | Seg 07 → Seg 13 | Núcleo criptográfico + backend | Chat E2E multi-sala em CLI |
| **Sprint 2** | Ter 14 → Sex 17 | Interface + Roles | Aplicação visual funcional |
| **Sprint 3** | Dom 19 → Ter 21 | LAN Mode + Entrega | Projeto completo entregue |

Sábados (11 e 18) = **off** para D&D.

---

## 🎯 Princípios de execução

1. **Nunca pule os testes da Sprint 1.** Criptografia bugada só aparece dias depois — teste unitário economiza horas.
2. **Commits pequenos e semânticos.** `feat:`, `fix:`, `refactor:`, `test:`, `docs:`. Meta: 40+ commits até o fim.
3. **Um branch por feature grande.** `feat/e2e-groups`, `feat/lan-mode`. Merge no main quando funcional.
4. **Documente decisões técnicas** enquanto toma, não depois. Um arquivo `docs/decisions.md` com bullets basta.
5. **Grave clipes curtos de features prontas** durante o desenvolvimento. Vai economizar horas na hora do vídeo.
6. **Marcos de checkpoint diários:** ao fim de cada dia, o que estiver na branch main precisa **rodar**. Se quebrou, reverte antes de dormir.

---

## 📂 Estrutura de pastas completa

```
corvo-negro/
├── README.md
├── LICENSE
├── .gitignore
├── requirements.txt              # deps compartilhadas
│
├── shared/                       # código usado por server e client
│   ├── __init__.py
│   ├── crypto_utils.py           # SHA-256, RSA, AES, PBKDF2
│   ├── protocol.py               # constantes de comandos, framing TCP
│   ├── models.py                 # dataclasses: User, Forum, Message, Role
│   └── permissions.py            # bitmask de permissões
│
├── server/
│   ├── __init__.py
│   ├── main.py                   # entry point
│   ├── config.py                 # host, porta, paths
│   ├── database.py               # schema + queries SQLite
│   ├── session_manager.py        # dict socket → user_id
│   ├── router.py                 # despachador de mensagens
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── auth.py               # register, login, logout
│   │   ├── forum.py              # create, join, leave, list
│   │   ├── message.py            # send, history, pin, delete
│   │   ├── role.py               # create_role, assign, revoke
│   │   └── key_exchange.py       # distribuição de chaves
│   └── requirements.txt
│
├── client/
│   ├── __init__.py
│   ├── main.py                   # entry point GUI
│   ├── config.py                 # server IP, paths locais
│   ├── network/
│   │   ├── __init__.py
│   │   ├── client_socket.py      # TCP + framing
│   │   ├── lan_discovery.py      # zeroconf mDNS
│   │   ├── mesh_peer.py          # conexões P2P em modo LAN
│   │   └── sync.py               # merge de histórico ao reconectar
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── theme.py              # paleta grimdark + fontes
│   │   ├── login_window.py       # registro + login
│   │   ├── main_window.py        # janela principal
│   │   ├── forum_sidebar.py      # lista de fóruns à esquerda
│   │   ├── chat_view.py          # área central de mensagens
│   │   ├── members_sidebar.py    # membros do fórum à direita
│   │   ├── role_manager.py       # modal de gerenciamento de roles
│   │   ├── create_forum_modal.py
│   │   ├── join_forum_modal.py
│   │   ├── cipher_viewer.py      # popup mostrando o texto cifrado
│   │   └── status_bar.py         # indicador ONLINE/LAN
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── local_db.py           # SQLite local cifrado
│   │   └── key_vault.py          # armazenamento seguro da priv key
│   └── requirements.txt
│
├── tests/
│   ├── __init__.py
│   ├── test_crypto.py
│   ├── test_protocol.py
│   ├── test_auth.py
│   ├── test_forum.py
│   ├── test_e2e.py
│   ├── test_roles.py
│   └── test_sync.py
│
└── docs/
    ├── DEVELOPMENT.md            # este arquivo
    ├── architecture.md           # diagramas e fluxos
    ├── protocol_spec.md          # especificação do protocolo TCP
    ├── decisions.md              # log de decisões técnicas
    └── screenshots/              # para o README e vídeo
```

---

## 🗓 SPRINT 1 — Núcleo Criptográfico e Backend
### Segunda 07/07 → Segunda 13/07 (6 dias úteis, ~55h)

**Meta:** ao fim da sprint, 3 clientes CLI conectam ao servidor, autenticam, criam fóruns, entram por convite, e trocam mensagens criptografadas ponta a ponta.

---

### 📆 Dia 1 — Segunda 07/07 (Setup + Crypto Utils)
**Horas estimadas: 8h**

**Manhã (4h)**
- [ ] Criar repositório `corvo-negro` no GitHub (público)
- [ ] `.gitignore` para Python (nunca committar `.db`, `.env`, `venv/`, `__pycache__`, `*.key`)
- [ ] Criar README.md inicial (usa o pronto)
- [ ] Estrutura de pastas conforme árvore acima
- [ ] `requirements.txt` inicial: `cryptography`, `pytest`
- [ ] Setup do venv, primeiro commit

**Tarde (4h)**
- [ ] Implementar `shared/crypto_utils.py`:
  - `hash_password(password: str) -> bytes` (salt 16B + PBKDF2-HMAC-SHA256, 100k iterações)
  - `verify_password(password: str, stored: bytes) -> bool`
  - `generate_rsa_keypair() -> tuple[bytes, bytes]` (PEM serialization)
  - `rsa_encrypt(data: bytes, public_key_pem: bytes) -> bytes` (OAEP + SHA-256)
  - `rsa_decrypt(ciphertext: bytes, private_key_pem: bytes) -> bytes`
  - `aes_encrypt(plaintext: bytes, key: bytes) -> tuple[bytes, bytes]` (CBC, retorna ciphertext + IV)
  - `aes_decrypt(ciphertext: bytes, key: bytes, iv: bytes) -> bytes`
  - `generate_aes_key() -> bytes` (32 bytes = AES-256)
  - `derive_key_from_password(password: str, salt: bytes) -> bytes` (PBKDF2 para cifrar DB local)
- [ ] `tests/test_crypto.py`:
  - Hash + verify (senha correta e errada)
  - RSA round-trip
  - AES round-trip
  - PBKDF2 determinístico com mesmo salt

**Commit:** `feat: implementa utilitários criptográficos + testes`

---

### 📆 Dia 2 — Terça 08/07 (Socket TCP + Protocolo)
**Horas estimadas: 8-10h**

**Manhã (5h)**
- [ ] `shared/protocol.py`:
  - Constantes de comandos: `CMD_REGISTER`, `CMD_LOGIN`, `CMD_MSG_1V1`, `CMD_CREATE_FORUM`, etc
  - Função `pack_message(dict) -> bytes` — 4 bytes big-endian de tamanho + JSON
  - Função `unpack_message(sock) -> dict` — lê tamanho, depois o payload
- [ ] `server/main.py`:
  - `socket.socket()`, bind, listen
  - `threading.Thread` por cliente
  - Loop `recv` que despacha para router
- [ ] Teste manual: `telnet` ou script Python conectando e mandando mensagem crua

**Tarde (4-5h)**
- [ ] `server/session_manager.py`:
  - Dict `{socket: user_data}` thread-safe (lock)
  - Método para broadcast, unicast, disconnect
- [ ] `client/network/client_socket.py`:
  - Classe `CorvoClient` com métodos `connect`, `send`, `close`
  - Thread de recebimento
  - Queue para passar mensagens ao consumer
- [ ] CLI de teste: `python -m client.cli_test` para conectar e enviar comandos crus
- [ ] Testar 3 clientes conectando simultaneamente

**Commit:** `feat: comunicação TCP com framing e protocolo JSON`

---

### 📆 Dia 3 — Quarta 09/07 (Autenticação)
**Horas estimadas: 8h**

**Manhã (4h)**
- [ ] `server/database.py`:
  - Cria schema SQLite:
    ```sql
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash BLOB NOT NULL,
        public_key BLOB NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ```
  - Funções: `create_user`, `get_user_by_username`, `update_public_key`

**Tarde (4h)**
- [ ] `server/handlers/auth.py`:
  - `handle_register(data, sock)` — valida, cria user, retorna sucesso/erro
  - `handle_login(data, sock)` — verifica hash, cria sessão, retorna user info
  - `handle_logout(data, sock)` — limpa sessão
- [ ] `client`: fluxo CLI de cadastro e login
- [ ] Testes: usuário duplicado, senha errada, login sem cadastro

**Commit:** `feat: autenticação com SHA-256 + PBKDF2`

---

### 📆 Dia 4 — Quinta 10/07 (E2E 1:1)
**Horas estimadas: 8-9h**

**Manhã (4h)**
- [ ] No login, cliente **gera par RSA** e envia public key ao servidor
- [ ] Server armazena public key na tabela `users`
- [ ] Cliente armazena private key localmente **cifrada com a senha** (PBKDF2 → AES-256)
- [ ] Novo comando: `CMD_GET_PUBKEY(username)` — servidor devolve public key de outro user

**Tarde (4-5h)**
- [ ] Comando `CMD_MSG_1V1`:
  - Remetente pede public_key do destinatário
  - Gera AES key aleatória
  - Cifra a mensagem com AES-CBC
  - Cifra a AES key com RSA-OAEP do destinatário
  - Envia `{recipient, ciphertext, encrypted_key, iv, sender}`
- [ ] Servidor apenas rotea (não decifra)
- [ ] Destinatário: decifra AES key com sua RSA, decifra msg com AES
- [ ] Teste: A manda "olá" para B, B mostra "olá" descriptografado no terminal

**Commit:** `feat: mensagens 1:1 com criptografia híbrida RSA+AES`

---

### 📆 Dia 5 — Domingo 12/07 (Fóruns) — sábado é off
**Horas estimadas: 9-10h**

**Manhã (5h)**
- [ ] `shared/models.py`: dataclasses `Forum`, `ForumMember`
- [ ] Schema SQLite:
  ```sql
  CREATE TABLE forums (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      invite_hash BLOB NOT NULL,
      owner_id INTEGER NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (owner_id) REFERENCES users(id)
  );

  CREATE TABLE forum_members (
      forum_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (forum_id, user_id)
  );
  ```
- [ ] Handler `create_forum`:
  - Cliente envia nome
  - Servidor gera código de convite (`CORVO-XXXX-XXXX`)
  - Armazena SHA-256 do código (invite_hash)
  - Retorna o código em claro para o dono compartilhar

**Tarde (4-5h)**
- [ ] Handler `join_forum`:
  - Cliente envia código
  - Servidor compara hash
  - Adiciona à `forum_members`
- [ ] Handler `list_my_forums`
- [ ] Handler `leave_forum`
- [ ] CLI: comandos `/create`, `/join`, `/list`, `/leave`

**Commit:** `feat: sistema de fóruns com convites por hash`

---

### 📆 Dia 6 — Segunda 13/07 (E2E em grupo)
**Horas estimadas: 9-10h**

**Manhã (5h)**
- [ ] Nova tabela:
  ```sql
  CREATE TABLE forum_keys (
      forum_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      encrypted_aes_key BLOB NOT NULL,
      key_version INTEGER NOT NULL DEFAULT 1,
      PRIMARY KEY (forum_id, user_id, key_version)
  );
  ```
- [ ] Ao criar fórum:
  - Dono gera AES key da sala localmente
  - Cifra com sua própria RSA public key
  - Envia ao servidor: `{forum_id, encrypted_aes_key, key_version: 1}`
- [ ] Ao alguém entrar num fórum:
  - Servidor notifica o dono
  - Dono pega public key do novo membro
  - Cifra AES key da sala com essa public key
  - Envia ao servidor para armazenar

**Tarde (4-5h)**
- [ ] Comando `CMD_SEND_TO_FORUM`:
  - Cliente cifra msg com AES do fórum (que ele já tem decifrada em memória)
  - Envia `{forum_id, ciphertext, iv, key_version}`
- [ ] Servidor persiste em `messages(id, forum_id, sender_id, ciphertext, iv, key_version, timestamp)`
- [ ] Servidor rotea para todos os membros online
- [ ] **Rotação de chave** ao alguém sair:
  - Dono gera nova AES
  - Redistribui pra membros restantes
  - `key_version += 1`
- [ ] Comando `CMD_GET_HISTORY(forum_id)` — retorna mensagens; cliente decifra com key da versão correspondente
- [ ] Teste: 3 clientes, 2 fóruns, mensagens circulando, um sai e chave rotaciona

**Commit:** `feat: E2E em grupo com rotação de chave AES`

**🏁 MARCO SPRINT 1:** Chat criptografado multi-sala funcionando em CLI. Se aqui não estiver estável, **não avance** — corrija na terça de manhã antes de começar a Sprint 2.

---

## 🗓 SPRINT 2 — Interface + Roles
### Terça 14/07 → Sexta 17/07 (4 dias úteis, ~35h)

**Meta:** aplicação visual completa com gerenciamento de permissões.

---

### 📆 Dia 7 — Terça 14/07 (Sistema de Roles)
**Horas estimadas: 8h**

**Manhã (4h)**
- [ ] `shared/permissions.py`:
  ```python
  class Permission:
      SEND_MESSAGE = 1
      DELETE_MESSAGE = 2
      PIN_MESSAGE = 4
      SEND_IMAGE = 8
      CREATE_CHANNEL = 16
      KICK_MEMBER = 32
      BAN_MEMBER = 64
      MANAGE_ROLES = 128
      MANAGE_FORUM = 256
      ALL = 511
  ```
- [ ] Schema:
  ```sql
  CREATE TABLE roles (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      forum_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      color TEXT NOT NULL DEFAULT '#8b0000',
      permissions INTEGER NOT NULL DEFAULT 1,
      priority INTEGER DEFAULT 0
  );

  CREATE TABLE member_roles (
      forum_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      role_id INTEGER NOT NULL,
      PRIMARY KEY (forum_id, user_id, role_id)
  );
  ```

**Tarde (4h)**
- [ ] Roles padrão criadas ao criar fórum:
  - `Corvo-Mor` (ALL) — automática para o dono
  - `Escriba` (SEND + DELETE + PIN + KICK)
  - `Iniciado` (SEND)
- [ ] Handlers: `create_role`, `edit_role`, `delete_role`, `assign_role`, `revoke_role`
- [ ] Toda ação sensível checa permissão no servidor **antes** de executar
- [ ] Testes: dono edita role, member sem permissão tenta e é negado

**Commit:** `feat: sistema de roles customizáveis com permissões bitmask`

---

### 📆 Dia 8 — Quarta 15/07 (GUI Base + Tema)
**Horas estimadas: 9-10h**

**Manhã (5h)**
- [ ] `client/ui/theme.py`:
  ```python
  COLORS = {
      "bg_dark": "#0a0a0a",
      "bg_medium": "#1a1a1a",
      "bg_light": "#2a2a2a",
      "accent_crimson": "#8b0000",
      "accent_gold": "#c9a961",
      "text_primary": "#e5d4a1",
      "text_muted": "#7a6d4a",
      "danger": "#a83232",
      "success": "#4a7c3a",
  }
  FONTS = {
      "title": ("Cormorant Garamond", 20, "bold"),
      "body": ("Inter", 12),
      "mono": ("JetBrains Mono", 11),
  }
  ```
- [ ] `client/ui/login_window.py`:
  - CTk window com tabs: "Convocação" (login) e "Novo Corvo" (registro)
  - Campo de servidor (com valor padrão)
  - Botões estilizados em crimson/dourado
  - Feedback de erro em caixa vermelha escura

**Tarde (4-5h)**
- [ ] `client/ui/main_window.py`:
  - Layout de 3 colunas:
    - Esquerda (200px): sidebar de fóruns
    - Centro (flex): chat_view
    - Direita (200px): sidebar de membros
  - Cabeçalho superior: nome do fórum + status ONLINE/LAN
  - Rodapé inferior: nome do usuário logado
- [ ] Placeholders vazios de `forum_sidebar`, `chat_view`, `members_sidebar` (só estrutura)

**Commit:** `feat: GUI base com tema grimdark`

---

### 📆 Dia 9 — Quinta 16/07 (GUI Chat)
**Horas estimadas: 9-10h**

**Manhã (5h)**
- [ ] `client/ui/forum_sidebar.py`:
  - Scrollable frame listando fóruns do usuário
  - Botão "⚜ Criar Fórum" no topo
  - Botão "🎟 Aceitar Convocação" abaixo
  - Click em fórum → carrega no chat_view
- [ ] `client/ui/create_forum_modal.py` e `join_forum_modal.py`
- [ ] `client/ui/chat_view.py`:
  - Área scrollable de mensagens
  - Cada mensagem: avatar-placeholder + nome (colorido pela role) + timestamp + texto + botão 👁 (cipher viewer)
  - Input inferior + botão enviar

**Tarde (4-5h)**
- [ ] `client/ui/members_sidebar.py`:
  - Lista membros do fórum atual agrupados por role
  - Cores das roles visíveis
- [ ] `client/ui/cipher_viewer.py`:
  - Popup modal com o ciphertext em base64
  - Copiável, com fonte JetBrains Mono
  - Título: "🔒 Assim viajou a mensagem"
- [ ] `client/ui/status_bar.py`:
  - Indicador visual do modo: 🟢 ONLINE / 🟡 CONECTANDO / 🔴 LAN
  - Contador de peers em modo LAN

**Commit:** `feat: interface completa de chat e visualização de cifra`

---

### 📆 Dia 10 — Sexta 17/07 (Integração + Polish)
**Horas estimadas: 8-9h**

**Manhã (4h)**
- [ ] Conectar UI ao backend:
  - Thread de rede empurra eventos numa `queue.Queue`
  - UI puxa da queue via `window.after(50, poll_queue)`
  - Nunca chamar widget CTk de outra thread
- [ ] Todos os fluxos: login → main window → criar fórum → conversar

**Tarde (4-5h)**
- [ ] `client/ui/role_manager.py`:
  - Modal listando roles do fórum
  - Formulário de criação/edição com checkboxes de permissões
  - Botão de atribuir a membros
  - Só abre se usuário tem permissão MANAGE_ROLES
- [ ] Feedback visual quando não tem permissão (tooltip "Você não tem essa autoridade")
- [ ] Grava clipe 1: fluxo de login e primeiro chat funcionando

**Commit:** `feat: integração completa GUI + backend, gerenciamento de roles`

**🏁 MARCO SPRINT 2:** Aplicação usável ponta a ponta na versão online. Deve estar bonita, funcional e sem crashes básicos.

---

## 🗓 SPRINT 3 — LAN Mode + Sync + Entrega
### Domingo 19/07 → Terça 21/07 (3 dias úteis, ~28h)

**Meta:** Modo LAN funcional, sync ao voltar online, projeto entregue.

---

### 📆 Dia 11 — Domingo 19/07 (LAN Discovery + Mesh)
**Horas estimadas: 10h**

**Manhã (5h)**
- [ ] Adicionar `zeroconf` ao requirements
- [ ] `client/network/lan_discovery.py`:
  - `LanAdvertiser`: registra serviço `_corvonegro._tcp.local.` com propriedades `{user_id, forums}`
  - `LanBrowser`: escuta anúncios, mantém dict de peers ativos
- [ ] Ao subir cliente:
  - Testa conexão com servidor central (timeout 3s)
  - Se OK → modo ONLINE
  - Se falha → modo LAN, ativa advertiser e browser

**Tarde (5h)**
- [ ] `client/network/mesh_peer.py`:
  - Ao descobrir peer novo, abre TCP direto com ele
  - Handshake: troca de identidades assinadas
  - Verifica se compartilham fóruns
  - Se sim, mantém conexão viva
- [ ] Mensagem em modo LAN:
  - Cifra normal com AES do fórum
  - Envia para todos os peers que também são membros
  - Cada peer recebe e decifra localmente
- [ ] Status bar mostra "🔴 LAN — 3 corvos"

**Commit:** `feat: modo LAN autônomo com descoberta mDNS e mesh P2P`

---

### 📆 Dia 12 — Segunda 20/07 (Sync + Local DB + Vídeo)
**Horas estimadas: 10h**

**Manhã (5h)**
- [ ] `client/storage/local_db.py`:
  - SQLite local: `messages`, `forums`, `roles`, `known_users`
  - Todo o DB cifrado com chave derivada da senha (SQLCipher OU cifragem manual a cada write/read)
  - Simplificação: cifra o **valor** de cada campo sensível ao invés do arquivo inteiro
- [ ] Toda mensagem carrega `uuid` + `origin_timestamp`
- [ ] Cache local guarda todo o histórico visto

**Tarde início (2h)**
- [ ] `client/network/sync.py`:
  - Ao reconectar online:
    1. Envia ao servidor: `{last_seen_msg_id_per_forum}`
    2. Servidor devolve tudo desde esses IDs
    3. Cliente envia ao servidor todas msgs LAN geradas offline (com uuid + timestamp)
    4. Servidor faz insert `INSERT OR IGNORE` (uuid é PK) — resolve duplicatas
  - Ordenação final por timestamp
  - Merge no local_db
- [ ] Documenta no `decisions.md`: "last-write-wins por timestamp, aceitável para escopo acadêmico"

**Tarde final (3h)**
- [ ] Bug hunting:
  - Rodar 3 clientes por 30min
  - Desligar wifi de um, reconectar
  - Ver se sync funciona sem crash
  - Trata todos os except silenciosos
- [ ] Screenshots finais para o README

**Commit:** `feat: sincronização entre modos LAN e online + cache local cifrado`

---

### 📆 Dia 13 — Terça 21/07 (Vídeo + README + Entrega)
**Horas estimadas: 8-10h**

**Manhã (5h)**
- [ ] Finalizar README.md com screenshots reais
- [ ] Escrever `docs/architecture.md` com diagramas Excalidraw
- [ ] Escrever `docs/protocol_spec.md` documentando todos os comandos
- [ ] Ajustar `.gitignore` final (garantir que nada sensível vaza)
- [ ] Verificar histórico de commits (fazer rebase interativo se estiver bagunçado)

**Tarde início (3h) — Gravação do vídeo**
Roteiro (7-9min):
1. **Intro (30s):** "Fala, eu sou o Rafhael, este é o Corvo Negro..."
2. **Arquitetura (1min):** mostra diagrama, explica o híbrido RSA+AES
3. **Demo autenticação (1min):** cadastro, login, mostra hash SHA-256 no banco
4. **Chat online (2min):** cria fórum, gera convite, segundo cliente entra, trocam mensagens, mostra o cipher viewer
5. **Wireshark (1min):** captura TCP em `port 9999`, filtra, mostra que é lixo binário
6. **Roles (1min):** cria role customizada, atribui, mostra membro sem permissão sendo negado
7. **LAN mode (1-2min):** desliga wifi, mostra status mudando pra LAN, chat continua funcionando, religa e sync acontece
8. **Encerramento (30s):** "código no GitHub, obrigado"
- [ ] Grava com OBS
- [ ] Edita cortes básicos (DaVinci Resolve ou CapCut)
- [ ] Upload YouTube não-listado
- [ ] Coloca link no README

**Tarde final:**
- [ ] Preenche o formulário de entrega
- [ ] **ENTREGA** 🎉

**Commit final:** `docs: README final com vídeo demonstrativo`

---

## 📋 Especificação do protocolo TCP

### Framing
```
[4 bytes big-endian: tamanho do payload em bytes][payload JSON UTF-8]
```

### Estrutura das mensagens

**Request cliente → servidor:**
```json
{
    "cmd": "COMMAND_NAME",
    "session_token": "optional_if_authenticated",
    "data": { ... }
}
```

**Response servidor → cliente:**
```json
{
    "cmd": "COMMAND_NAME_RESPONSE",
    "status": "ok" | "error",
    "message": "descrição humana",
    "data": { ... }
}
```

**Broadcast servidor → cliente:**
```json
{
    "cmd": "EVENT_NAME",
    "data": { ... }
}
```

### Comandos principais

| Comando | Direção | Propósito |
|---|---|---|
| `REGISTER` | C→S | Cadastro de novo usuário |
| `LOGIN` | C→S | Autenticação + retorno de session_token |
| `LOGOUT` | C→S | Encerrar sessão |
| `GET_PUBKEY` | C→S | Obter public key de outro user |
| `CREATE_FORUM` | C→S | Criar novo fórum |
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

---

## ✅ Checklist final de entrega

### Código (70pts)
- [ ] Autenticação SHA-256 + PBKDF2 (20pts)
- [ ] RSA-2048 troca segura (25pts)
- [ ] AES-256-CBC (25pts)
- [ ] Socket TCP + roteamento (20pts)
- [ ] Código organizado, docstrings (10pts)

### GitHub (10pts)
- [ ] Repositório público
- [ ] README completo com badges e screenshots
- [ ] `requirements.txt` em cada componente
- [ ] `.gitignore` sem vazamentos
- [ ] 30+ commits semânticos
- [ ] `docs/` com arquitetura e protocolo

### Vídeo (10pts)
- [ ] 5-10 minutos
- [ ] Wireshark demonstrando cifragem
- [ ] Múltiplos clientes
- [ ] Demonstração de LAN mode
- [ ] Publicado no YouTube (não-listado ok)

### Bônus (+5pts)
- [ ] GUI ✅
- [ ] Histórico ✅
- [ ] Múltiplos clientes ✅
- [ ] LAN mode ✅ (extra além do pedido)

**Meta de nota: 110/105**

---

## 🚨 Regras de sobrevivência

1. **Se Sprint 1 atrasar 1 dia →** corta o gerenciamento visual de roles, mantém só 3 roles fixas
2. **Se Sprint 2 atrasar 2 dias →** vídeo mais curto (5min mínimo), corta funcionalidades secundárias
3. **Se LAN mode não funcionar até domingo à noite →** entrega sem ele, mantém no roadmap
4. **Se algo criptográfico quebrar →** para tudo, foca em consertar, o resto pode esperar
5. **Nunca committar depois das 22h.** Bug de fim de noite arrasta pra madrugada. Anota no dia seguinte.

---

## 🎯 Próximo passo agora

**Segunda 07/07, 09h:**
1. Cria o repo no GitHub
2. Copia esses dois arquivos (README.md e docs/DEVELOPMENT.md)
3. Faz o primeiro commit: `chore: setup inicial do projeto`
4. Começa pelo `shared/crypto_utils.py`

Boa jornada, Corvo-Mor. 🜲
