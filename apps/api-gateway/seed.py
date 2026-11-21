from sqlalchemy import select

from packages.agents import (
    FinancialLedgerInterceptor,
    GrowthSocialAgent,
    MetaCreatorAgent,
    SoftwareFactoryAgent,
    Support24hAgent,
)
from packages.database.event_bus import event_bus
from packages.database.models import AgentRegistry, ScheduledJob
from packages.database.session import AsyncSessionLocal
from packages.memory import EmpireSemanticMemory
from packages.payments import PaymentGatewayManager
from packages.security import SovereignSecurityGuard
from packages.ventures import AutonomousVentureBuilder

CORE_AGENTS = [
    {
        "id": "agent-master",
        "slug": "master-orchestrator",
        "name": "Agente Orquestrador Mestre",
        "department": "CORE_EXECUTIVE",
        "role_description": "Coordena os 7 departamentos, gere cascata Multi-LLM + pgvector RAG e Scheduler 24/7.",
        "system_prompt": "Coordena os nós do LangGraph com governança estrita de custos e SLA.",
        "model_name": "gpt-4o",
        "tools_manifest": ["langgraph_router", "pgvector_rag", "cron_scheduler_24_7", "killswitch_guard"],
        "tasks_completed": 16,
        "max_budget_per_task_usd": 5.00,
    },
    {
        "id": "agent-finance",
        "slug": "finance-cfo",
        "name": "Agente Financeiro (CFO)",
        "department": "FINANCE",
        "role_description": "Concilia Stripe/Asaas Pix Webhooks, audita custos de APIs/Ads/Sandboxes e protege margens.",
        "system_prompt": "Monitoriza cada cêntimo de API vs Receita e garante margem líquida superior a 85%.",
        "model_name": "deepseek-chat",
        "tools_manifest": ["ledger_auditor", "stripe_checkout_api", "asaas_pix_api", "roas_calculator"],
        "tasks_completed": 11,
        "max_budget_per_task_usd": 1.50,
    },
    {
        "id": "agent-support",
        "slug": "support-24h",
        "name": "Agente de Suporte 24h",
        "department": "SUPPORT",
        "role_description": "Atendimento omnicanal ininterrupto via WhatsApp (Evolution API v2 QR) e E-mail com RAG.",
        "system_prompt": "Resolve tickets técnicos e financeiros em menos de 3 segundos com empatia e precisão.",
        "model_name": "deepseek-chat",
        "tools_manifest": ["evolution_whatsapp_qr", "smtp_imap_bridge", "pgvector_client_ctx"],
        "tasks_completed": 31,
        "max_budget_per_task_usd": 0.50,
    },
    {
        "id": "agent-sales",
        "slug": "sales-closer",
        "name": "Agente de Vendas & Prospecção",
        "department": "SALES",
        "role_description": "Executa prospecção B2B ativa, emite cobranças Pix/Stripe e fecha contratos recorrentes.",
        "system_prompt": "Identifica decisores, conduz cadência consultiva e converte leads em receita.",
        "model_name": "gpt-4o",
        "tools_manifest": ["b2b_lead_scraper", "outbound_sequencer", "rag_playbook", "invoice_issuer"],
        "tasks_completed": 14,
        "max_budget_per_task_usd": 3.00,
    },
    {
        "id": "agent-growth",
        "slug": "growth-social",
        "name": "Agente Tráfego, Social & SEO",
        "department": "GROWTH_SOCIAL",
        "role_description": "Cria e distribui conteúdo viral (LinkedIn, Reels, X), artigos SEO e campanhas Meta/Google Ads.",
        "system_prompt": "Maximiza alcance orgânico, captura leads qualificados e otimiza ROAS continuamente.",
        "model_name": "deepseek-chat",
        "tools_manifest": ["linkedin_publisher", "reels_script_engine", "meta_google_ads", "programmatic_seo"],
        "tasks_completed": 6,
        "max_budget_per_task_usd": 2.50,
    },
    {
        "id": "agent-factory",
        "slug": "software-factory",
        "name": "Fábrica de Software Nível 2",
        "department": "SOFTWARE_FACTORY",
        "role_description": "Programa, auto-corrige falhas (Self-Healing 5x em Sandbox), versiona Git e faz deploy Cloud.",
        "system_prompt": "Gera software limpo, auto-repara erros em sandbox segura, commita no Git e publica.",
        "model_name": "claude-3-5-sonnet",
        "tools_manifest": ["self_healing_loop_5x", "isolated_sandbox_qa", "git_packager", "vercel_deployer"],
        "tasks_completed": 5,
        "max_budget_per_task_usd": 8.00,
    },
    {
        "id": "agent-meta",
        "slug": "meta-creator",
        "name": "Meta-Agente (Criador de Agentes)",
        "department": "META_EVOLUTION",
        "role_description": "Deteta gargalos operacionais, projeta novos sub-agentes e faz hot-spawn após aval do CEO.",
        "system_prompt": "Analisa filas e métricas para propor sub-agentes modulares com código Python auditável.",
        "model_name": "gpt-4o",
        "tools_manifest": ["bottleneck_profiler", "agent_code_synthesizer", "hitl_approval_gate", "graph_hot_loader"],
        "tasks_completed": 3,
        "max_budget_per_task_usd": 4.00,
    },
]

