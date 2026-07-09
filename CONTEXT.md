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

**Data:** 09/07/2026 — **Dia 8 da Sprint 2 concluído + rodada grande de polimento de UI/UX e correções de backend de roles/fórum.**

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
- [x] **Dia 7 — Sistema de Roles** (`shared/permissions.py` com bitmask `Permission` + `has_permission`/`combine_masks`, `handlers/role.py` com `create_default_roles`/`assign_default_role_to_new_member`/`handle_create_role`/`handle_assign_role`, roles padrão `Corvo-Mor`/`Escriba`/`Iniciado` criadas automaticamente em `handle_create_forum`, `handle_pin_message`/`handle_delete_message` em `handlers/message.py` com checagem de permissão real, `cli_test.py` com `/createrole /assignrole /pin /delete`, `tests/test_roles.py`) — 18 testes ✅
- [x] **Dia 8 — GUI Base + Tema (design real do Claude Design implementado)**: `theme.py` com os tokens exatos do design (paleta grimdark ritualística preto/dourado/crimson, fontes VT323 + Cormorant Garamond baixadas em `client/assets/fonts/`), `login_window.py` (tabs Convocação/Registro, força de senha, toggle de olho — conectado ao backend real), `main_window.py` (layout 3 colunas: header/forum_sidebar/chat_view/members_sidebar/status_bar), `chat_view.py` (animação de decodificação hash→texto, envio/recebimento cifrado real, histórico em cascata), `cipher_viewer.py` (ciphertext real em base64), `create_forum_modal.py`/`join_forum_modal.py` (funcionais, conectados ao backend), `forum_sidebar.py`/`members_sidebar.py`/`status_bar.py` (dados reais via rede), `client/network/gui_bridge.py` (**novo** — `ClientBridge`, dispatcher de inbox que separa responses de eventos e resolve o problema do `inbox.get()` bloqueante que existia no `cli_test.py`), `client/ui/app_state.py` (**novo** — estado de sessão compartilhado), `client/main.py` (entry point real). Backend: novo comando `CMD_GET_FORUM_MEMBERS` (`handlers/forum.py`) porque a sidebar de membros precisava de dados reais. `tests/test_gui_bridge.py` (6 testes) + 3 novos em `test_forum.py`. — 9 testes novos ✅
- [x] venv de pé (Python **3.14.0**) com deps instaladas

**Ambiente rodando:** 98/98 testes passando (`.\venv\Scripts\python.exe -m pytest`).
**Validado manualmente:** servidor real + múltiplos clientes TCP — DM cifrada ponta a ponta (Dia 4), ciclo completo de fórum (Dia 5), fluxo de grupo com 3 membros e rotação de chave (Dia 6), fluxo de roles (Dia 7), e **GUI real de ponta a ponta** (Dia 8): registro/login reais via `LoginWindow` → `MainWindow` → criar fórum via modal → segundo cliente aceita convocação via modal → mensagens cifradas circulando com animação de decodificação → cipher viewer com ciphertext real → cenário de 3 clientes com um saindo e a chave rotacionando automaticamente, terceiro membro decifrando mensagens antes e depois da rotação. Ver `.claude/skills/verify/SKILL.md` (criada nesta sessão) para o roteiro e gotchas de como dirigir a GUI em testes automatizados.

---

## 🚀 Próximos passos imediatos (ordem)

**Sprint 2 em andamento** (Ter 14/07 → Sex 17/07). Splash/Boot, Gerenciar Ordens e Investir Ordem (que estavam pendentes na atualização anterior deste arquivo) **já foram implementados** — ver `client/ui/splash_window.py` e `client/ui/role_manager.py`. Nesta sessão mais recente o foco foi: reconstrução completa da GUI a partir do handoff de design real (`docs/screenshots/`), depois uma rodada grande de correções de UI/UX e de backend a partir de feedback manual testando a aplicação de ponta a ponta.

### 🐞 Pendência de validação: trava no modal de criar fórum

