import uuid
from datetime import datetime, timezone
from typing import Any, TypedDict
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from packages.agents import (
    FinanceAgent,
    GrowthSocialAgent,
    MasterOrchestratorAgent,
    MetaCreatorAgent,
    SalesProspectingAgent,
    SoftwareFactoryAgent,
    Support24hAgent,
)
from packages.database.event_bus import event_bus
from packages.database.models import AgentRegistry, TaskExecution
from packages.database.session import AsyncSessionLocal
from packages.security import SovereignSecurityGuard


class EmpireGraphState(TypedDict, total=False):
    task_id: str
    trace_id: str
    title: str
    directive: str
    forced_department: str | None
    target_department: str
    assigned_agent_id: str
    result_summary: str
    artifacts: dict[str, Any]
    status: str


async def _set_agent_status(agent_id: str, status: str, increment_tasks: bool = False) -> None:
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(AgentRegistry).where(AgentRegistry.id == agent_id))
        agent = res.scalar_one_or_none()
        if agent and agent.status != "PAUSED":
            agent.status = status
            agent.last_heartbeat = datetime.now(timezone.utc)
            if increment_tasks:
                agent.tasks_completed = (agent.tasks_completed or 0) + 1
            await db.commit()
        elif agent and increment_tasks:
            agent.tasks_completed = (agent.tasks_completed or 0) + 1
            await db.commit()


async def master_router_node(state: EmpireGraphState) -> EmpireGraphState:
    await _set_agent_status("agent-master", "RUNNING")
    try:
        async with AsyncSessionLocal() as db:
            routed = await MasterOrchestratorAgent.route_directive(
                db=db,
                task_id=state["task_id"],
                directive=state["directive"],
                forced_department=state.get("forced_department"),
            )
            target = routed["target_department"]
    finally:
        await _set_agent_status("agent-master", "IDLE", increment_tasks=True)

    return {"target_department": target}


def route_condition(state: EmpireGraphState) -> str:
    target = state.get("target_department", "SALES")
    if target.startswith("DYNAMIC:"):
        return "dynamic_specialist_node"
    mapping = {
        "FINANCE": "finance_node",
        "SUPPORT": "support_node",
        "SALES": "sales_node",
        "GROWTH_SOCIAL": "growth_social_node",
        "SOFTWARE_FACTORY": "software_factory_node",
        "META_CREATOR": "meta_creator_node",
    }
    return mapping.get(target, "sales_node")


async def finance_node(state: EmpireGraphState) -> EmpireGraphState:
    await _set_agent_status("agent-finance", "RUNNING")
    try:
        async with AsyncSessionLocal() as db:
            summary = await FinanceAgent.execute_audit(
                db=db,
                task_id=state["task_id"],
                directive=state["directive"],
            )
    finally:
        await _set_agent_status("agent-finance", "IDLE", increment_tasks=True)

    return {
        "assigned_agent_id": "agent-finance",
        "result_summary": summary,
        "status": "COMPLETED",
    }


async def support_node(state: EmpireGraphState) -> EmpireGraphState:
    await _set_agent_status("agent-support", "RUNNING")
    try:
        async with AsyncSessionLocal() as db:
            ticket = await Support24hAgent.handle_inbound_ticket(
                db=db,
                task_id=state["task_id"],
                channel="WHATSAPP_EVOLUTION",
                contact_name="Cliente VIP WhatsApp",
                contact_handle="+5511994028811",
                message=state["directive"],
            )
    finally:
        await _set_agent_status("agent-support", "IDLE", increment_tasks=True)

    return {
        "assigned_agent_id": "agent-support",
        "result_summary": f"Atendimento resolvido via {ticket['channel']}: {ticket['response']}",
        "artifacts": ticket,
        "status": "COMPLETED",
    }


