-- ============================================================================
-- AUTONOMOUS BUSINESS EMPIRE v2.0 — POSTGRESQL 16 + PGVECTOR CORE SCHEMA
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 1. REGISTO CENTRAL DE AGENTES (Estáticos + Gerados pelo Meta-Agente)
CREATE TABLE IF NOT EXISTS agents_registry (
    id VARCHAR(64) PRIMARY KEY,
    slug VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(120) NOT NULL,
    department VARCHAR(64) NOT NULL,
    role_description TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    model_name VARCHAR(64) NOT NULL DEFAULT 'gpt-4o',
    tools_manifest JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'IDLE',
    is_dynamic BOOLEAN NOT NULL DEFAULT FALSE,
    created_by VARCHAR(64) NOT NULL DEFAULT 'SYSTEM',
    tasks_completed INTEGER NOT NULL DEFAULT 0,
    success_rate NUMERIC(5,2) NOT NULL DEFAULT 100.00,
    total_cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0.000000,
    max_budget_per_task_usd NUMERIC(10,4) NOT NULL DEFAULT 5.0000,
    last_heartbeat TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. EXECUÇÃO DE TAREFAS & CHECKPOINTS DO ORQUESTRADOR (LangGraph)
CREATE TABLE IF NOT EXISTS tasks_execution (
    id VARCHAR(64) PRIMARY KEY,
    trace_id VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    directive TEXT NOT NULL,
    assigned_agent_id VARCHAR(64) REFERENCES agents_registry(id),
    department VARCHAR(64) NOT NULL,
    priority VARCHAR(16) NOT NULL DEFAULT 'HIGH',
    status VARCHAR(32) NOT NULL DEFAULT 'QUEUED',
    state_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_summary TEXT,
    llm_provider_used VARCHAR(48) DEFAULT 'local-router',
    tokens_prompt INTEGER NOT NULL DEFAULT 0,
    tokens_completion INTEGER NOT NULL DEFAULT 0,
    execution_cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0.000000,
    revenue_generated_usd NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks_execution(status);
CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks_execution(assigned_agent_id);

-- 3. RAZÃO CONTABILÍSTICO IMUTÁVEL (Financial Ledger)
CREATE TABLE IF NOT EXISTS financial_ledger (
    id VARCHAR(64) PRIMARY KEY,
    entry_type VARCHAR(16) NOT NULL CHECK (entry_type IN ('REVENUE', 'EXPENSE')),
    category VARCHAR(64) NOT NULL,
    agent_id VARCHAR(64) REFERENCES agents_registry(id),
    task_id VARCHAR(64) REFERENCES tasks_execution(id),
    amount_usd NUMERIC(12,6) NOT NULL CHECK (amount_usd >= 0),
    currency VARCHAR(8) NOT NULL DEFAULT 'USD',
    description TEXT NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ledger_type_created ON financial_ledger(entry_type, created_at DESC);

-- 4. PEDIDOS DE APROVAÇÃO HUMANA (Human-in-the-Loop)
CREATE TABLE IF NOT EXISTS approval_requests (
    id VARCHAR(64) PRIMARY KEY,
    request_type VARCHAR(64) NOT NULL,
    requested_by_agent VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    rationale TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    estimated_cost_usd NUMERIC(10,4) NOT NULL DEFAULT 0.0000,
    projected_roi_usd NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. FÁBRICA DE SOFTWARE NÍVEL 2 — SELF-HEALING, GIT & CLOUD DEPLOY
CREATE TABLE IF NOT EXISTS software_projects (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(160) NOT NULL,
    project_type VARCHAR(48) NOT NULL,
    client_name VARCHAR(120) NOT NULL DEFAULT 'Interno / Império',
    specification TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'SPECIFYING',
    sandbox_exit_code INTEGER,
    healing_iterations INTEGER NOT NULL DEFAULT 1,
    healing_log JSONB NOT NULL DEFAULT '[]'::jsonb,
    git_commit_hash VARCHAR(32),
    test_report TEXT,
    files_manifest JSONB NOT NULL DEFAULT '[]'::jsonb,
    preview_url VARCHAR(255),
    external_deploy_url VARCHAR(255),
    contract_value_usd NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    build_cost_usd NUMERIC(10,6) NOT NULL DEFAULT 0.000000,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. CRM DE VENDAS & TICKETS OMNICANAL (WhatsApp Evolution API + E-mail)
CREATE TABLE IF NOT EXISTS omnichannel_interactions (
    id VARCHAR(64) PRIMARY KEY,
    channel VARCHAR(32) NOT NULL,
    department VARCHAR(32) NOT NULL,
    contact_name VARCHAR(120) NOT NULL,
    contact_handle VARCHAR(120) NOT NULL,
    inbound_message TEXT NOT NULL,
    agent_response TEXT NOT NULL,
    sentiment VARCHAR(24) NOT NULL DEFAULT 'NEUTRAL',
    deal_stage VARCHAR(32) NOT NULL DEFAULT 'OPEN',
    deal_value_usd NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. MEMÓRIA VETORIAL DE LONGO PRAZO (pgvector RAG para todos os Agentes)
CREATE TABLE IF NOT EXISTS semantic_memory (
    id VARCHAR(64) PRIMARY KEY,
    namespace VARCHAR(64) NOT NULL, -- SALES_PLAYBOOK, FACTORY_PATTERNS, CLIENT_CONTEXT, CEO_DIRECTIVES
    source_agent VARCHAR(64) NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    embedding_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    embedding_pg vector(1536), -- Nativo pgvector em PostgreSQL
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_namespace ON semantic_memory(namespace);

-- 8. FATURAS & COBRANÇAS REAIS (Stripe Checkout + Asaas Pix/Boleto)
CREATE TABLE IF NOT EXISTS payment_invoices (
    id VARCHAR(64) PRIMARY KEY,
    provider VARCHAR(32) NOT NULL, -- STRIPE, ASAAS_PIX
    external_id VARCHAR(120) NOT NULL,
    client_name VARCHAR(140) NOT NULL,
    client_email VARCHAR(140) NOT NULL,
    description TEXT NOT NULL,
    amount_usd NUMERIC(12,2) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'PENDING', -- PENDING, PAID, CANCELED
    checkout_url TEXT,
    pix_copy_paste TEXT,
    pix_qr_svg TEXT,
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. COFRE DE INTEGRAÇÕES & CREDENCIAIS RUNTIME
CREATE TABLE IF NOT EXISTS runtime_vault (
    key_name VARCHAR(80) PRIMARY KEY,
    secret_value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 10. SCHEDULER AUTÓNOMO 24/7 (Cron Pipelines & Piloto Automático)
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(140) NOT NULL,
    department VARCHAR(64) NOT NULL,
    directive_template TEXT NOT NULL,
    interval_seconds INTEGER NOT NULL DEFAULT 60,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    runs_count INTEGER NOT NULL DEFAULT 0,
    last_run_at TIMESTAMPTZ,
    last_result TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 11. CAMPANHAS DE TRÁFEGO, CONTEÚDO SOCIAL & SEO PROGRAMÁTICO
CREATE TABLE IF NOT EXISTS growth_campaigns (
    id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(180) NOT NULL,
    channel VARCHAR(48) NOT NULL, -- LINKEDIN_B2B, INSTAGRAM_REELS, META_GOOGLE_ADS, SEO_ARTICLE, X_THREAD
    target_audience VARCHAR(160) NOT NULL,
    hook_headline VARCHAR(240) NOT NULL,
    content_body TEXT NOT NULL,
    cta_url VARCHAR(255) NOT NULL,
    impressions INTEGER NOT NULL DEFAULT 0,
    clicks INTEGER NOT NULL DEFAULT 0,
    leads_captured INTEGER NOT NULL DEFAULT 0,
    ad_spend_usd NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    attributed_revenue_usd NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    status VARCHAR(32) NOT NULL DEFAULT 'PUBLISHED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 12. AUDITORIA DE SEGURANÇA SOBERANA CEO (JWT, 2FA TOTP & Kill-Switch)
CREATE TABLE IF NOT EXISTS security_audit_logs (
    id VARCHAR(64) PRIMARY KEY,
    action VARCHAR(64) NOT NULL,
    actor VARCHAR(80) NOT NULL DEFAULT 'CEO_ADMIN',
    ip_hint VARCHAR(64) NOT NULL DEFAULT '0.0.0.0',
    details TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 13. PORTFÓLIO DE EMPRESAS & PRODUTOS COMERCIAIS (Venture Builder Holding)
CREATE TABLE IF NOT EXISTS business_ventures (
    id VARCHAR(64) PRIMARY KEY,
    codename VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(160) NOT NULL,
    niche VARCHAR(140) NOT NULL,
    tagline VARCHAR(255) NOT NULL,
    monthly_price_usd NUMERIC(10,2) NOT NULL DEFAULT 197.00,
    active_customers INTEGER NOT NULL DEFAULT 0,
    mrr_usd NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    total_revenue_usd NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    software_project_id VARCHAR(64) REFERENCES software_projects(id),
    dedicated_agent_id VARCHAR(64) REFERENCES agents_registry(id),
    public_url VARCHAR(255),
    status VARCHAR(32) NOT NULL DEFAULT 'SCALING', -- BUILDING, LIVE, SCALING, PAUSED
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


