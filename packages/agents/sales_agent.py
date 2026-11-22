import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.event_bus import event_bus
from packages.database.models import OmnichannelInteraction
from packages.llm_router import MultiModelLLMGateway
from packages.memory import EmpireSemanticMemory


class SalesProspectingAgent:
    """
    Agente de Vendas & Prospecção Ativa (Modo Caixa 100% Real).
    Gera abordagens comerciais reais via Gemini 3 Flash sem lançar receitas simuladas:
    a receita no Ledger sobe exclusivamente quando faturas Pix/Stripe reais são pagas.
    """

    AGENT_ID = "agent-sales"

    @classmethod
    async def run_outbound_campaign(
        cls,
        db: AsyncSession,
        task_id: str,
        directive: str,
    ) -> dict:
        await event_bus.publish(
            event_type="SALES_PROSPECTING_START",
            agent_slug="sales-closer",
            level="INFO",
            message=f"[Modo Real] Estruturando abordagem comercial B2B: '{directive[:80]}'",
            payload={"task_id": task_id},
        )

        rag_hits = await EmpireSemanticMemory.search_similar(
            db=db, query=directive, namespace="SALES_PLAYBOOK", top_k=2
        )
        playbook_ctx = "; ".join(h["title"] for h in rag_hits) if rag_hits else "Abordagem Direta no WhatsApp + Checkout Pix"

        default_copy = (
            f"Script comercial preparado para '{directive[:90]}'. "
            "Usa a aba 'Caçador de Clientes Reais' para disparar no WhatsApp e emitir cobrança Pix real no Asaas."
        )

        llm_out = await MultiModelLLMGateway.complete(
            db=db,
            agent_id=cls.AGENT_ID,
            task_id=task_id,
            system_prompt=(
                "És o Diretor Comercial B2B do Império Autónomo no Brasil. "
                "Escreve uma mensagem de abordagem pronta para enviar no WhatsApp, curta, humana e focada em fechar no Pix."
            ),
            user_prompt=f"Diretriz: {directive} | Playbook: {playbook_ctx}",
            operation_label="Copywriting & Abordagem Comercial B2B",
            strategy="MARGIN_OPTIMIZED",
            local_fallback_text=default_copy,
        )

        interaction = OmnichannelInteraction(
            id=f"omni-{uuid.uuid4().hex[:10]}",
            channel="OUTBOUND_PLAYBOOK",
            department="SALES",
            contact_name="Playbook Comercial Pronto",
            contact_handle="WhatsApp B2B",
            inbound_message=directive[:240],
            agent_response=llm_out.content[:1500],
            sentiment="HIGH_INTENT",
            deal_stage="OUTBOUND_READY",
            deal_value_usd=0.0,
        )
        db.add(interaction)
        await db.commit()

        await EmpireSemanticMemory.store_memory(
            db=db,
            namespace="SALES_PLAYBOOK",
            source_agent="sales-closer",
            title=f"Abordagem B2B: {directive[:55]}",
            content=llm_out.content[:600],
        )

        summary = f"[Vendas · {llm_out.provider.upper()}] {llm_out.content[:1800]}"
        await event_bus.publish(
            event_type="SALES_PLAYBOOK_READY",
            agent_slug="sales-closer",
            level="SUCCESS",
            message="Abordagem comercial real gerada! Pronta para disparo no WhatsApp (Caixa 100% Real).",
            payload={"provider": llm_out.provider},
        )

        return {"summary": summary, "revenue_usd": 0.0, "client": "Prospecção Real"}