async def sales_node(state: EmpireGraphState) -> EmpireGraphState:
    await _set_agent_status("agent-sales", "RUNNING")
    try:
        async with AsyncSessionLocal() as db:
            outcome = await SalesProspectingAgent.run_outbound_campaign(
                db=db,
                task_id=state["task_id"],
                directive=state["directive"],
            )
    finally:
        await _set_agent_status("agent-sales", "IDLE", increment_tasks=True)

    return {
        "assigned_agent_id": "agent-sales",
        "result_summary": outcome["summary"],
        "artifacts": outcome,
        "status": "COMPLETED",
    }


async def growth_social_node(state: EmpireGraphState) -> EmpireGraphState:
    await _set_agent_status("agent-growth", "RUNNING")
    try:
        async with AsyncSessionLocal() as db:
            camp = await GrowthSocialAgent.launch_campaign(
                db=db,
                task_id=state["task_id"],
                directive=state["directive"],
            )
            summary = (
                f"Campanha {camp.channel} publicada ('{camp.hook_headline[:70]}...'): "
                f"{camp.impressions:,} impressões, {camp.leads_captured} leads e +${camp.attributed_revenue_usd:,.2f} USD gerados."
            )
            artifacts = {"campaign_id": camp.id, "channel": camp.channel}
    finally:
        await _set_agent_status("agent-growth", "IDLE", increment_tasks=True)

    return {
        "assigned_agent_id": "agent-growth",
        "result_summary": summary,
        "artifacts": artifacts,
        "status": "COMPLETED",
    }


async def software_factory_node(state: EmpireGraphState) -> EmpireGraphState:
    await _set_agent_status("agent-factory", "RUNNING")
    try:
        async with AsyncSessionLocal() as db:
            raw_title = state.get("title") or state["directive"][:45]
            proj = await SoftwareFactoryAgent.build_software_project(
                db=db,
                task_id=state["task_id"],
                name=raw_title,
                specification=state["directive"],
                contract_value_usd=2200.00,
            )
            summary = (
                f"Projeto '{proj.name}' [Git #{proj.git_commit_hash}] testado em Sandbox "
                f"({proj.healing_iterations}x) e publicado em {proj.preview_url}."
            )
            artifacts = {
                "project_id": proj.id,
                "preview_url": proj.preview_url,
                "project_type": proj.project_type,
            }
    finally:
        await _set_agent_status("agent-factory", "IDLE", increment_tasks=True)

    return {
        "assigned_agent_id": "agent-factory",
        "result_summary": summary,
        "artifacts": artifacts,
        "status": "COMPLETED" if proj.status == "DEPLOYED" else "FAILED",
    }


async def meta_creator_node(state: EmpireGraphState) -> EmpireGraphState:
    await _set_agent_status("agent-meta", "RUNNING")
    try:
        async with AsyncSessionLocal() as db:
            approval = await MetaCreatorAgent.propose_specialized_agent(
                db=db,
                task_id=state["task_id"],
                directive=state["directive"],
            )
            summary = (
                f"Blueprint '{approval.title}' gerado pelo Meta-Agente. "
                f"Aguardando autorização do Administrador (ID: {approval.id})."
            )
            artifacts = {"approval_id": approval.id}
    finally:
        await _set_agent_status("agent-meta", "IDLE", increment_tasks=True)

    return {
        "assigned_agent_id": "agent-meta",
        "result_summary": summary,
        "artifacts": artifacts,
        "status": "AWAITING_APPROVAL",
    }


async def dynamic_specialist_node(state: EmpireGraphState) -> EmpireGraphState:
    target = state.get("target_department", "")
    dyn_id = target.split(":", 1)[1] if ":" in target else ""
    await _set_agent_status(dyn_id, "RUNNING")
    try:
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(AgentRegistry).where(AgentRegistry.id == dyn_id))
            agent = res.scalar_one_or_none()
            if not agent:
                return {
                    "assigned_agent_id": "agent-master",
                    "result_summary": "Sub-agente dinâmico não encontrado.",
                    "status": "FAILED",
                }
            summary = await MetaCreatorAgent.execute_dynamic_specialist(
                db=db,
                agent=agent,
                task_id=state["task_id"],
                directive=state["directive"],
            )
    finally:
        await _set_agent_status(dyn_id, "IDLE", increment_tasks=True)

    return {
        "assigned_agent_id": dyn_id,
        "result_summary": summary,
        "status": "COMPLETED",
    }


