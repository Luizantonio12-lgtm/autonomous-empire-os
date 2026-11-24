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
            title="Modo Caixa 100% Real Ativado",
            content="Apenas liquidações reais confirmadas via Webhook Asaas Pix ou Stripe entram como RECEITA no Ledger Financeiro.",
        )

        # Portfólio Comercial Completo das 11 Empresas SaaS Prontas p/ Vender no Pix (0 simulações financeiras)
        ventures_seed = [
            ("NexusFlow AI", "Clínicas Médicas, Odontológicas & Escritórios", "Atendimento WhatsApp IA 24h, Agendamento Anti-Faltas e Cobrança Pix Automática", 49.00),
            ("ImobZap AI", "Imobiliárias, Corretores de Imóveis & Locação", "Qualificação Automática de Compradores e Inquilinos no WhatsApp 24h, Filtro de Renda/FGTS e Agendamento de Visitas", 52.00),
            ("ReativaCliente Flash AI", "Clínicas, Salões, Oficinas & Comércios com Base de Clientes Inativos", "Campanha Relâmpago de IA no WhatsApp que Chama Clientes Sumidos há +90 Dias e Enche a Agenda em 48 Horas", 44.00),
            ("ParceiroAgência 30% AI", "Agências de Marketing, Gestores de Tráfego Pago & Social Media", "Programa Oficial White-Label & Parceria 30% Recorrente: Coloque Nossa IA de Fechamento WhatsApp nos Seus Clientes", 35.00),
            ("AutoEstética Pro AI", "Estética Automotiva, Vitrificação, Polimento & Insulfilm", "Orçamento Instantâneo por Porte do Veículo no WhatsApp, Agenda de Box e Lembrete Automático de Retorno em 30 Dias", 31.00),
            ("ZapPedido Delivery AI", "Pizzarias, Hamburguerias & Delivery", "Cardápio Inteligente no WhatsApp, Fechamento de Pedido IA e Pagamento Pix na Hora (0% Taxa)", 29.00),
            ("CobraFácil Pix AI", "Academias, Escolas, Personal Trainers, Contabilidades & Mensalidades", "Cobrador Automático Educado no WhatsApp com Pix Copia e Cola que Recupera Inadimplentes sem Constrangimento", 27.00),
            ("OficinaZap AI", "Oficinas Mecânicas, Auto Centers & Troca de Óleo", "Orçamento Rápido no WhatsApp, Aviso Automático de Carro Pronto e Lembrete de Troca de Óleo", 26.02),
            ("TopMapa 5 Estrelas AI", "Negócios Locais, Restaurantes, Clínicas & Lojas Físicas", "Pós-Venda Automático no WhatsApp que Pede Avaliação 5 Estrelas no Google Maps e Coloca Sua Loja em 1º na Cidade", 22.00),
            ("AgendaCorte Pro AI", "Barbearias, Salões de Beleza & Estética", "Agendamento 24h pelo WhatsApp, Lembrete Automático de Horário e Sinal via Pix", 19.00),
            ("PetAgenda AI", "Pet Shops, Banho e Tosa & Clínicas Veterinárias", "Agendamento Automático de Banho e Tosa no WhatsApp, Aviso de Pet Pronto e Cobrança Pix", 17.17),
        ]
        for v_name, v_niche, v_tagline, v_price in ventures_seed:
            await AutonomousVentureBuilder.launch_full_venture(
                db=db,
                name=v_name,
                niche=v_niche,
                tagline=v_tagline,
                monthly_price_usd=v_price,
                initial_customers=0,
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
