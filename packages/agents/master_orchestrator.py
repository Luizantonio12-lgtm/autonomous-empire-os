from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.agents.llm_interceptor import FinancialLedgerInterceptor
from packages.database.event_bus import event_bus
from packages.database.models import AgentRegistry


class MasterOrchestratorAgent:
    """
    Agente Orquestrador Mestre (Nó Raiz do LangGraph).
    Classifica a intenção estratégica, verifica agentes dinâmicos criados pelo Meta-Agente
    e encaminha o fluxo de execução para o departamento ideal.
    """

    AGENT_ID = "agent-master"

    @classmethod
    async def route_directive(
        cls,
        db: AsyncSession,
        task_id: str,
        directive: str,
        forced_department: str | None = None,
    ) -> dict:
        await event_bus.publish(
            event_type="ORCHESTRATOR_ROUTING",
            agent_slug="master-orchestrator",
            level="INFO",
            message=f"Analisando diretriz executiva e alocando recursos: '{directive[:90]}'",
            payload={"task_id": task_id},
        )

        # Contabiliza inferência de roteamento do Orquestrador Mestre
        await FinancialLedgerInterceptor.record_llm_usage(
            db=db,
            agent_id=cls.AGENT_ID,
            task_id=task_id,
            model="gpt-4o-mini",
            prompt_tokens=420,
            completion_tokens=165,
            operation_label="Roteamento e Decomposição Estratégica (Orquestrador Mestre)",
        )

        # Se o utilizador especificou um departamento explícito ou um sub-agente dinâmico
        if forced_department and forced_department != "AUTO":
            target = forced_department.upper()
        else:
            text = directive.lower()
            # Verifica primeiro se corresponde a algum sub-agente dinâmico criado pelo Meta-Agente
            dyn_res = await db.execute(
                select(AgentRegistry).where(
                    AgentRegistry.is_dynamic.is_(True),
                    AgentRegistry.status != "PAUSED",
                )
            )
            dynamic_agents = dyn_res.scalars().all()
            matched_dynamic = None
            for da in dynamic_agents:
                keywords = [w.lower() for w in da.name.split() if len(w) > 3] + [
                    da.department.lower()
                ]
                if any(k in text for k in keywords):
                    matched_dynamic = da
                    break

            if matched_dynamic:
                target = f"DYNAMIC:{matched_dynamic.id}"
            elif any(
                k in text
                for k in [
                    "jogo",
                    "game",
                    "site",
                    "landing",
                    "app",
                    "aplicativo",
                    "sistema",
                    "software",
                    "programar",
                    "compilar",
                    "deploy",
                    "saas",
                ]
            ):
                target = "SOFTWARE_FACTORY"
            elif any(
                k in text
                for k in [
                    "meta",
                    "criar agente",
                    "novo agente",
                    "sub-agente",
                    "gargalo",
                    "escalar equipa",
                ]
            ):
                target = "META_CREATOR"
            elif any(
                k in text
                for k in [
                    "conteúdo",
                    "tráfego",
                    "social",
                    "linkedin",
                    "instagram",
                    "reels",
                    "tiktok",
                    "seo",
                    "ads",
                    "post",
                    "viral",
                ]
            ):
                target = "GROWTH_SOCIAL"
            elif any(
                k in text
                for k in [
                    "venda",
                    "lead",
                    "prospec",
                    "cliente novo",
                    "funil",
                    "fechar",
                    "outbound",
                    "comercial",
                ]
            ):
                target = "SALES"
            elif any(
                k in text
                for k in [
                    "suporte",
                    "whatsapp",
                    "evolution",
                    "ticket",
                    "atendimento",
                    "reclama",
                    "ajuda",
                    "email",
                ]
            ):
                target = "SUPPORT"
            elif any(
                k in text
                for k in [
                    "financ",
                    "lucro",
                    "margem",
                    "balanço",
                    "custo",
                    "auditoria",
                    "roi",
                    "caixa",
                ]
            ):
                target = "FINANCE"
            else:
                target = "SALES"

        await event_bus.publish(
            event_type="ORCHESTRATOR_DELEGATED",
            agent_slug="master-orchestrator",
            level="INFO",
            message=f"Diretriz delegada para o nó [{target}] no grafo de execução.",
            payload={"task_id": task_id, "target_node": target},
        )

        return {"target_department": target}
