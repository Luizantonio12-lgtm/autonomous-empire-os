# Arquitetura Mestre — Ecossistema Empresarial Autónomo (A + B + C)

Este repositório contém a implementação completa, modular e executável do teu **Império de Negócios Automatizado**, cobrindo simultaneamente as três frentes solicitadas:

---

## A. Backend Core, Esquema PostgreSQL & Grafo Mestre (`LangGraph` + `FastAPI`)

1. **Persistência Transacional & Razão Imutável (`packages/database/`):**
   - `schema.sql`: DDL nativo **PostgreSQL 16** com 6 tabelas nucleares (`agents_registry`, `tasks_execution`, `financial_ledger`, `approval_requests`, `software_projects`, `omnichannel_interactions`).
   - `models.py` & `session.py`: Modelos **SQLAlchemy 2.0 Async** compatíveis com `postgresql+asyncpg` (em produção Docker) e fallback transparente `sqlite+aiosqlite` (para execução imediata em sandbox).
   - `event_bus.py`: Barramento dual **Redis Streams / PubSub** (`XADD empire:telemetry:stream` + `PUBLISH`) com ring-buffer em memória para streaming **WebSocket** (`<15ms`) no Painel ADM.

2. **Interceptor Financeiro Nativo (`packages/agents/llm_interceptor.py`):**
   - Cada inferência de LLM, execução de computação na Sandbox ou fecho comercial passa obrigatoriamente pelo `FinancialLedgerInterceptor`, debitando o custo exato de tokens (`prompt_tokens` / `completion_tokens`) ou creditando faturação (`REVENUE`) e emitindo eventos `LEDGER_EXPENSE` / `LEDGER_REVENUE` em tempo real.

3. **Grafo de Estado Cíclico (`packages/orchestrator/empire_graph.py`):**
   - Construído sobre `langgraph.graph.StateGraph`.
   - O `master_router_node` recebe qualquer diretriz executiva, verifica sub-agentes dinâmicos criados pelo Meta-Agente e encaminha condicionalmente para os nós departamentais (`finance_node`, `support_node`, `sales_node`, `software_factory_node`, `meta_creator_node`, `dynamic_specialist_node`), gravando o *checkpoint* final em `checkpoint_finalizer_node`.

---

## B. Vertical Slice Executável & Painel Administrativo Central (`apps/command-center`)

- **API Gateway (`apps/api-gateway/main.py`):**
  - `GET /api/dashboard/overview`: Balanço consolidado P&L, registo de agentes, tarefas, aprovações HITL, deploys da Fábrica e interações omnicanal.
  - `POST /api/command/execute`: Consola de Comando Soberano do CEO ligada diretamente ao `StateGraph`.
  - `POST /api/factory/build` & `/api/factory/builds/{project_id}/index.html`: Compilação, teste em Sandbox e alojamento imediato de aplicações e jogos.
  - `POST /api/approvals/{approval_id}/decide`: Autorização soberana (*Human-in-the-Loop*) para instanciar novos sub-agentes.
  - `POST /api/webhooks/evolution`: Receptor nativo de webhooks **Evolution API v2** (`messages.upsert`) para atendimento WhatsApp 24h.
  - `WS /ws/telemetry`: Canal WebSocket bidirecional em tempo real.
- **Painel ADM Web (`apps/command-center/src/App.tsx`):**
  - Construído em **React 18 + TypeScript + Tailwind CSS v4** com proxy reverso nativo (`/api` e `/ws`) e viewport ao vivo para testar/jogar os sistemas criados pela Fábrica sem sair do Dashboard.

---

## C. Especificação Profunda: Fábrica de Software & Meta-Agente

### 1. Fábrica de Software & Runner Isolado (`packages/sandbox_runner/` + `software_factory.py`)
- **Pipeline Determinístico em 4 Estágios:**
  1. `SPECIFYING`: Classificação arquitetural (`GAME_HTML5`, `SAAS_LANDING`, `WEB_APP`) e manifesto de módulos.
  2. `CODING`: Síntese multi-ficheiro limpa (`index.html`, `styles.css`, `app.js`, `backend_core.py`).
  3. `TESTING_SANDBOX`: O `IsolatedSandboxExecutor` isola o diretório `/deployments/{project_id}`, limpa variáveis de ambiente sensíveis (protegendo chaves mestras de API) e executa uma suíte real `unittest` + `ast.parse` + auditoria DOM com *timeout* rígido, contabilizando o custo de computação (`SANDBOX_COMPUTE`).
  4. `DEPLOYED`: Apenas se `exit_code == 0`, publica o artefacto em `/api/factory/builds/{project_id}/index.html` e lança a receita do contrato no Razão Financeiro.

### 2. Meta-Agente Criador de Sub-Agentes (`packages/agents/meta_creator.py`)
- **Fluxo de Auto-Evolução Governada:**
  1. Analisa gargalos operacionais ou diretrizes de expansão do CEO.
  2. Projeta o `Blueprint` completo do novo especialista: `system_prompt`, `tools_manifest`, `max_budget_per_task_usd`, `projected_roi_usd` e gera o ficheiro de código Python correspondente.
  3. Regista um `ApprovalRequest` (`status='PENDING'`) no Painel ADM.
  4. Assim que autorizas com 1 clique no Dashboard, grava o módulo em `packages/agents/dynamic_spawns/{slug}.py`, regista-o em `agents_registry` (`is_dynamic=True`) e o `MasterOrchestratorAgent` passa imediatamente a rotear tarefas para o novo sub-agente sem reiniciar o servidor (*Hot-Spawn*).

---

## Execução em Produção (Docker Compose Completo)

```bash
cp .env.example .env
# Preenche OPENAI_API_KEY / ANTHROPIC_API_KEY / E2B_API_KEY
docker compose up -d --build
```
Serviços provisionados automaticamente:
- **Command Center ADM:** `http://localhost:3000`
- **FastAPI Gateway & Docs:** `http://localhost:8000/docs`
- **Evolution API v2 (WhatsApp):** `http://localhost:8080`
- **PostgreSQL 16:** `localhost:5432`
- **Redis 7 (Streams & PubSub):** `localhost:6379`
