import random
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from packages.agents.llm_interceptor import FinancialLedgerInterceptor
from packages.database.event_bus import event_bus
from packages.database.models import GrowthCampaign
from packages.llm_router import MultiModelLLMGateway
from packages.memory import EmpireSemanticMemory


class GrowthSocialAgent:
    """
    Agente de Tráfego, Conteúdo Social & SEO Programático (CMO Autónomo).
    Cria e publica ativos de aquisição orgânica e paga (LinkedIn B2B, Reels/TikTok,
    X Threads, Artigos SEO e Meta/Google Ads), alimentando o funil de Vendas 24/7.
    """

    AGENT_ID = "agent-growth"

    CAMPAIGN_TEMPLATES = {
        "LINKEDIN_B2B": {
            "audience": "CEOs, CTOs e Diretores de Operações B2B",
            "hook": "Como substituímos 14 processos manuais por um Grafo Multi-Agente com 98% de margem líquida",
            "body": (
                "1. O modelo tradicional de escalar equipas operacionais quebrou.\n"
                "2. Construímos uma arquitetura LangGraph + Sandbox QA que opera Vendas, Suporte 24h e Engenharia em paralelo.\n"
                "3. Resultado em 30 dias: tempo de resposta <3s no WhatsApp e software entregue já auditado em Sandbox.\n\n"
                "Queres ver a arquitetura ao vivo na tua operação? Comenta 'ARQUITETURA' ou acede ao simulador abaixo."
            ),
            "ad_spend": 0.0,
        },
        "INSTAGRAM_REELS": {
            "audience": "Fundadores SaaS, Agências Digitais & E-Commerces",
            "hook": "[Roteiro Reels 45s] Olha o que acontece quando 7 Agentes de IA gerem uma empresa inteira em tempo real...",
            "body": (
                "[00-05s] Hook visual no Command Center mostrando saldo subindo via Webhook Pix.\n"
                "[05-20s] Demonstração da Fábrica de Software corrigindo um bug sozinha na Iteração #2 (Self-Healing).\n"
                "[20-35s] Agente WhatsApp 24h fechando lead e gerando QR Code automático.\n"
                "[35-45s] CTA direto: Link na bio para diagnóstico autónomo gratuito."
            ),
            "ad_spend": 0.0,
        },
        "META_GOOGLE_ADS": {
            "audience": "Empresas procurando Software Sob Medida & Automação IA (High-Intent)",
            "hook": "Software, Apps e Atendimento IA Entregues 10x Mais Rápido — Garantia Sandbox QA",
            "body": (
                "Anúncio Search + Retargeting Dinâmico:\n"
                "• Headline 1: Fábrica de Software Autónoma B2B\n"
                "• Headline 2: Atendimento WhatsApp IA 24/7 Integrado\n"
                "• Copy: Reduza custos operacionais em até 74% com agentes especializados auditados ao cêntimo."
            ),
            "ad_spend": 18.50,
        },
        "SEO_ARTICLE": {
            "audience": "Tráfego Orgânico Google (Decisores Técnicos & Financeiros)",
            "hook": "Guia Definitivo 2026: Orquestração Empresarial com LangGraph, pgvector e Self-Healing",
            "body": (
                "Artigo pilar de 2.400 palavras otimizado para intenção comercial (Schema FAQ + JSON-LD):\n"
                "- Comparativo de ROI: Operação Tradicional vs Sistemas Multi-Agente\n"
                "- Governança Financeira ao Token e Isolamento de Código Seguro\n"
                "- Calculadora interativa embutida para captura de leads B2B."
            ),
            "ad_spend": 0.0,
        },
        "X_THREAD": {
            "audience": "Tech Founders, Indie Hackers & Investidores",
            "hook": "Construímos um sistema autónomo onde o Meta-Agente deteta gargalos e programa novos agentes sozinho. Thread aberta 🧵👇",
            "body": (
                "1/7 A maioria usa IA apenas como chat. Nós ligámos IA diretamente ao PostgreSQL, Redis, Sandbox e Stripe.\n"
                "2/7 Cada chamada de API passa por um Interceptor Financeiro que calcula margem em tempo real.\n"
                "3/7 Quando o tráfego cresce, o Meta-Agente propõe um novo especialista e faz Hot-Spawn com 1 clique do CEO."
            ),
            "ad_spend": 0.0,
        },
    }

    @classmethod
    def _pick_channel(cls, directive: str, explicit_channel: str | None = None) -> str:
        if explicit_channel and explicit_channel in cls.CAMPAIGN_TEMPLATES:
            return explicit_channel
        low = directive.lower()
        if any(w in low for w in ["ads", "tráfego pago", "meta", "google ads", "anúncio"]):
            return "META_GOOGLE_ADS"
        if any(w in low for w in ["instagram", "reels", "tiktok", "vídeo", "viral"]):
            return "INSTAGRAM_REELS"
        if any(w in low for w in ["seo", "artigo", "blog", "orgânico"]):
            return "SEO_ARTICLE"
        if any(w in low for w in ["twitter", "thread", "x.com"]):
            return "X_THREAD"
        return "LINKEDIN_B2B"

    @classmethod
    async def launch_campaign(
        cls,
        db: AsyncSession,
        task_id: str | None,
        directive: str,
        explicit_channel: str | None = None,
        custom_title: str | None = None,
    ) -> GrowthCampaign:
        channel = cls._pick_channel(directive, explicit_channel)
        tpl = cls.CAMPAIGN_TEMPLATES[channel]
        title = custom_title or f"Campanha {channel}: {directive[:55]}"

        await event_bus.publish(
            event_type="GROWTH_CAMPAIGN_START",
            agent_slug="growth-social",
            level="INFO",
            message=f"[Growth & Social] Sintetizando ativo viral/aquisição em {channel}: '{title}'",
            payload={"channel": channel},
        )

        llm_res = await MultiModelLLMGateway.complete(
            db=db,
            agent_id=cls.AGENT_ID,
            task_id=task_id,
            system_prompt="És o CMO Autónomo especialista em Growth B2B, Copywriting Viral, SEO Programático e Performance Ads.",
            user_prompt=f"Canal: {channel}\nPúblico: {tpl['audience']}\nDiretriz: {directive}",
            operation_label=f"Criação & Distribuição de Campanha ({channel})",
            strategy="MARGIN_OPTIMIZED",
            local_fallback_text=tpl["body"],
        )

        campaign = GrowthCampaign(
            id=f"cmp-{uuid.uuid4().hex[:8]}",
            title=title,
            channel=channel,
            target_audience=tpl["audience"],
            hook_headline=tpl["hook"],
            content_body=llm_res.content[:1800],
            cta_url="https://autonomous-empire-os.onrender.com",
            impressions=0,
            clicks=0,
            leads_captured=0,
            ad_spend_usd=0.0,
            attributed_revenue_usd=0.0,
            status="READY_TO_POST",
        )
        db.add(campaign)
        await db.commit()

        await EmpireSemanticMemory.store_memory(
            db=db,
            namespace="SALES_PLAYBOOK",
            source_agent="growth-social",
            title=f"Criativo {channel}: {title[:45]}",
            content=llm_res.content[:600],
        )

        await event_bus.publish(
            event_type="GROWTH_CAMPAIGN_PUBLISHED",
            agent_slug="growth-social",
            level="SUCCESS",
            message=f"Criativo [{channel}] pronto para publicação ({llm_res.provider.upper()} • Custo $0.00)!",
            payload={"campaign_id": campaign.id, "leads": 0, "revenue": 0.0},
        )
        return campaign
