import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.event_bus import event_bus
from packages.database.models import AgentRegistry, FinancialLedger, TaskExecution

# Tabela Oficial de Preços por 1M Tokens (USD)
MODEL_PRICING_PER_1M: dict[str, tuple[float, float]] = {
    "gemini-3-flash-preview": (0.0, 0.0),
    "llama-3.3-70b-versatile": (0.0, 0.0),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "claude-3-5-sonnet": (3.00, 15.00),
    "deepseek-chat": (0.14, 0.28),
    "deepseek-reasoner": (0.55, 2.19),
    "o3-mini": (1.10, 4.40),
}


class FinancialLedgerInterceptor:
    """
    Middleware Nativo de Governança Financeira.
    Nenhuma chamada de IA, execução de sandbox ou faturação acontece sem registo
    atómico no PostgreSQL e emissão de telemetria WebSocket.
    """

    @staticmethod
    def compute_token_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        in_rate, out_rate = MODEL_PRICING_PER_1M.get(model, (2.50, 10.00))
        if in_rate == 0.0 and out_rate == 0.0:
            return 0.0
        cost = (prompt_tokens / 1_000_000.0) * in_rate + (completion_tokens / 1_000_000.0) * out_rate
        return round(max(cost, 0.000120), 6)

    @classmethod
    async def record_llm_usage(
        cls,
        db: AsyncSession,
        agent_id: str,
        task_id: str | None,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        operation_label: str,
    ) -> float:
        cost_usd = cls.compute_token_cost(model, prompt_tokens, completion_tokens)

        ledger_entry = FinancialLedger(
            id=f"led-{uuid.uuid4().hex[:10]}",
            entry_type="EXPENSE",
            category="LLM_TOKENS",
            agent_id=agent_id,
            task_id=task_id,
            amount_usd=cost_usd,
            description=f"[{model}] {operation_label} ({prompt_tokens} in / {completion_tokens} out tokens)",
            metadata_json={
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
        )
        db.add(ledger_entry)

        # Atualiza acumulado do agente
        agent_res = await db.execute(select(AgentRegistry).where(AgentRegistry.id == agent_id))
        agent = agent_res.scalar_one_or_none()
        if agent:
            agent.total_cost_usd = round((agent.total_cost_usd or 0.0) + cost_usd, 6)
            agent.last_heartbeat = datetime.now(timezone.utc)

        # Atualiza tarefa se vinculada
        if task_id:
            task_res = await db.execute(select(TaskExecution).where(TaskExecution.id == task_id))
            task = task_res.scalar_one_or_none()
            if task:
                task.tokens_prompt += prompt_tokens
                task.tokens_completion += completion_tokens
                task.execution_cost_usd = round((task.execution_cost_usd or 0.0) + cost_usd, 6)

        await db.commit()

        await event_bus.publish(
            event_type="LEDGER_EXPENSE",
            agent_slug=agent.slug if agent else agent_id,
            level="FINANCE",
            message=f"Custo API contabilizado: -${cost_usd:.5f} USD ({operation_label})",
            payload={"amount_usd": cost_usd, "category": "LLM_TOKENS", "entry_type": "EXPENSE"},
        )
        return cost_usd

    @classmethod
    async def record_custom_transaction(
        cls,
        db: AsyncSession,
        entry_type: str,
        category: str,
        amount_usd: float,
        description: str,
        agent_id: str | None = None,
        task_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> FinancialLedger:
        entry = FinancialLedger(
            id=f"led-{uuid.uuid4().hex[:10]}",
            entry_type=entry_type,
            category=category,
            agent_id=agent_id,
            task_id=task_id,
            amount_usd=round(amount_usd, 6),
            description=description,
            metadata_json=metadata or {},
        )
        db.add(entry)

        if task_id and entry_type == "REVENUE":
            task_res = await db.execute(select(TaskExecution).where(TaskExecution.id == task_id))
            task = task_res.scalar_one_or_none()
            if task:
                task.revenue_generated_usd = round((task.revenue_generated_usd or 0.0) + amount_usd, 2)

        if agent_id and entry_type == "EXPENSE":
            agent_res = await db.execute(select(AgentRegistry).where(AgentRegistry.id == agent_id))
            agent = agent_res.scalar_one_or_none()
            if agent:
                agent.total_cost_usd = round((agent.total_cost_usd or 0.0) + amount_usd, 6)

        await db.commit()

        sign = "+" if entry_type == "REVENUE" else "-"
        await event_bus.publish(
            event_type=f"LEDGER_{entry_type}",
            agent_slug=agent_id or "agent-finance",
            level="SUCCESS" if entry_type == "REVENUE" else "FINANCE",
            message=f"Transação {category}: {sign}${amount_usd:.2f} USD — {description}",
            payload={"amount_usd": amount_usd, "category": category, "entry_type": entry_type},
        )
        return entry
