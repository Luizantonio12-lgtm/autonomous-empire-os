import asyncio
import time
from collections import deque
import json
import os
import sys
import tempfile
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
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
from packages.payments.gateways import PaymentGatewayUnavailable  # noqa: E402
from packages.sandbox_runner import DEPLOYMENTS_ROOT  # noqa: E402
from packages.scheduler import AutonomousSchedulerDaemon  # noqa: E402
from packages.security import SovereignSecurityGuard  # noqa: E402
from packages.security.session_controls import COOKIE_NAME, same_origin, secure_credentials_configured, valid_internal_secret, valid_session  # noqa: E402
from packages.ventures import AutonomousVentureBuilder  # noqa: E402


async def _boot_seed_and_daemons():
    try:
        await run_seed()
    except Exception as exc:
        print(f"[EMPIRE BOOT] Seed warning: {exc}")
    AutonomousSchedulerDaemon.start_background_worker()
    AutonomousOutreachEngine.start_autopilot_daemon()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_database()
    await event_bus.connect_redis_if_available()
    boot_task = asyncio.create_task(_boot_seed_and_daemons())
    yield
    boot_task.cancel()
    await AutonomousOutreachEngine.stop_autopilot_daemon()
    await AutonomousSchedulerDaemon.stop_background_worker()


