from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.agents.llm_interceptor import FinancialLedgerInterceptor
from packages.database.event_bus import event_bus
from packages.database.models import AgentRegistry, FinancialLedger


class FinanceAgent:
    """
    Agente Financeiro (CFO Autónomo).
    Audita o razão imutável (PostgreSQL), monitoriza margem líquida, custos de tokens/sandbox
    e emite relatórios executivos com recomendações de otimização de ROI.
    """

    AGENT_ID = "agent-finance"

    @classmethod
    async def compute_balance_sheet(cls, db: AsyncSession) -> dict:
        rev_res = await db.execute(
            select(func.coalesce(func.sum(FinancialLedger.amount_usd), 0.0)).where(
                FinancialLedger.entry_type == "REVENUE"
            )
        )
        total_revenue = float(rev_res.scalar() or 0.0)

        exp_res = await db.execute(
            select(func.coalesce(func.sum(FinancialLedger.amount_usd), 0.0)).where(
                FinancialLedger.entry_type == "EXPENSE"
            )
        )
        total_expenses = float(exp_res.scalar() or 0.0)

        llm_res = await db.execute(
            select(func.coalesce(func.sum(FinancialLedger.amount_usd), 0.0)).where(
                FinancialLedger.entry_type == "EXPENSE",
                FinancialLedger.category == "LLM_TOKENS",
            )
        )
        llm_cost = float(llm_res.scalar() or 0.0)

        sandbox_res = await db.execute(
            select(func.coalesce(func.sum(FinancialLedger.amount_usd), 0.0)).where(
                FinancialLedger.entry_type == "EXPENSE",
                FinancialLedger.category == "SANDBOX_COMPUTE",
            )
        )
        sandbox_cost = float(sandbox_res.scalar() or 0.0)

        net_profit = round(total_revenue - total_expenses, 4)
        margin_pct = round((net_profit / total_revenue * 100.0), 2) if total_revenue > 0 else 0.0

        return {
            "total_revenue_usd": round(total_revenue, 2),
            "total_expenses_usd": round(total_expenses, 4),
            "llm_api_cost_usd": round(llm_cost, 4),
            "sandbox_compute_cost_usd": round(sandbox_cost, 4),
            "net_profit_usd": round(net_profit, 2),
            "profit_margin_pct": margin_pct,
        }

    @classmethod
    async def execute_audit(cls, db: AsyncSession, task_id: str, directive: str) -> str:
        await event_bus.publish(
            event_type="FINANCE_AUDIT_START",
            agent_slug="finance-cfo",
            level="INFO",
            message="Iniciando auditoria em tempo real do Razão Contabilístico (Ledger)...",
            payload={"task_id": task_id},
        )

        await FinancialLedgerInterceptor.record_llm_usage(
            db=db,
            agent_id=cls.AGENT_ID,
            task_id=task_id,
            model="gpt-4o-mini",
            prompt_tokens=680,
            completion_tokens=340,
            operation_label="Auditoria P&L, Burn Rate de APIs e Eficiência por Agente",
        )

        sheet = await cls.compute_balance_sheet(db)

        agents_res = await db.execute(select(AgentRegistry))
        agents = agents_res.scalars().all()
        top_spender = max(agents, key=lambda a: a.total_cost_usd or 0.0, default=None)

        summary = (
            f"Balanço Auditado Concluído | Receita Bruta: ${sheet['total_revenue_usd']:,.2f} USD | "
            f"Custos Totais (APIs + Sandboxes): ${sheet['total_expenses_usd']:,.4f} USD | "
            f"Lucro Líquido: ${sheet['net_profit_usd']:,.2f} USD (Margem: {sheet['profit_margin_pct']}%). "
        )
        if top_spender:
            summary += (
                f"Maior consumo de API registado em '{top_spender.name}' "
                f"(${top_spender.total_cost_usd:.4f} USD em {top_spender.tasks_completed} execuções)."
            )

        await event_bus.publish(
            event_type="FINANCE_AUDIT_COMPLETE",
            agent_slug="finance-cfo",
            level="SUCCESS",
            message=summary,
            payload=sheet,
        )
        return summary