O usuário reportou a janela travando ao dar Alt+Tab com o modal de criar fórum (`client/ui/create_forum_modal.py`) aberto — mesmo sintoma do bug de `grab_set()` já corrigido em outros modais. **O código já usa `grab_seguro(self)`** (não o `grab_set` bruto), então a correção mais recente de `grab_seguro()` (baseada em `focus_displayof()`, ver linha abaixo) deve cobrir este modal também — **mas isso ainda não foi revalidado em execução real após essa correção mais recente**. Próxima ação: abrir o cliente, testar o modal de criar fórum especificamente com Alt+Tab e clique nos campos, confirmar que não trava mais.

### O que foi corrigido nesta sessão de polimento (bugs reportados testando manualmente)

- **Bug de altura de widgets em `CTkFrame`**: qualquer `CTkFrame` sem `height` explícito herda o default de 200px do customtkinter — isso inflava a sidebar de fóruns, a lista de ordens do `RoleManagerModal`, e cada mensagem do chat (`_MensagemWidget`). Corrigido passando `height=1` explicitamente nos frames-wrapper afetados (padrão a lembrar para qualquer novo item de lista: sempre passar `height` explícito em frames que usam `fill="y"`/`fill="x"` dentro de outro frame, senão herdam 200px).
- **Maximização de todas as janelas + bordas customizadas**: `LoginWindow`, `SplashWindow` e `MainWindow` usam `overrideredirect(True)` com uma barra de título própria (arrastável, com minimizar/fechar) via `montar_janela_sem_moldura()` (novo helper central em `ui_helpers.py` — reaproveitar para qualquer nova janela de nível superior).
- **Ícone sumindo da barra de tarefas do Windows**: janelas `overrideredirect` viram `WS_EX_TOOLWINDOW` por padrão (sem entrada na taskbar). Corrigido com `forcar_icone_taskbar()` em `ui_helpers.py` (troca o extended window style via `ctypes`/`user32`).
- **Trava ao Alt+Tab com um modal aberto**: `grab_set()` bruto não se solta quando o SO tira o foco da aplicação inteira, deixando tudo sem resposta a clique. Corrigido com `grab_seguro()` em `ui_helpers.py`, que faz polling (250ms) de `janela.focus_displayof()` — `None` quando a aplicação perde o foco do SO — e solta/recaptura o grab de acordo. **Tentativas anteriores que NÃO funcionaram**: bind de `<FocusOut>`/`<FocusIn>` no toplevel (dispara também ao trocar foco entre widgets filhos, não só quando o SO tira o foco) e comparação de HWND via `ctypes.windll.user32.GetForegroundWindow()`/`GetParent()`/`GetAncestor()` (os HWNDs não batem de forma confiável com o handle top-level do Tk nesse ambiente).
- **Gradiente de fundo "sumindo"/virando mancha preta em tela cheia**: o raio do gradiente radial em `login_window.py`/`splash_window.py` era calculado a partir de `max(w, h)`, que fica desproporcional em telas largas. Corrigido usando a diagonal da tela (`(w**2+h**2)**0.5`) e uma curva não-linear de interpolação de cor (`t**1.6`).
- **Splash sem borda dourada ao redor do conteúdo**: `SplashWindow` não tinha um card/painel envolvendo a coroa+título+painel de boot (diferente do login, que sempre teve). Corrigido envolvendo tudo num card único com `cantos_dourados()`, igual ao login.
- **Filtro CRT dourado (scanlines)**: implementado via agente de UI/UX especializado — `desenhar_scanlines()` em `ui_helpers.py`, linhas horizontais a cada 3px com alpha simulado de 0.05 sobre `theme.mix(DOURADO, BG_PROFUNDO, ...)`, aplicado em `login_window.py` e `splash_window.py`. Ajustável via `ESPACAMENTO_SCANLINE`/`_SCANLINE_ALPHA` no mesmo arquivo.
- **Header da MainWindow condicional a fórum selecionado**: badge ONLINE, botão ⚙ (configurações) e a sidebar de membros à direita agora ficam ocultos quando nenhum fórum está selecionado (`_atualizar_visibilidade_header_forum()` em `main_window.py`). O botão ⚔ (nunca conectado a nada) e o botão ⏻ de desligar (redundante com o ✕ da barra customizada) foram **removidos** do header.
- **Modal de configurações do fórum** (`client/ui/forum_settings_modal.py`, **novo arquivo**): aberto pelo ⚙ do header. Menu vertical condicional à permissão do usuário no fórum: Convite (regenerar código + copiar, requer `CREATE_INVITE`), Gerenciar Ordens (abre `RoleManagerModal`, requer `MANAGE_ROLES`), Gerenciar Membros (expulsar/banir, requer `KICK_MEMBER`/`BAN_MEMBER`), Editar Fórum (nome+ícone, só dono), Deletar Fórum (confirmação por digitação do nome, só dono).
- **Backend novo para suportar o modal acima**: `CMD_REGENERATE_INVITE`, `CMD_UPDATE_FORUM`, `CMD_DELETE_FORUM`, `CMD_KICK_MEMBER`, `CMD_BAN_MEMBER`, `CMD_LIST_ROLES`, `CMD_UPDATE_ROLE`, `CMD_DELETE_ROLE` (todos em `server/handlers/forum.py`/`server/handlers/role.py`, registrados em `server/router.py`). Nova permissão `Permission.CREATE_INVITE` em `shared/permissions.py` (mudou `ALL` de 511 para 1023). Nova coluna `forums.icon` e nova tabela `forum_bans` no schema (`server/database.py`).
- **Editar/dissolver ordem não funcionava de verdade**: `RoleManagerModal._salvar_ordem()` só fingia salvar quando a role já existia (só criava roles novas de verdade); o botão "DISSOLVER ORDEM" não tinha `command` nenhum. Corrigido conectando ambos a `CMD_UPDATE_ROLE`/`CMD_DELETE_ROLE` novos.
- **Ordem sem membros sumia da lista ao recarregar**: o cliente derivava a lista de roles a partir de `CMD_GET_FORUM_MEMBERS` (só mostra roles com ≥1 portador). Corrigido com `CMD_LIST_ROLES` novo (lista todas as roles do fórum, mesmo vazias).
- **Autor de uma ação não via o próprio efeito refletido**: vários broadcasts (`EVT_ROLE_UPDATED`, `EVT_ROLE_DELETED`, `EVT_FORUM_UPDATED`) usavam `exclude=ctx.sock`, então quem editava não recebia o próprio evento de volta. Removido o `exclude` de `EVT_ROLE_UPDATED`/`EVT_ROLE_DELETED` (o autor também quer ver o resultado); para `EVT_FORUM_UPDATED` (que ainda exclui o autor por design), o callback local de "Editar Fórum" agora chama `self._forum_sidebar.recarregar()` diretamente em vez de depender só do broadcast.
- Padrão a lembrar: **sempre abrir uma instância real do cliente e guiar o usuário até a mudança específica para validação visual em mudanças de UI/UX** — screenshots isolados/scripts de automação headless não substituem isso (várias rodadas desta sessão gastaram tempo tentando validar via screenshot antes de simplesmente subir o cliente).