app = FastAPI(
    title="Autonomous Business Empire v3.0 — API Gateway",
    version="3.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

@app.middleware("http")
async def restrict_sensitive_api(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api/"):
        return await call_next(request)
    if path in ("/api/health", "/api/security/login", "/api/webhooks/asaas"):
        if path == "/api/security/login" and request.method != "GET":
            if not same_origin(request.headers.get("origin"), request.headers.get("host")):
                return JSONResponse(status_code=403, content={"detail": "Origem não autorizada."})
        return await call_next(request)
    if path in ("/api/internal/wa-auth-backup", "/api/internal/wa-auth-restore", "/api/internal/wa-delivery-status", "/api/webhooks/wa-bridge-inbound"):
        if not valid_internal_secret(request.headers.get("x-wa-internal-secret")):
            return JSONResponse(status_code=403, content={"detail": "Acesso interno negado."})
        return await call_next(request)
    if not valid_session(request.cookies.get(COOKIE_NAME)):
        return JSONResponse(status_code=401, content={"detail": "Autenticação necessária."})
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if not same_origin(request.headers.get("origin"), request.headers.get("host")):
            return JSONResponse(status_code=403, content={"detail": "Origem não autorizada."})
    return await call_next(request)


@app.exception_handler(PaymentGatewayUnavailable)
async def payment_unavailable_handler(request: Request, exc: PaymentGatewayUnavailable):
    return JSONResponse(status_code=503, content={"ok": False, "detail": "Pagamento indisponível. Tente novamente mais tarde."})


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
    initial_customers: int = Field(default=0, ge=0)


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
    export_zip = Path(tempfile.gettempdir()) / "autonomous-empire-production-ready.zip"
    skip_dirs = {".git", "node_modules", "__pycache__", ".wa_auth", ".venv", ".mypy_cache", ".pytest_cache"}
    if not export_zip.exists():
        with zipfile.ZipFile(export_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for root_dir, dirnames, filenames in os.walk(MONOREPO_ROOT):
                dirnames[:] = [d for d in dirnames if d not in skip_dirs]
                for fname in filenames:
                    if fname.endswith((".db", ".db-wal", ".db-shm", ".pyc")):
                        continue
                    full_p = Path(root_dir) / fname
                    rel_p = full_p.relative_to(MONOREPO_ROOT)
                    zf.write(full_p, f"autonomous-empire/{rel_p}")
    return FileResponse(
        path=str(export_zip),
        media_type="application/zip",
        filename="autonomous-empire-production-ready.zip",
    )


@app.post("/api/internal/wa-auth-backup")
async def internal_wa_auth_backup(request: Request, db: AsyncSession = Depends(get_db)):
    if request.client and request.client.host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="Loopback only.")
    from packages.database.models import RuntimeVault

    body = await request.json()
    files = body.get("files") or {}
    res = await db.execute(select(RuntimeVault).where(RuntimeVault.key_name == "__INTERNAL_WA_AUTH_BUNDLE__"))
    row = res.scalar_one_or_none()
    if not files:
        if row:
            await db.delete(row)
            await db.commit()
        return {"ok": True, "cleared": True}
    serialized = json.dumps(files, ensure_ascii=False)
    if row:
        row.secret_value = serialized
    else:
        db.add(RuntimeVault(key_name="__INTERNAL_WA_AUTH_BUNDLE__", secret_value=serialized))
    await db.commit()
    return {"ok": True, "files_saved": len(files)}


@app.get("/api/internal/wa-auth-restore")
async def internal_wa_auth_restore(request: Request, db: AsyncSession = Depends(get_db)):
    if request.client and request.client.host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="Loopback only.")
    from packages.database.models import RuntimeVault

    known_res = await db.execute(
        select(OmnichannelInteraction.contact_handle)
        .where(OmnichannelInteraction.channel == "WHATSAPP_REAL_AUTO")
        .limit(400)
    )
    known_contacts = list({"".join(c for c in (h or "") if c.isdigit()) for h in known_res.scalars().all() if h})

    res = await db.execute(select(RuntimeVault).where(RuntimeVault.key_name == "__INTERNAL_WA_AUTH_BUNDLE__"))
    row = res.scalar_one_or_none()
    if not row or not row.secret_value:
        return {"ok": False, "files": {}, "known_contacts": known_contacts}
    try:
        return {"ok": True, "files": json.loads(row.secret_value), "known_contacts": known_contacts}
    except Exception:
        return {"ok": False, "files": {}, "known_contacts": known_contacts}


@app.get("/vitrine")
async def serve_live_3s_vitrine():
    vitrine_path = GATEWAY_DIR / "vitrine_3s.html"
    if vitrine_path.exists():
        return FileResponse(str(vitrine_path), media_type="text/html")
    raise HTTPException(status_code=404, detail="Vitrine não encontrada.")


@app.get("/meu-robo/{invoice_id}")
async def serve_client_self_service_portal(invoice_id: str):
    portal_path = GATEWAY_DIR / "client_portal.html"
    if portal_path.exists():
        return FileResponse(str(portal_path), media_type="text/html")
    raise HTTPException(status_code=404, detail="Portal não encontrado.")


@app.get("/trickspace")
async def serve_trickspace_gamer_store():
    store_path = GATEWAY_DIR / "trickspace_store.html"
    if store_path.exists():
        return FileResponse(str(store_path), media_type="text/html")
    raise HTTPException(status_code=404, detail="Loja TrickSpace não encontrada.")


@app.get("/demo")
async def serve_personalized_client_demo():
    demo_path = GATEWAY_DIR / "personalized_demo.html"
    if demo_path.exists():
        return FileResponse(str(demo_path), media_type="text/html")
    raise HTTPException(status_code=404, detail="Demo não encontrada.")


@app.get("/criativos")
async def serve_viral_creatives_studio():
    cr_path = GATEWAY_DIR / "viral_creatives.html"
    if cr_path.exists():
        return FileResponse(str(cr_path), media_type="text/html")
    raise HTTPException(status_code=404, detail="Estúdio de criativos não encontrado.")


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
        "outreach_autopilot": AutonomousOutreachEngine.get_campaign_status(),
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
        AutonomousOutreachEngine.set_autopilot(payload.enabled)
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
# Limite global por processo: mitigação complementar, não substitui WAF ou
# rate limiting distribuído em ambientes com várias instâncias.
_LOGIN_ATTEMPTS: deque[float] = deque()


@app.post("/api/security/login")
async def ceo_sovereign_login(
    payload: SecurityLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    if not secure_credentials_configured():
        raise HTTPException(status_code=503, detail="Credenciais seguras ainda não configuradas.")
    now = time.monotonic()
    while _LOGIN_ATTEMPTS and _LOGIN_ATTEMPTS[0] <= now - 60:
        _LOGIN_ATTEMPTS.popleft()
    if len(_LOGIN_ATTEMPTS) >= 10:
        raise HTTPException(status_code=429, detail="Muitas tentativas. Aguarde um minuto.")
    _LOGIN_ATTEMPTS.append(now)
    ip_hint = request.client.host if request.client else "unknown"
    try:
        auth = await SovereignSecurityGuard.authenticate_ceo(
            db=db,
            password=payload.password,
            totp_code=payload.totp_code,
            ip_hint=ip_hint,
        )
        response.set_cookie(COOKIE_NAME, auth["token"], httponly=True, secure=True, samesite="strict", max_age=14400, path="/")
        return {"ok": True, "role": auth["role"]}
    except ValueError:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")


@app.post("/api/security/logout")
async def ceo_logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="strict")
    return {"ok": True}


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
    # Uma solicitação com ID de fatura não é prova de pagamento.
    # Desabilitado até existir conciliação autenticada com o provedor.
    raise HTTPException(status_code=403, detail="Liquidação manual desabilitada.")


@app.post("/api/webhooks/asaas")
async def asaas_production_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    from packages.payments.asaas_sandbox_inbox import record_event, sandbox_enabled
    from packages.payments.asaas_validation import valid_webhook_token

    if not sandbox_enabled():
        raise HTTPException(status_code=503, detail="Conciliação Asaas indisponível fora do sandbox de testes.")
    token = os.getenv("ASAAS_WEBHOOK_TOKEN", "")
    if not (32 <= len(token) <= 255) or any(c.isspace() for c in token):
        raise HTTPException(status_code=503, detail="Token sandbox não configurado.")
    if not valid_webhook_token(token, request.headers.get("asaas-access-token", "")):
        raise HTTPException(status_code=401, detail="Token inválido.")
    api_key = await ConfigVault.get_secret(db, "ASAAS_API_KEY")
    if token == api_key:
        raise HTTPException(status_code=503, detail="Token do webhook deve ser diferente da chave de API.")
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 65536:
            raise HTTPException(status_code=413, detail="Evento muito grande.")
        chunks.append(chunk)
    try:
        body = json.loads(b"".join(chunks))
        created = await record_event(db, body)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Evento inválido ou conflito de identificação.")
    # Durável, mas NÃO liquidado: ainda exige verificação e revisão manual.
    return {"ok": True, "recorded": created, "settled": False}


@app.get("/api/payments/asaas-inbox")
async def list_asaas_sandbox_events(
    offset: int = Query(default=0, ge=0, le=100000),
    limit: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    from packages.database.models import AsaasWebhookInbox
    from packages.payments.asaas_sandbox_inbox import sandbox_enabled
    if not sandbox_enabled():
        raise HTTPException(status_code=503, detail="Caixa do Sandbox Asaas não está habilitada.")
    rows = (await db.execute(select(AsaasWebhookInbox)
        .order_by(desc(AsaasWebhookInbox.created_at), desc(AsaasWebhookInbox.event_id))
        .offset(offset).limit(limit + 1))).scalars().all()
    return {
        'ok': True,
        'sandbox_only': True,
        'items': [{
            'event_id': row.event_id,
            'event_type': row.event_type,
            'payment_id': row.payment_id,
            'status': row.status,
            'reason': row.verification_reason,
            'invoice_id': row.invoice_id,
            'created_at': row.created_at.isoformat() if row.created_at else '',
            'verified_at': row.verified_at.isoformat() if row.verified_at else None,
        } for row in rows[:limit]],
        'next_offset': offset + limit if len(rows) > limit else None,
    }


@app.post("/api/payments/asaas-inbox/{event_id}/verify")
async def verify_asaas_sandbox_event(event_id: str, db: AsyncSession = Depends(get_db)):
    from packages.payments.asaas_sandbox_inbox import verify_received_event
    try:
        return {"ok": True, **await verify_received_event(db, event_id)}
    except LookupError:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    except ValueError:
        raise HTTPException(status_code=400, detail="Evento inválido.")
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Verificação sandbox indisponível.")


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


@app.post("/api/whatsapp/test-vip-alert")
async def whatsapp_test_vip_alert():
    out = await EvolutionWhatsAppManager.notify_owner_vip(
        "🔔 *[Empire OS • Teste de Alerta VIP CEO]*\n\n"
        "Tudo funcionando 100%! Você receberá avisos automáticos nesta conversa sempre que:\n"
        "1️⃣ Um cliente pedir o Pix na conversa;\n"
        "2️⃣ Um pagamento Pix for confirmado na sua conta Asaas!"
    )
    return out


@app.post("/api/whatsapp/sweep-unanswered")
async def sweep_unanswered_whatsapp_chats():
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post("http://127.0.0.1:3005/sweep", json={})
            return r.json()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


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
    phone_jid: str = ""
    message_id: str = ""
    phone: str
    contact_name: str = "Cliente WhatsApp"
    message: str
    has_audio: bool = False
    has_image: bool = False
    audio_base64: str = ""
    audio_mime: str = "audio/ogg"
    image_base64: str = ""
    image_mime: str = "image/jpeg"


class WaDeliveryStatusRequest(BaseModel):
    phone_jid: str = Field(..., max_length=128)
    message_id: str = Field(..., max_length=128)
    result: str = Field(..., pattern=r'^(SUBMITTED|UNCERTAIN)$')


class VipSetupCheckoutRequest(BaseModel):
    business_name: str
    whatsapp_phone: str
    venture_name: str = "NexusFlow AI"
    plan_type: str = "VIP_197"


class ViralCreativeGenRequest(BaseModel):
    topic: str = "TrickSpace ZeroLag v2.6 Gamer Free Fire (R$ 19,90)"


class ClientOnboardingConfigRequest(BaseModel):
    invoice_id: str = "vip"
    business_name: str
    whatsapp_phone: str
    business_hours: str
    services_and_prices: str
    merchant_pix_key: str = ""
    bot_tone: str = "Simpático, acolhedor e direto"


class TrickSpaceCheckoutRequest(BaseModel):
    player_name: str
    whatsapp_phone: str


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


@app.post("/api/leads/autopilot-toggle")
async def toggle_outreach_autopilot(payload: AutopilotToggleRequest):
    stats = AutonomousOutreachEngine.set_autopilot(payload.enabled)
    return {"ok": True, "stats": stats}


@app.post("/api/leads/recover-pending")
async def trigger_abandoned_pix_recovery(db: AsyncSession = Depends(get_db)):
    return await AutonomousOutreachEngine.run_abandoned_pix_and_ghost_recovery(db)


@app.post("/api/webhooks/wa-bridge-inbound")
async def handle_wa_bridge_inbound(
    payload: WaBridgeInboundRequest,
    db: AsyncSession = Depends(get_db),
):
    from packages.leads.conversation_policy import handle_inbound

    result = await handle_inbound(
        db=db,
        message_id=payload.message_id,
        phone_jid=payload.phone_jid or payload.remote_jid,
        name=payload.contact_name,
        message=payload.message,
        audio=payload.has_audio or bool(payload.audio_base64) or payload.message.startswith('[ÁUDIO_WHATSAPP]') or payload.message.startswith('[Áudio recebido'),
        image=payload.has_image or bool(payload.image_base64) or payload.message == '[FOTO_WHATSAPP]',
        handoff=payload.message.startswith('[CEO_HANDOFF_TRIGGER]'),
    )
    return {"ok": True, "auto_reply": result['reply'], "reason": result['reason']}


@app.post("/api/internal/wa-delivery-status")
async def wa_delivery_status(payload: WaDeliveryStatusRequest, db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timezone
    from sqlalchemy import update
    from packages.database.models import WhatsAppReplyDelivery
    from packages.leads.conversation_policy import message_hash_for

    key = message_hash_for(payload.phone_jid, payload.message_id)
    if not key:
        raise HTTPException(status_code=400, detail="Identificador inválido.")
    result = await db.execute(update(WhatsAppReplyDelivery).where(
        WhatsAppReplyDelivery.message_hash == key,
        WhatsAppReplyDelivery.status == 'PREPARED',
    ).values(status=payload.result, updated_at=datetime.now(timezone.utc)))
    await db.commit()
    return {"ok": True, "updated": result.rowcount == 1}


@app.get("/api/conversations")
async def list_conversations(
    pending_only: bool = False,
    offset: int = Query(default=0, ge=0, le=100000),
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    from packages.database.models import WhatsAppReplyDelivery
    query = (select(OmnichannelInteraction, WhatsAppReplyDelivery.status)
        .outerjoin(WhatsAppReplyDelivery, WhatsAppReplyDelivery.interaction_id == OmnichannelInteraction.id)
        .where(OmnichannelInteraction.channel == 'WHATSAPP_REAL_AUTO'))
    if pending_only:
        query = query.where(OmnichannelInteraction.deal_stage == 'WAIT_HUMAN_REVIEW')
    rows = (await db.execute(query.order_by(desc(OmnichannelInteraction.created_at), desc(OmnichannelInteraction.id))
                             .offset(offset).limit(limit + 1))).all()
    items = [{
        'id': interaction.id,
        'contact_name': interaction.contact_name,
        'contact_handle': interaction.contact_handle,
        'inbound_message': interaction.inbound_message,
        'agent_response': interaction.agent_response,
        'deal_stage': interaction.deal_stage,
        'delivery_status': status or ('NO_AUTO_REPLY' if interaction.deal_stage in ('WAIT_HUMAN_REVIEW', 'REVIEWED_HUMAN') else 'LEGACY_UNKNOWN'),
        'created_at': interaction.created_at.isoformat() if interaction.created_at else '',
    } for interaction, status in rows[:limit]]
    return {'ok': True, 'items': items, 'next_offset': offset + limit if len(rows) > limit else None}


@app.post("/api/conversations/{interaction_id}/reviewed")
async def mark_conversation_reviewed(interaction_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import update
    result = await db.execute(update(OmnichannelInteraction).where(
        OmnichannelInteraction.id == interaction_id,
        OmnichannelInteraction.channel == 'WHATSAPP_REAL_AUTO',
        OmnichannelInteraction.deal_stage == 'WAIT_HUMAN_REVIEW',
    ).values(deal_stage='REVIEWED_HUMAN'))
    await db.commit()
    if result.rowcount != 1:
        raise HTTPException(status_code=404, detail='Mensagem pendente não encontrada.')
    return {'ok': True, 'sent': False}


@app.post("/api/vip-setup/checkout-pix")
async def create_vip_or_promo_demo_pix(
    payload: VipSetupCheckoutRequest,
    db: AsyncSession = Depends(get_db),
):
    import re
    from packages.integrations.whatsapp_evolution import EvolutionWhatsAppManager

    digits = re.sub(r"\D", "", payload.whatsapp_phone)
    if len(digits) in (10, 11):
        digits = "55" + digits
    is_vip = payload.plan_type.upper() == "VIP_197"
    usd_val = 34.8673 if is_vip else 8.8319
    brl_str = "197,00" if is_vip else "49,90"
    desc = f"Setup VIP Chave na Mao {payload.venture_name}" if is_vip else f"Teste 15 Dias {payload.venture_name}"

    inv = await PaymentGatewayManager.create_invoice(
        db=db,
        provider="ASAAS_PIX",
        client_name=payload.business_name[:75],
        client_email=f"{digits}@whatsapp.com.br",
        description=desc,
        amount_usd=usd_val,
    )
    await EvolutionWhatsAppManager.notify_owner_vip(
        f"👑🔔 *[CLIENTE GEROU PIX R$ {brl_str} NA DEMO PERSONALIZADA!]*\n\n"
        f"🏪 *Empresa:* {payload.business_name} (+{digits})\n"
        f"📦 *Plano:* {desc}\n"
        f"🧾 *Fatura:* {inv.id}"
    )
    return {
        "ok": True,
        "invoice_id": inv.id,
        "brl_amount": brl_str,
        "pix_qr_svg": inv.pix_qr_svg,
        "pix_copy_paste": inv.pix_copy_paste,
    }


@app.post("/api/creatives/generate")
async def generate_viral_video_script(
    payload: ViralCreativeGenRequest,
    db: AsyncSession = Depends(get_db),
):
    from packages.llm_router import MultiModelLLMGateway

    out = await MultiModelLLMGateway.complete(
        db=db,
        agent_id="agent-growth",
        task_id=None,
        system_prompt=(
            "És um especialista brasileiro em vídeos curtos virais de 15 segundos para TikTok, Reels e Kwai que vendem no Pix. "
            "Entrega: [GANCHO 0-3s], [DEMONSTRAÇÃO 3-10s], [CHAMADA PRA AÇÃO 10-15s] e [LEGENDA + 5 HASHTAGS]."
        ),
        user_prompt=f"Cria um roteiro viral inédito de 15 segundos para vender: {payload.topic}",
        operation_label="Estúdio de Criativos Virais",
        strategy="MARGIN_OPTIMIZED",
        local_fallback_text=(
            f"🎬 [0-3s GANCHO]: Olha o que essa ferramenta faz em 3 segundos para {payload.topic}!\n"
            f"📱 [3-10s PROVA]: Mostre a tela funcionando ao vivo sem cortes.\n"
            f"🚀 [10-15s CTA]: Clica no link da Bio agora e testa no seu celular!\n"
            f"#vendas #pix #automacao #viral"
        ),
    )
    return {"ok": True, "script": out.content}


@app.post("/api/onboarding/configure")
async def save_client_bot_onboarding(
    payload: ClientOnboardingConfigRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    import re
    from packages.integrations.whatsapp_evolution import EvolutionWhatsAppManager

    digits = re.sub(r"\D", "", payload.whatsapp_phone)
    if len(digits) in (10, 11):
        digits = "55" + digits
    ref_code = (payload.invoice_id[-6:] if len(payload.invoice_id) >= 6 else uuid.uuid4().hex[:6]).upper()
    base_url = f"{request.url.scheme}://{request.url.netloc}"
    if "127.0.0.1" in base_url or "localhost" in base_url:
        base_url = "https://autonomous-empire-os.onrender.com"
    referral_url = f"{base_url}/vitrine?ref={ref_code}"

    cfg_text = (
        f"Empresa: {payload.business_name} | WhatsApp: {digits} | Horário: {payload.business_hours} | "
        f"Serviços/Preços: {payload.services_and_prices} | Pix Loja: {payload.merchant_pix_key} | "
        f"Tom: {payload.bot_tone} | Código Indicação: {ref_code}"
    )
    await EmpireSemanticMemory.store_memory(
        db=db,
        namespace="CLIENT_BOT_CONFIG",
        source_agent="support-24h",
        title=f"Configuração Self-Service: {payload.business_name}",
        content=cfg_text[:1500],
    )

    await EvolutionWhatsAppManager.notify_owner_vip(
        f"🛠️🚀 *[NOVO CLIENTE CONFIGUROU O ROBÔ SOZINHO!]*\n\n"
        f"🏪 *Empresa:* {payload.business_name}\n"
        f"📱 *WhatsApp:* +{digits}\n"
        f"🕒 *Horários:* {payload.business_hours}\n"
        f"📋 *Serviços/Preços:* {payload.services_and_prices[:300]}\n"
        f"💳 *Chave Pix dele:* {payload.merchant_pix_key or 'Não informada'}\n"
        f"🎁 *Código Indicação dele:* `{ref_code}`"
    )
    return {"ok": True, "ref_code": ref_code, "referral_url": referral_url}


@app.post("/api/trickspace/checkout-pix")
async def create_trickspace_pix_checkout(
    payload: TrickSpaceCheckoutRequest,
    db: AsyncSession = Depends(get_db),
):
    import re
    from packages.integrations.whatsapp_evolution import EvolutionWhatsAppManager

    digits = re.sub(r"\D", "", payload.whatsapp_phone)
    if len(digits) in (10, 11):
        digits = "55" + digits
    # R$ 19,90 -> 19.90 / 5.65 = 3.5221 USD
    inv = await PaymentGatewayManager.create_invoice(
        db=db,
        provider="ASAAS_PIX",
        client_name=payload.player_name[:75],
        client_email=f"{digits}@whatsapp.com.br",
        description="TrickSpace ZeroLag v2.6 Pro Vitalicio",
        amount_usd=3.5221,
    )
    await EvolutionWhatsAppManager.notify_owner_vip(
        f"🎮🔔 *[GAMER GEROU PIX R$ 19,90 • TRICKSPACE PRO!]*\n\n"
        f"🕹️ *Jogador:* {payload.player_name} (+{digits})\n"
        f"🧾 *Fatura:* {inv.id}\n"
        f"⚡ Assim que ele pagar no banco, o sistema envia o APK + Chave VIP no WhatsApp dele sozinho!"
    )
    return {
        "ok": True,
        "invoice_id": inv.id,
        "brl_amount": "19,90",
        "pix_qr_svg": inv.pix_qr_svg,
        "pix_copy_paste": inv.pix_copy_paste,
    }


@app.get("/api/trickspace/status/{invoice_id}")
async def check_trickspace_invoice_status(invoice_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(PaymentInvoice).where(PaymentInvoice.id == invoice_id))
    inv = res.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Fatura não encontrada.")
    is_paid = inv.status == "PAID"
    code_tag = inv.id[-6:].upper()
    return {
        "ok": True,
        "invoice_id": inv.id,
        "paid": is_paid,
        "pro_key": f"TSPRO-{code_tag}-VIP" if is_paid else "",
        "download_url": (
            "https://github.com/Luizantonio12-lgtm/autonomous-empire-os/releases/download/v3.0-downloads/TrickSpace-ZeroLag-v2.6.apk"
            if is_paid
            else ""
        ),
    }


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
    if not same_origin(ws.headers.get("origin"), ws.headers.get("host")) or not valid_session(ws.cookies.get(COOKIE_NAME)):
        await ws.close(code=1008)
        return
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

