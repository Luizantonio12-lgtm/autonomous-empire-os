import asyncio
import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

GATEWAY_DIR = Path(__file__).resolve().parent
MONOREPO_ROOT = GATEWAY_DIR.parents[1]
for p in (str(MONOREPO_ROOT), str(GATEWAY_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from seed import seed_initial_empire_state as run_seed  # noqa: E402
from packages.agents import (  # noqa: E402
    FinanceAgent,
    GrowthSocialAgent,
    MetaCreatorAgent,
    SoftwareFactoryAgent,
    Support24hAgent,
)
from packages.database import (  # noqa: E402
    AgentRegistry,
    ApprovalRequest,
    BusinessVenture,
    FinancialLedger,
    GrowthCampaign,
    OmnichannelInteraction,
    PaymentInvoice,
    ScheduledJob,
    SecurityAuditLog,
    SemanticMemoryChunk,
    SoftwareProject,
    TaskExecution,
    event_bus,
    get_db,
    init_database,
)
from packages.integrations import EvolutionWhatsAppManager  # noqa: E402
from packages.leads import AutonomousOutreachEngine, RealLeadHunter  # noqa: E402
from packages.llm_router import ConfigVault  # noqa: E402
from packages.memory import EmpireSemanticMemory  # noqa: E402
from packages.orchestrator import execute_empire_directive  # noqa: E402
from packages.payments import PaymentGatewayManager  # noqa: E402
from packages.sandbox_runner import DEPLOYMENTS_ROOT  # noqa: E402
from packages.scheduler import AutonomousSchedulerDaemon  # noqa: E402
from packages.security import SovereignSecurityGuard  # noqa: E402
from packages.ventures import AutonomousVentureBuilder  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_database()
    await event_bus.connect_redis_if_available()
    await run_seed()
    AutonomousSchedulerDaemon.start_background_worker()
    yield
    await AutonomousSchedulerDaemon.stop_background_worker()


app = FastAPI(
    title="Autonomous Business Empire v3.0 — API Gateway",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEPLOYMENTS_ROOT.mkdir(parents=True, exist_ok=True)
app.mount(
    "/api/factory/builds",
    StaticFiles(directory=str(DEPLOYMENTS_ROOT), html=True),
    name="factory_builds",
)


# ============================================================================
# SCHEMAS PYDANTIC
# ============================================================================
class CommandDirectiveRequest(BaseModel):
    directive: str = Field(..., min_length=3)
    title: str | None = None
    department: str = "AUTO"
    priority: str = "HIGH"


class FactoryBuildRequest(BaseModel):
    name: str = Field(..., min_length=2)
    project_type: str = "GAME_HTML5"
    specification: str = Field(..., min_length=5)
    client_name: str = "Cliente Enterprise B2B"
    contract_value_usd: float = 2400.00
    simulate_fault_healing: bool = False


class ApprovalDecisionRequest(BaseModel):
    approve: bool


class AgentConfigPatchRequest(BaseModel):
    status: str | None = None
    max_budget_per_task_usd: float | None = None


class EvolutionWebhookPayload(BaseModel):
    event: str = "messages.upsert"
    contact_name: str = "Cliente WhatsApp"
    contact_handle: str = "+5511999887766"
    message: str = "Olá, gostaria de suporte sobre a minha subscrição."
    data: dict[str, Any] | None = None


class CreateInvoiceRequest(BaseModel):
    provider: str = "ASAAS_PIX"
    client_name: str = Field(..., min_length=2)
    client_email: str = "financeiro@cliente.com"
    description: str = Field(..., min_length=3)
    amount_usd: float = Field(..., gt=0)


class PairWhatsAppRequest(BaseModel):
    phone_number: str = "5516993862008"


class StoreMemoryRequest(BaseModel):
    namespace: str = "CEO_DIRECTIVES"
    title: str = Field(..., min_length=3)
    content: str = Field(..., min_length=5)


class VaultSecretUpdateRequest(BaseModel):
    key_name: str
    value: str


class AutopilotToggleRequest(BaseModel):
    enabled: bool


class CreateScheduledJobRequest(BaseModel):
    name: str = Field(..., min_length=3)
    department: str = "SALES"
    directive_template: str = Field(..., min_length=5)
    interval_seconds: int = Field(default=30, ge=10)


class ToggleJobRequest(BaseModel):
    is_enabled: bool


class LaunchGrowthCampaignRequest(BaseModel):
    title: str = Field(..., min_length=3)
    channel: str = "LINKEDIN_B2B"
    directive: str = Field(..., min_length=5)


class SecurityLoginRequest(BaseModel):
    password: str
    totp_code: str


class KillSwitchRequest(BaseModel):
    engage: bool


class LaunchVentureRequest(BaseModel):
    name: str = Field(..., min_length=2)
    niche: str = Field(..., min_length=3)
    tagline: str = Field(..., min_length=5)
    monthly_price_usd: float = Field(default=297.0, gt=0)
    initial_customers: int = Field(default=3, ge=0)


class VentureCheckoutRequest(BaseModel):
    customer_name: str = Field(..., min_length=2)
    customer_email: str = "cliente@empresa.com"
    customer_phone: str = "+5511999999999"
    provider: str = "ASAAS_PIX"


# ============================================================================
# OVERVIEW CONSOLIDADO v3.0
# ============================================================================
@app.get("/api/health")
async def health_check():
    return {
        "status": "ONLINE",
        "version": "3.0.0",
        "departments": 7,
        "autopilot": AutonomousSchedulerDaemon.get_state(),
        "kill_switch": SovereignSecurityGuard._kill_switch_active,
    }


@app.get("/api/system/export-monorepo.zip")
async def export_full_monorepo_zip():
    export_zip = MONOREPO_ROOT.parent / "autonomous-empire-production-ready.zip"
    if not export_zip.exists():
        raise HTTPException(status_code=404, detail="Pacote de produção ainda não empacotado.")
    return FileResponse(
        path=str(export_zip),
        media_type="application/zip",
        filename="autonomous-empire-production-ready.zip",
    )


@app.get("/api/dashboard/overview")
async def get_dashboard_overview(db: AsyncSession = Depends(get_db)):
    balance = await FinanceAgent.compute_balance_sheet(db)

    agents_res = await db.execute(select(AgentRegistry).order_by(AgentRegistry.created_at.asc()))
    agents = [
        {
            "id": a.id,
            "slug": a.slug,
            "name": a.name,
            "department": a.department,
            "role_description": a.role_description,
            "model_name": a.model_name,
            "tools_manifest": a.tools_manifest,
            "status": a.status,
            "is_dynamic": a.is_dynamic,
            "created_by": a.created_by,
            "tasks_completed": a.tasks_completed,
            "success_rate": a.success_rate,
            "total_cost_usd": round(a.total_cost_usd or 0.0, 4),
            "max_budget_per_task_usd": a.max_budget_per_task_usd,
        }
        for a in agents_res.scalars().all()
    ]

    ledger_res = await db.execute(
        select(FinancialLedger).order_by(desc(FinancialLedger.created_at)).limit(45)
    )
    ledger = [
        {
            "id": l.id,
            "entry_type": l.entry_type,
            "category": l.category,
            "agent_id": l.agent_id,
            "amount_usd": l.amount_usd,
            "description": l.description,
            "created_at": l.created_at.isoformat() if l.created_at else "",
        }
        for l in ledger_res.scalars().all()
    ]

    tasks_res = await db.execute(
        select(TaskExecution).order_by(desc(TaskExecution.started_at)).limit(25)
    )
    tasks = [
        {
            "id": t.id,
            "trace_id": t.trace_id,
            "title": t.title,
            "directive": t.directive,
            "assigned_agent_id": t.assigned_agent_id,
            "department": t.department,
            "priority": t.priority,
            "status": t.status,
            "result_summary": t.result_summary,
            "execution_cost_usd": round(t.execution_cost_usd or 0.0, 5),
            "revenue_generated_usd": round(t.revenue_generated_usd or 0.0, 2),
            "started_at": t.started_at.isoformat() if t.started_at else "",
        }
        for t in tasks_res.scalars().all()
    ]

    approvals_res = await db.execute(
        select(ApprovalRequest).order_by(desc(ApprovalRequest.created_at)).limit(20)
    )
    approvals = [
        {
            "id": ap.id,
            "request_type": ap.request_type,
            "requested_by_agent": ap.requested_by_agent,
            "title": ap.title,
            "rationale": ap.rationale,
            "payload_json": ap.payload_json,
            "estimated_cost_usd": ap.estimated_cost_usd,
            "projected_roi_usd": ap.projected_roi_usd,
            "status": ap.status,
            "created_at": ap.created_at.isoformat() if ap.created_at else "",
        }
        for ap in approvals_res.scalars().all()
    ]

    projects_res = await db.execute(
        select(SoftwareProject).order_by(desc(SoftwareProject.created_at)).limit(20)
    )
    projects = [
        {
            "id": p.id,
            "name": p.name,
            "project_type": p.project_type,
            "client_name": p.client_name,
            "specification": p.specification,
            "status": p.status,
            "sandbox_exit_code": p.sandbox_exit_code,
            "healing_iterations": p.healing_iterations,
            "healing_log": p.healing_log or [],
            "git_commit_hash": p.git_commit_hash,
            "test_report": p.test_report,
            "files_manifest": p.files_manifest,
            "preview_url": p.preview_url,
            "external_deploy_url": p.external_deploy_url,
            "download_zip_url": f"/api/factory/projects/{p.id}/download.zip",
            "contract_value_usd": p.contract_value_usd,
            "build_cost_usd": round(p.build_cost_usd or 0.0, 5),
            "created_at": p.created_at.isoformat() if p.created_at else "",
        }
        for p in projects_res.scalars().all()
    ]

    omni_res = await db.execute(
        select(OmnichannelInteraction).order_by(desc(OmnichannelInteraction.created_at)).limit(20)
    )
    interactions = [
        {
            "id": o.id,
            "channel": o.channel,
            "department": o.department,
            "contact_name": o.contact_name,
            "contact_handle": o.contact_handle,
            "inbound_message": o.inbound_message,
            "agent_response": o.agent_response,
            "deal_stage": o.deal_stage,
            "deal_value_usd": o.deal_value_usd,
            "created_at": o.created_at.isoformat() if o.created_at else "",
        }
        for o in omni_res.scalars().all()
    ]

    inv_res = await db.execute(
        select(PaymentInvoice).order_by(desc(PaymentInvoice.created_at)).limit(20)
    )
    invoices = [
        {
            "id": inv.id,
            "provider": inv.provider,
            "external_id": inv.external_id,
            "client_name": inv.client_name,
            "client_email": inv.client_email,
            "description": inv.description,
            "amount_usd": inv.amount_usd,
            "status": inv.status,
            "checkout_url": inv.checkout_url,
            "pix_copy_paste": inv.pix_copy_paste,
            "pix_qr_svg": inv.pix_qr_svg,
            "created_at": inv.created_at.isoformat() if inv.created_at else "",
        }
        for inv in inv_res.scalars().all()
    ]

    mem_res = await db.execute(
        select(SemanticMemoryChunk).order_by(desc(SemanticMemoryChunk.created_at)).limit(25)
    )
    memories = [
        {
            "id": m.id,
            "namespace": m.namespace,
            "source_agent": m.source_agent,
            "title": m.title,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else "",
        }
        for m in mem_res.scalars().all()
    ]

    jobs_res = await db.execute(select(ScheduledJob).order_by(ScheduledJob.created_at.asc()))
    scheduled_jobs = [
        {
            "id": j.id,
            "name": j.name,
            "department": j.department,
            "directive_template": j.directive_template,
            "interval_seconds": j.interval_seconds,
            "is_enabled": j.is_enabled,
            "runs_count": j.runs_count,
            "last_run_at": j.last_run_at.isoformat() if j.last_run_at else None,
            "last_result": j.last_result,
        }
        for j in jobs_res.scalars().all()
    ]

    camp_res = await db.execute(
        select(GrowthCampaign).order_by(desc(GrowthCampaign.created_at)).limit(20)
    )
    growth_campaigns = [
        {
            "id": c.id,
            "title": c.title,
            "channel": c.channel,
            "target_audience": c.target_audience,
            "hook_headline": c.hook_headline,
            "content_body": c.content_body,
            "cta_url": c.cta_url,
            "impressions": c.impressions,
            "clicks": c.clicks,
            "leads_captured": c.leads_captured,
            "ad_spend_usd": c.ad_spend_usd,
            "attributed_revenue_usd": c.attributed_revenue_usd,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else "",
        }
        for c in camp_res.scalars().all()
    ]

    sec_res = await db.execute(
        select(SecurityAuditLog).order_by(desc(SecurityAuditLog.created_at)).limit(15)
    )
    security_logs = [
        {
            "id": s.id,
            "action": s.action,
            "actor": s.actor,
            "details": s.details,
            "created_at": s.created_at.isoformat() if s.created_at else "",
        }
        for s in sec_res.scalars().all()
    ]

    ven_res = await db.execute(
        select(BusinessVenture).order_by(desc(BusinessVenture.created_at))
    )
    ventures = [
        {
            "id": v.id,
            "codename": v.codename,
            "name": v.name,
            "niche": v.niche,
            "tagline": v.tagline,
            "monthly_price_usd": v.monthly_price_usd,
            "active_customers": v.active_customers,
            "mrr_usd": v.mrr_usd,
            "total_revenue_usd": v.total_revenue_usd,
            "software_project_id": v.software_project_id,
            "dedicated_agent_id": v.dedicated_agent_id,
            "public_url": v.public_url,
            "status": v.status,
            "created_at": v.created_at.isoformat() if v.created_at else "",
        }
        for v in ven_res.scalars().all()
    ]
    holding_mrr_usd = round(sum(v["mrr_usd"] for v in ventures), 2)

    whatsapp_instance = await EvolutionWhatsAppManager.get_status(db)
    vault_status = await ConfigVault.list_status(db)

    return {
        "balance": balance,
        "holding_mrr_usd": holding_mrr_usd,
        "ventures": ventures,
        "agents": agents,
        "ledger": ledger,
        "tasks": tasks,
        "approvals": approvals,
        "projects": projects,
        "interactions": interactions,
        "invoices": invoices,
        "memories": memories,
        "scheduler": AutonomousSchedulerDaemon.get_state(),
        "scheduled_jobs": scheduled_jobs,
        "growth_campaigns": growth_campaigns,
        "security": SovereignSecurityGuard.get_security_overview(),
        "security_logs": security_logs,
        "whatsapp_instance": whatsapp_instance,
        "vault_status": vault_status,
        "telemetry": event_bus.recent_events(80),
    }


# ============================================================================
# PORTFÓLIO DE EMPRESAS & VENTURE BUILDER AUTÓNOMO (SAAS + CHECKOUT LIVE)
# ============================================================================
@app.post("/api/ventures/launch")
async def launch_new_venture(
    payload: LaunchVentureRequest,
    db: AsyncSession = Depends(get_db),
):
    if SovereignSecurityGuard._kill_switch_active:
        raise HTTPException(status_code=403, detail="Global Kill-Switch ativo.")
    ven = await AutonomousVentureBuilder.launch_full_venture(
        db=db,
        name=payload.name,
        niche=payload.niche,
        tagline=payload.tagline,
        monthly_price_usd=payload.monthly_price_usd,
        initial_customers=payload.initial_customers,
    )
    return {"ok": True, "venture_id": ven.id, "public_url": ven.public_url}


@app.post("/api/ventures/{venture_id}/checkout")
async def venture_self_serve_checkout(
    venture_id: str,
    payload: VentureCheckoutRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        out = await AutonomousVentureBuilder.process_self_serve_checkout(
            db=db,
            venture_id=venture_id,
            customer_name=payload.customer_name,
            customer_email=payload.customer_email,
            customer_phone=payload.customer_phone,
            provider=payload.provider,
        )
        return out
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/command/execute")
async def execute_direct_command(payload: CommandDirectiveRequest):
    state = await execute_empire_directive(
        directive=payload.directive,
        title=payload.title,
        forced_department=payload.department,
        priority=payload.priority,
    )
    return {"ok": True, "execution": state}


# ============================================================================
# SCHEDULER AUTÓNOMO 24/7 (PILOTO AUTOMÁTICO & CRON PIPELINES)
# ============================================================================
@app.post("/api/scheduler/autopilot")
async def toggle_autopilot(payload: AutopilotToggleRequest):
    try:
        state = await AutonomousSchedulerDaemon.set_autopilot(payload.enabled)
        return {"ok": True, "scheduler": state}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/scheduler/jobs")
async def create_scheduled_job(
    payload: CreateScheduledJobRequest,
    db: AsyncSession = Depends(get_db),
):
    job = ScheduledJob(
        id=f"cron-{uuid.uuid4().hex[:8]}",
        name=payload.name,
        department=payload.department,
        directive_template=payload.directive_template,
        interval_seconds=payload.interval_seconds,
        is_enabled=True,
    )
    db.add(job)
    await db.commit()
    await event_bus.publish(
        event_type="CRON_JOB_CREATED",
        agent_slug="master-orchestrator",
        level="SUCCESS",
        message=f"Novo pipeline 24/7 agendado: '{job.name}' a cada {job.interval_seconds}s.",
    )
    return {"ok": True, "job_id": job.id}


@app.post("/api/scheduler/jobs/{job_id}/run")
async def trigger_job_immediately(job_id: str):
    try:
        out = await AutonomousSchedulerDaemon.run_single_job(job_id)
        return {"ok": True, **out}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.patch("/api/scheduler/jobs/{job_id}/toggle")
async def toggle_scheduled_job(
    job_id: str,
    payload: ToggleJobRequest,
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(ScheduledJob).where(ScheduledJob.id == job_id))
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    job.is_enabled = payload.is_enabled
    await db.commit()
    return {"ok": True, "id": job.id, "is_enabled": job.is_enabled}


# ============================================================================
# AGENTE DE TRÁFEGO, CONTEÚDO SOCIAL & SEO PROGRAMÁTICO
# ============================================================================
@app.post("/api/growth/campaigns")
async def launch_growth_campaign_endpoint(
    payload: LaunchGrowthCampaignRequest,
    db: AsyncSession = Depends(get_db),
):
    if SovereignSecurityGuard._kill_switch_active:
        raise HTTPException(status_code=403, detail="Global Kill-Switch ativo.")
    camp = await GrowthSocialAgent.launch_campaign(
        db=db,
        task_id=None,
        directive=payload.directive,
        explicit_channel=payload.channel,
        custom_title=payload.title,
    )
    return {"ok": True, "campaign_id": camp.id}


# ============================================================================
# SEGURANÇA SOBERANA CEO (JWT HS256 + TOTP 2FA RFC 6238 + GLOBAL KILL-SWITCH)
# ============================================================================
@app.post("/api/security/login")
async def ceo_sovereign_login(
    payload: SecurityLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip_hint = request.client.host if request.client else "127.0.0.1"
    try:
        auth = await SovereignSecurityGuard.authenticate_ceo(
            db=db,
            password=payload.password,
            totp_code=payload.totp_code,
            ip_hint=ip_hint,
        )
        return {"ok": True, **auth}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@app.post("/api/security/kill-switch")
async def toggle_emergency_kill_switch(
    payload: KillSwitchRequest,
    db: AsyncSession = Depends(get_db),
):
    if payload.engage:
        await AutonomousSchedulerDaemon.set_autopilot(False)
    out = await SovereignSecurityGuard.toggle_kill_switch(db=db, engage=payload.engage)
    return {"ok": True, **out}


# ============================================================================
# FÁBRICA DE SOFTWARE NÍVEL 2, PAGAMENTOS, WHATSAPP, MEMÓRIA & GOVERNANÇA
# ============================================================================
@app.post("/api/factory/build")
async def trigger_software_factory_build(
    payload: FactoryBuildRequest,
    db: AsyncSession = Depends(get_db),
):
    if SovereignSecurityGuard._kill_switch_active:
        raise HTTPException(status_code=403, detail="Global Kill-Switch ativo.")
    project = await SoftwareFactoryAgent.build_software_project(
        db=db,
        task_id=None,
        name=payload.name,
        specification=payload.specification,
        project_type=payload.project_type,
        client_name=payload.client_name,
        contract_value_usd=payload.contract_value_usd,
        simulate_fault_healing=payload.simulate_fault_healing,
    )
    return {
        "ok": True,
        "project": {
            "id": project.id,
            "name": project.name,
            "project_type": project.project_type,
            "status": project.status,
            "preview_url": project.preview_url,
            "git_commit_hash": project.git_commit_hash,
            "healing_iterations": project.healing_iterations,
            "healing_log": project.healing_log,
            "download_zip_url": f"/api/factory/projects/{project.id}/download.zip",
            "sandbox_exit_code": project.sandbox_exit_code,
            "test_report": project.test_report,
        },
    }


@app.get("/api/factory/projects/{project_id}/source")
async def inspect_project_source(project_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(SoftwareProject).where(SoftwareProject.id == project_id))
    proj = res.scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")

    proj_dir = DEPLOYMENTS_ROOT / project_id
    sources: dict[str, str] = {}
    if proj_dir.exists():
        for fname in proj.files_manifest:
            fpath = proj_dir / fname
            if fpath.exists() and fpath.is_file():
                sources[fname] = fpath.read_text(encoding="utf-8", errors="replace")

    return {
        "project_id": proj.id,
        "name": proj.name,
        "git_commit_hash": proj.git_commit_hash,
        "healing_iterations": proj.healing_iterations,
        "healing_log": proj.healing_log or [],
        "test_report": proj.test_report,
        "sources": sources,
    }


@app.get("/api/factory/projects/{project_id}/download.zip")
async def download_project_zip(project_id: str):
    zip_path = DEPLOYMENTS_ROOT / f"{project_id}.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="Pacote ZIP não encontrado.")
    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=f"{project_id}-autonomous-build.zip",
    )


@app.post("/api/factory/projects/{project_id}/deploy-cloud")
async def deploy_project_cloud(project_id: str, db: AsyncSession = Depends(get_db)):
    try:
        out = await SoftwareFactoryAgent.deploy_to_external_cloud(db, project_id)
        return {"ok": True, **out}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/payments/invoices")
async def create_payment_invoice(
    payload: CreateInvoiceRequest,
    db: AsyncSession = Depends(get_db),
):
    inv = await PaymentGatewayManager.create_invoice(
        db=db,
        provider=payload.provider,
        client_name=payload.client_name,
        client_email=payload.client_email,
        description=payload.description,
        amount_usd=payload.amount_usd,
    )
    return {"ok": True, "invoice_id": inv.id}


@app.post("/api/webhooks/payments/{invoice_id}/settle")
async def settle_payment_webhook(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        inv = await PaymentGatewayManager.reconcile_paid_webhook(db, invoice_id)
        return {"ok": True, "invoice_id": inv.id, "status": inv.status}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/webhooks/asaas")
async def asaas_production_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        body = await request.json()
    except Exception:
        body = {}
    result = await PaymentGatewayManager.handle_asaas_webhook(db, body)
    return {"ok": True, **result}


@app.post("/api/whatsapp/qr/refresh")
async def whatsapp_refresh_qr(db: AsyncSession = Depends(get_db)):
    state = await EvolutionWhatsAppManager.refresh_qr_code(db)
    return {"ok": True, "whatsapp_instance": state}


@app.post("/api/whatsapp/pair")
async def whatsapp_confirm_pair(payload: PairWhatsAppRequest):
    try:
        state = await EvolutionWhatsAppManager.confirm_pairing(payload.phone_number)
        return {"ok": True, "whatsapp_instance": state}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/whatsapp/pair-code")
async def whatsapp_request_pair_code(payload: PairWhatsAppRequest):
    try:
        state = await EvolutionWhatsAppManager.request_real_pairing_code(payload.phone_number)
        return {"ok": True, "whatsapp_instance": state}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/whatsapp/disconnect")
async def whatsapp_disconnect():
    state = await EvolutionWhatsAppManager.disconnect_instance()
    return {"ok": True, "whatsapp_instance": state}


@app.post("/api/webhooks/evolution")
async def evolution_whatsapp_webhook(
    payload: EvolutionWebhookPayload,
    db: AsyncSession = Depends(get_db),
):
    contact_name = payload.contact_name
    contact_handle = payload.contact_handle
    message_text = payload.message

    if payload.data and isinstance(payload.data, dict):
        push_name = payload.data.get("pushName")
        key_obj = payload.data.get("key", {})
        msg_obj = payload.data.get("message", {})
        if push_name:
            contact_name = push_name
        if isinstance(key_obj, dict) and key_obj.get("remoteJid"):
            contact_handle = str(key_obj["remoteJid"]).split("@")[0]
        if isinstance(msg_obj, dict) and msg_obj.get("conversation"):
            message_text = str(msg_obj["conversation"])

    result = await Support24hAgent.handle_inbound_ticket(
        db=db,
        task_id=None,
        channel="WHATSAPP_EVOLUTION",
        contact_name=contact_name,
        contact_handle=contact_handle,
        message=message_text,
    )
    return {"ok": True, "ticket": result}


@app.get("/api/memory/search")
async def search_semantic_memory(
    q: str = Query(..., min_length=2),
    namespace: str = Query("ALL"),
    db: AsyncSession = Depends(get_db),
):
    results = await EmpireSemanticMemory.search_similar(db=db, query=q, namespace=namespace, top_k=8)
    return {"ok": True, "results": results}


@app.post("/api/memory/store")
async def store_semantic_memory(
    payload: StoreMemoryRequest,
    db: AsyncSession = Depends(get_db),
):
    chunk = await EmpireSemanticMemory.store_memory(
        db=db,
        namespace=payload.namespace,
        source_agent="ceo-command",
        title=payload.title,
        content=payload.content,
    )
    return {"ok": True, "memory_id": chunk.id}


@app.post("/api/vault/secret")
async def update_vault_secret(
    payload: VaultSecretUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        await ConfigVault.set_secret(db, payload.key_name, payload.value)
        await event_bus.publish(
            event_type="VAULT_SECRET_UPDATED",
            agent_slug="master-orchestrator",
            level="SUCCESS",
            message=f"Credencial '{payload.key_name}' atualizada em quente no Cofre de Integrações.",
        )
        return {"ok": True, "vault_status": await ConfigVault.list_status(db)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/approvals/{approval_id}/decide")
async def decide_approval_endpoint(
    approval_id: str,
    payload: ApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        outcome = await MetaCreatorAgent.decide_approval(
            db=db,
            approval_id=approval_id,
            approve=payload.approve,
        )
        return {"ok": True, **outcome}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.patch("/api/agents/{agent_id}/toggle")
async def update_agent_operational_state(
    agent_id: str,
    payload: AgentConfigPatchRequest,
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(AgentRegistry).where(AgentRegistry.id == agent_id))
    agent = res.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado.")

    if payload.status in ("IDLE", "PAUSED"):
        agent.status = payload.status
    if payload.max_budget_per_task_usd is not None and payload.max_budget_per_task_usd > 0:
        agent.max_budget_per_task_usd = payload.max_budget_per_task_usd

    await db.commit()
    await event_bus.publish(
        event_type="AGENT_GOVERNANCE_UPDATED",
        agent_slug=agent.slug,
        level="INFO",
        message=f"Diretriz operacional atualizada em '{agent.name}': status={agent.status}, teto=${agent.max_budget_per_task_usd:.2f}/task.",
    )
    return {"ok": True, "id": agent.id, "status": agent.status}


class LeadHuntRequest(BaseModel):
    niche: str = Field(..., min_length=2)
    city: str = Field(..., min_length=2)
    venture_id: str | None = None


class SingleAutoSendRequest(BaseModel):
    business_name: str
    phone_digits: str
    message: str
    venture_name: str = "AgendaCorte Pro AI"
    price_usd: float = 19.0


class WaBridgeInboundRequest(BaseModel):
    remote_jid: str = ""
    phone: str
    contact_name: str = "Cliente WhatsApp"
    message: str


@app.post("/api/leads/hunt")
async def hunt_real_b2b_leads(
    payload: LeadHuntRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    base_url = f"{request.url.scheme}://{request.url.netloc}"
    if "127.0.0.1" in base_url or "localhost" in base_url:
        base_url = "https://autonomous-empire-os.onrender.com"
    return await RealLeadHunter.hunt_real_businesses(
        db=db,
        niche=payload.niche,
        city=payload.city,
        venture_id=payload.venture_id,
        public_base_url=base_url,
    )


@app.post("/api/leads/auto-outreach")
async def trigger_autonomous_whatsapp_outreach(
    payload: LeadHuntRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    base_url = f"{request.url.scheme}://{request.url.netloc}"
    if "127.0.0.1" in base_url or "localhost" in base_url:
        base_url = "https://autonomous-empire-os.onrender.com"
    return await AutonomousOutreachEngine.start_autonomous_batch(
        db=db,
        niche=payload.niche,
        city=payload.city,
        venture_id=payload.venture_id,
        public_base_url=base_url,
    )


@app.post("/api/leads/send-one")
async def send_single_lead_autonomous(
    payload: SingleAutoSendRequest,
    db: AsyncSession = Depends(get_db),
):
    return await AutonomousOutreachEngine.send_single_lead_now(
        db=db,
        business_name=payload.business_name,
        phone_digits=payload.phone_digits,
        message=payload.message,
        venture_name=payload.venture_name,
        price_usd=payload.price_usd,
    )


@app.get("/api/leads/campaign-status")
async def get_auto_campaign_status():
    return {"ok": True, "stats": AutonomousOutreachEngine.get_campaign_status()}


@app.post("/api/webhooks/wa-bridge-inbound")
async def handle_wa_bridge_inbound(
    payload: WaBridgeInboundRequest,
    db: AsyncSession = Depends(get_db),
):
    reply = await AutonomousOutreachEngine.handle_real_whatsapp_reply(
        db=db,
        phone=payload.phone,
        contact_name=payload.contact_name,
        message=payload.message,
    )
    return {"ok": True, "auto_reply": reply}


@app.post("/api/system/reset-real-mode")
async def reset_to_strict_real_treasury_mode(db: AsyncSession = Depends(get_db)):
    # 1. Desliga Piloto Automático simulado
    await AutonomousSchedulerDaemon.set_autopilot(False)

    # 2. Remove faturas fictícias de demonstração (qualquer external_id simulado ext_...)
    all_inv_res = await db.execute(select(PaymentInvoice))
    for inv in all_inv_res.scalars().all():
        if (inv.external_id or "").startswith("ext_") or inv.client_name in (
            "Construtora Horizonte S.A.",
            "Nordic Cloud Ventures",
        ):
            await db.delete(inv)
    await db.flush()

    # 3. Mantém no Ledger APENAS pagamentos reais liquidados via Gateway (Asaas/Stripe)
    paid_res = await db.execute(select(PaymentInvoice).where(PaymentInvoice.status == "PAID"))
    paid_invoices = paid_res.scalars().all()
    paid_ids = {inv.id for inv in paid_invoices}

    led_res = await db.execute(select(FinancialLedger))
    for entry in led_res.scalars().all():
        meta = entry.metadata_json or {}
        if entry.category in ("GATEWAY_ASAAS_PIX", "GATEWAY_STRIPE") and meta.get("invoice_id") in paid_ids:
            continue
        await db.delete(entry)

    # 4. Zera custos fictícios acumulados nos agentes
    ag_res = await db.execute(select(AgentRegistry))
    for ag in ag_res.scalars().all():
        ag.total_cost_usd = 0.0

    # 5. Zera métricas fictícias em campanhas
    cmp_res = await db.execute(select(GrowthCampaign))
    for c in cmp_res.scalars().all():
        c.impressions = 0
        c.clicks = 0
        c.leads_captured = 0
        c.ad_spend_usd = 0.0
        c.attributed_revenue_usd = 0.0

    # 6. Recalcula MRR e Clientes de cada Empresa SaaS APENAS com faturas PAID reais
    ven_res = await db.execute(select(BusinessVenture))
    for ven in ven_res.scalars().all():
        matching_paid = [
            inv for inv in paid_invoices if ven.name.lower() in (inv.description or "").lower()
        ]
        ven.active_customers = len(matching_paid)
        ven.mrr_usd = round(sum(inv.amount_usd for inv in matching_paid), 2)
        ven.total_revenue_usd = ven.mrr_usd

    await db.commit()

    await event_bus.publish(
        event_type="REAL_TREASURY_MODE_ACTIVE",
        agent_slug="finance-cfo",
        level="SUCCESS",
        message="MODO CAIXA 100% REAL ATIVADO! Todas as simulações foram zeradas: o saldo reflete exclusivamente Pix/Stripe reais liquidados.",
    )
    return {"ok": True, "paid_real_invoices": len(paid_invoices)}


@app.websocket("/ws/telemetry")
async def websocket_telemetry(ws: WebSocket):
    await ws.accept()
    queue = event_bus.subscribe()
    try:
        await ws.send_json({"type": "SNAPSHOT", "events": event_bus.recent_events(60)})
        while True:
            try:
                evt = await asyncio.wait_for(queue.get(), timeout=20.0)
                await ws.send_json({"type": "EVENT", "event": evt})
            except asyncio.TimeoutError:
                await ws.send_json({"type": "HEARTBEAT"})
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.unsubscribe(queue)


FRONTEND_DIST = MONOREPO_ROOT / "apps" / "command-center" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="frontend_assets")

    @app.get("/manifest.webmanifest")
    async def serve_pwa_manifest():
        return FileResponse(str(FRONTEND_DIST / "manifest.webmanifest"), media_type="application/manifest+json")

    @app.get("/sw.js")
    async def serve_pwa_sw():
        return FileResponse(str(FRONTEND_DIST / "sw.js"), media_type="application/javascript")

    @app.get("/icon-192.png")
    async def serve_pwa_icon_192():
        return FileResponse(str(FRONTEND_DIST / "icon-192.png"), media_type="image/png")

    @app.get("/icon-512.png")
    async def serve_pwa_icon_512():
        return FileResponse(str(FRONTEND_DIST / "icon-512.png"), media_type="image/png")

    @app.get("/.well-known/assetlinks.json")
    async def serve_android_assetlinks():
        al_path = FRONTEND_DIST / ".well-known" / "assetlinks.json"
        if al_path.exists():
            return FileResponse(str(al_path), media_type="application/json")
        return [
            {
                "relation": ["delegate_permission/common.handle_all_urls"],
                "target": {
                    "namespace": "android_app",
                    "package_name": "com.autonomousempire.os",
                    "sha256_cert_fingerprints": [
                        "61:0C:6A:7E:94:72:7E:4B:26:B3:EA:EB:C8:CD:43:22:A4:83:35:2A:A2:46:32:81:6C:1E:AF:0E:21:7D:E6:07"
                    ],
                },
            }
        ]

    @app.get("/")
    async def serve_spa_root():
        return FileResponse(str(FRONTEND_DIST / "index.html"))