### Ainda falta pra fechar a Sprint 2

1. **Corrigir o `create_forum_modal.py`** para usar `grab_seguro()` (ver bug conhecido acima).
2. Reconfirmar visualmente, numa única passada, todos os fluxos já mexidos nesta sessão (login → splash → main window → criar fórum → configurações → editar/deletar ordem → kick/ban → editar/deletar fórum) — muita coisa foi corrigida em sequência rápida e vale um teste de ponta a ponta consolidado.
3. Estados de loading do `IMPLEMENTACAO.md` seção 5: skeleton do chat (parece já existir, conferir), banner de sync, toasts, "aguardando aprovação", "sem fóruns" (vazio, com corvo SVG → precisa exportar como PNG), "LAN sem peers" — a maioria só faz sentido plenamente quando a Sprint 3 (LAN) existir.
4. Scanner circular de fóruns na LAN (pedido do usuário) — **combinado explicitamente que fica pra Sprint 3**, quando o discovery real (mDNS/broadcast UDP) existir; não fazer com dados mock antes disso.

### O que já está pronto e reutilizável

- `crypto_utils`: hash/verify de senha, RSA-2048 OAEP, AES-256-CBC, PBKDF2, `public_key_from_private`. **16 testes.**
- `permissions`: bitmask `Permission` (SEND_MESSAGE..MANAGE_FORUM, ALL=511), `has_permission`, `combine_masks`. **3 testes.**
- `protocol`: framing `[4B tamanho][JSON]`, constantes de todos os comandos (auth, key_exchange, forum, mensagens 1:1/grupo, roles, pin/delete), helpers `make_request/make_response/make_event`. **Testado.**
- `SessionManager`: mapa socket→sessão thread-safe, unicast/broadcast, `send_to_user` (roteia só se online), autenticação de sessão.
- `Router`: despacho `cmd → handler` com `register()`; handlers embutidos `PING`/`ECHO` + auth + key_exchange + message + forum + role.
- `CorvoServer`: TCP threaded (1 thread/cliente), testado com múltiplos clientes simultâneos.
- `CorvoClient`: connect/send/close + thread de recv → `inbox` (queue).
- `key_vault`: salva/carrega a private key RSA cifrada (PBKDF2 → AES-256) em `~/.corvo_negro/keys/<user>.key`.
- Mensagens 1:1 (`MSG_1V1`): fluxo híbrido RSA+AES completo, servidor só persiste/roteia ciphertext em `direct_messages`.
- Fóruns: criação com convite `CORVO-XXXX-XXXX` (hash SHA-256, código nunca fica em claro no DB), join/leave/list, notificações `MEMBER_JOINED`/`MEMBER_LEFT` (com `owner_id`/`remaining_members`) só pros membros online.
- E2E em grupo: chave AES por fórum controlada pelo dono (`DISTRIBUTE_KEY`), mensagens de fórum via `SEND_TO_FORUM`/`NEW_MESSAGE`, histórico via `GET_HISTORY` com `key_version` por mensagem, rotação de chave automática ao alguém sair.
- Roles: 3 roles padrão automáticas por fórum, `CREATE_ROLE`/`ASSIGN_ROLE` (requerem `MANAGE_ROLES`), `PIN_MESSAGE`/`DELETE_MESSAGE` com checagem real de permissão (autor sempre pode apagar a própria mensagem).
- `cli_test`: `python -m client.cli_test` (`/register`, `/login`, `/dm`, `/create`, `/join`, `/leave`, `/list`, `/send`, `/history`, `/createrole`, `/assignrole`, `/pin`, `/delete`, `/ping`, `/echo`, `/raw`, `/quit`) — decifra `NEW_DM`/`NEW_MESSAGE` automaticamente e cuida da distribuição/rotação de chave quando o usuário logado é dono do fórum.
- **Design da GUI**: projeto "Corvo Negro briefing design" no Claude Design (ID `44a3ef99-545a-40c4-b190-26b34afb39cf`), 6 mockups `.dc.html` (Login, Splash, Janela Principal, Modais, Estados, Protótipo) + `IMPLEMENTACAO.md` do usuário com tokens exatos, receitas de animação e ordem de implementação sugerida. **Já lido e usado como plano mestre do Dia 8** — reconsultar via `DesignSync` (projeto tipo `PROJECT_TYPE_PROJECT`, precisa de `/design-login` autorizado) para os detalhes de Splash/Modais de Roles/Estados que ainda faltam implementar.
- `client/network/gui_bridge.py::ClientBridge`: dispatcher assíncrono de inbox (`call(cmd, data, on_ok, on_error)` + `on(evento, callback)`), poll via `tk_root.after()`. Resolve a race condition que o `cli_test.py` tinha entre requests e eventos broadcast.
- `client/ui/app_state.py::AppState`: estado de sessão (chave privada, `forum_keys` por versão, `owned_forums`, fórum atual) — substitui o dict global do `cli_test.py`.
- `client/ui/theme.py`: paleta `Cores`, helper `mix()` p/ alpha pré-misturado, `FONTES` (VT323 + Cormorant Garamond em vários pesos), `carregar_fontes()`. Fontes reais em `client/assets/fonts/` (baixadas do Google Fonts, licença OFL).

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