INITIAL_CRON_JOBS = [
    {
        "id": "cron-sales-hunter",
        "name": "Prospecção Outbound B2B Contínua",
        "department": "SALES",
        "directive_template": "Identificar decisores SaaS/Logística e fechar contrato comercial B2B ativo.",
        "interval_seconds": 25,
        "is_enabled": True,
    },
    {
        "id": "cron-growth-engine",
        "name": "Distribuição Conteúdo Viral & SEO",
        "department": "GROWTH_SOCIAL",
        "directive_template": "Publicar campanha de aquisição orgânica B2B no LinkedIn e capturar leads.",
        "interval_seconds": 35,
        "is_enabled": True,
    },
    {
        "id": "cron-cfo-audit",
        "name": "Auditoria Automática de Margem & Tokens",
        "department": "FINANCE",
        "directive_template": "Auditar razão contabilístico, margem líquida e eficiência de APIs.",
        "interval_seconds": 50,
        "is_enabled": True,
    },
]


async def seed_initial_empire_state() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(AgentRegistry).limit(1))
        if existing.scalar_one_or_none() is not None:
            return

        for cfg in CORE_AGENTS:
            db.add(AgentRegistry(**cfg))
        for job_cfg in INITIAL_CRON_JOBS:
            db.add(ScheduledJob(**job_cfg))
        await db.commit()

        await SovereignSecurityGuard.log_audit(
            db,
            "SHIELD_INITIALIZED",
            "Proteção Soberana JWT HS256 + TOTP 2FA (RFC 6238) + Global Kill-Switch armada.",
        )

        await EmpireSemanticMemory.store_memory(
            db=db,
            namespace="CEO_DIRECTIVES",
            source_agent="master-orchestrator",
            title="Diretriz Soberana de Margem & Autonomia",
            content="Priorizar DeepSeek/GPT-4o-mini em tarefas rotineiras e Claude 3.5 Sonnet / GPT-4o em código crítico e fecho comercial B2B, mantendo margem líquida acima de 90%.",
        )

        await FinancialLedgerInterceptor.record_custom_transaction(
            db=db,
            entry_type="REVENUE",
            category="SAAS_SALE",
            amount_usd=4850.00,
            description="Assinaturas Enterprise MRR — Lote Inicial Clientes B2B",
            agent_id="agent-sales",
        )
        await FinancialLedgerInterceptor.record_custom_transaction(
            db=db,
            entry_type="EXPENSE",
            category="INFRASTRUCTURE",
            amount_usd=42.50,
            description="Cluster PostgreSQL pgvector + Redis + Evolution API Gateway",
            agent_id="agent-master",
        )

        await PaymentGatewayManager.create_invoice(
            db=db,
            provider="ASAAS_PIX",
            client_name="Construtora Horizonte S.A.",
            client_email="financeiro@horizontesa.com.br",
            description="Implantação Sistema Web & Agente WhatsApp Dedicado",
            amount_usd=1950.00,
        )
        await PaymentGatewayManager.create_invoice(
            db=db,
            provider="STRIPE",
            client_name="Nordic Cloud Ventures",
            client_email="billing@nordiccloud.io",
            description="Licença Anual SaaS Enterprise + Custom Analytics",
            amount_usd=3400.00,
        )

        # Campanha inicial publicada pelo novo Agente Tráfego, Social & SEO
        await GrowthSocialAgent.launch_campaign(
            db=db,
            task_id=None,
            directive="Lançar campanha B2B executiva sobre automação empresarial com agentes de IA",
            explicit_channel="LINKEDIN_B2B",
            custom_title="Autoridade B2B LinkedIn — Império Autónomo",
        )

        await Support24hAgent.handle_inbound_ticket(
            db=db,
            task_id=None,
            channel="WHATSAPP_EVOLUTION",
            contact_name="Ricardo Almeida (CEO TechSul)",
            contact_handle="+5511988012345",
            message="Olá! Preciso confirmar a ativação da nossa chave API Enterprise e fatura deste mês.",
        )

        await SoftwareFactoryAgent.build_software_project(
            db=db,
            task_id=None,
            name="Neon Cyber Defender",
            specification="Jogo HTML5 Arcade espacial com sistema de waves, escudos, partículas e HUD em tempo real.",
            project_type="GAME_HTML5",
            client_name="Estúdio Lusitânia Digital",
            contract_value_usd=2900.00,
            simulate_fault_healing=True,
        )

        # 1.º Negócio Comercial Flagship construído, publicado e a vender 24/7
        await AutonomousVentureBuilder.launch_full_venture(
            db=db,
            name="NexusFlow AI",
            niche="Clínicas Médicas, Escritórios & E-Commerce B2B",
            tagline="Atendimento WhatsApp IA 24h, Agendamento Anti-Faltas e Cobrança Pix Automática",
            monthly_price_usd=297.00,
            initial_customers=6,
        )

        await MetaCreatorAgent.propose_specialized_agent(
            db=db,
            task_id=None,
            directive="Detetada expansão da Fábrica: criar Agente DevSecOps & Auditoria Contínua de Cibersegurança.",
        )

        await event_bus.publish(
            event_type="EMPIRE_BOOT_READY",
            agent_slug="master-orchestrator",
            level="SUCCESS",
            message="Autonomous Empire v3.0 online: 7 Departamentos, Scheduler 24/7, Growth Social, JWT+2FA & Self-Healing operacionais!",
        )