async def checkpoint_finalizer_node(state: EmpireGraphState) -> EmpireGraphState:
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(TaskExecution).where(TaskExecution.id == state["task_id"])
        )
        task = res.scalar_one_or_none()
        if task:
            task.assigned_agent_id = state.get("assigned_agent_id", "agent-master")
            task.status = state.get("status", "COMPLETED")
            task.result_summary = state.get("result_summary", "")
            task.state_snapshot = {
                "target_department": state.get("target_department"),
                "artifacts": state.get("artifacts", {}),
            }
            task.completed_at = datetime.now(timezone.utc)
            await db.commit()
    return state


def build_empire_langgraph():
    workflow = StateGraph(EmpireGraphState)

    workflow.add_node("master_router", master_router_node)
    workflow.add_node("finance_node", finance_node)
    workflow.add_node("support_node", support_node)
    workflow.add_node("sales_node", sales_node)
    workflow.add_node("growth_social_node", growth_social_node)
    workflow.add_node("software_factory_node", software_factory_node)
    workflow.add_node("meta_creator_node", meta_creator_node)
    workflow.add_node("dynamic_specialist_node", dynamic_specialist_node)
    workflow.add_node("checkpoint_finalizer", checkpoint_finalizer_node)

    workflow.add_edge(START, "master_router")
    workflow.add_conditional_edges(
        "master_router",
        route_condition,
        {
            "finance_node": "finance_node",
            "support_node": "support_node",
            "sales_node": "sales_node",
            "growth_social_node": "growth_social_node",
            "software_factory_node": "software_factory_node",
            "meta_creator_node": "meta_creator_node",
            "dynamic_specialist_node": "dynamic_specialist_node",
        },
    )

    for specialist in (
        "finance_node",
        "support_node",
        "sales_node",
        "growth_social_node",
        "software_factory_node",
        "meta_creator_node",
        "dynamic_specialist_node",
    ):
        workflow.add_edge(specialist, "checkpoint_finalizer")

    workflow.add_edge("checkpoint_finalizer", END)
    return workflow.compile()


empire_compiled_graph = build_empire_langgraph()


async def execute_empire_directive(
    directive: str,
    title: str | None = None,
    forced_department: str | None = None,
    priority: str = "HIGH",
) -> dict[str, Any]:
    if SovereignSecurityGuard._kill_switch_active:
        await event_bus.publish(
            event_type="EXECUTION_BLOCKED_KILLSWITCH",
            agent_slug="master-orchestrator",
            level="ERROR",
            message=f"Execução bloqueada pelo Global Kill-Switch: '{directive[:65]}'",
        )
        return {
            "status": "BLOCKED_KILL_SWITCH",
            "result_summary": "Sistema sob bloqueio de emergência (Global Kill-Switch ativo).",
        }

    task_id = f"task-{uuid.uuid4().hex[:8]}"
    trace_id = f"trc-{uuid.uuid4().hex[:10]}"
    resolved_title = title or directive[:72]

    async with AsyncSessionLocal() as db:
        task = TaskExecution(
            id=task_id,
            trace_id=trace_id,
            title=resolved_title,
            directive=directive,
            assigned_agent_id="agent-master",
            department=forced_department or "AUTO",
            priority=priority,
            status="IN_PROGRESS",
        )
        db.add(task)
        await db.commit()

    final_state = await empire_compiled_graph.ainvoke(
        {
            "task_id": task_id,
            "trace_id": trace_id,
            "title": resolved_title,
            "directive": directive,
            "forced_department": forced_department,
            "artifacts": {},
        }
    )
    return dict(final_state)
