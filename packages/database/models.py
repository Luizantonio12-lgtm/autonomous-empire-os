from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class AgentRegistry(Base):
    __tablename__ = "agents_registry"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    department: Mapped[str] = mapped_column(String(64), nullable=False)
    role_description: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), default="gpt-4o")
    tools_manifest: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="IDLE")
    is_dynamic: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(64), default="SYSTEM")
    tasks_completed: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[float] = mapped_column(Float, default=100.0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    max_budget_per_task_usd: Mapped[float] = mapped_column(Float, default=5.0)
    last_heartbeat: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class TaskExecution(Base):
    __tablename__ = "tasks_execution"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    directive: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_agent_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("agents_registry.id"), nullable=True
    )
    department: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), default="HIGH")
    status: Mapped[str] = mapped_column(String(32), default="QUEUED")
    state_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_provider_used: Mapped[str] = mapped_column(String(48), default="cascade-router")
    tokens_prompt: Mapped[int] = mapped_column(Integer, default=0)
    tokens_completion: Mapped[int] = mapped_column(Integer, default=0)
    execution_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_generated_usd: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class FinancialLedger(Base):
    __tablename__ = "financial_ledger"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entry_type: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("agents_registry.id"), nullable=True
    )
    task_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("tasks_execution.id"), nullable=True
    )
    amount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_type: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_by_agent: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    projected_roi_usd: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SoftwareProject(Base):
    __tablename__ = "software_projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    project_type: Mapped[str] = mapped_column(String(48), nullable=False)
    client_name: Mapped[str] = mapped_column(String(120), default="Interno / Império")
    specification: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="SPECIFYING")
    sandbox_exit_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    healing_iterations: Mapped[int] = mapped_column(Integer, default=1)
    healing_log: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    git_commit_hash: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    test_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    files_manifest: Mapped[list[str]] = mapped_column(JSON, default=list)
    preview_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    external_deploy_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contract_value_usd: Mapped[float] = mapped_column(Float, default=0.0)
    build_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class OmnichannelInteraction(Base):
    __tablename__ = "omnichannel_interactions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    department: Mapped[str] = mapped_column(String(32), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(120), nullable=False)
    contact_handle: Mapped[str] = mapped_column(String(120), nullable=False)
    inbound_message: Mapped[str] = mapped_column(Text, nullable=False)
    agent_response: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment: Mapped[str] = mapped_column(String(24), default="POSITIVE")
    deal_stage: Mapped[str] = mapped_column(String(32), default="OPEN")
    deal_value_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WhatsAppInboundClaim(Base):
    """Marca durável de processamento at-most-once de mensagem recebida."""
    __tablename__ = "whatsapp_inbound_claims"

    message_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    contact_key: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WhatsAppReplyDelivery(Base):
    """Status local da tentativa, não é comprovante de entrega ou leitura."""
    __tablename__ = "whatsapp_reply_deliveries"

    message_hash: Mapped[str] = mapped_column(String(64), ForeignKey("whatsapp_inbound_claims.message_hash"), primary_key=True)
    interaction_id: Mapped[str] = mapped_column(String(64), ForeignKey("omnichannel_interactions.id"), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PREPARED")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WhatsAppReplyWindow(Base):
    """Limite durável de respostas automáticas por contato."""
    __tablename__ = "whatsapp_reply_windows"

    contact_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_reserved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WhatsAppHandoffWindow(Base):
    """Limite durável para comandos manuais ⚡ por número normalizado."""
    __tablename__ = "whatsapp_handoff_windows"

    contact_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WhatsAppContactPreference(Base):
    """Preferência de não contato. Reativação exige revisão humana."""
    __tablename__ = "whatsapp_contact_preferences"

    contact_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    opted_out_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SemanticMemoryChunk(Base):
    __tablename__ = "semantic_memory"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    namespace: Mapped[str] = mapped_column(String(64), nullable=False)
    source_agent: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_json: Mapped[list[float]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PaymentInvoice(Base):
    __tablename__ = "payment_invoices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # STRIPE | ASAAS_PIX
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    client_name: Mapped[str] = mapped_column(String(140), nullable=False)
    client_email: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="PENDING")
    checkout_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pix_copy_paste: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pix_qr_svg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PixInvoiceExpectation(Base):
    """Montante BRL exato do QR criado pelo provedor (somente novas faturas)."""
    __tablename__ = "pix_invoice_expectations"

    invoice_id: Mapped[str] = mapped_column(String(64), ForeignKey("payment_invoices.id"), primary_key=True)
    amount_brl_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AsaasWebhookInbox(Base):
    """Fila durável de eventos em homologação; não concede acesso nem liquida."""
    __tablename__ = "asaas_webhook_inbox"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(96), nullable=False)
    payment_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING_REVIEW", nullable=False)
    verification_reason: Mapped[Optional[str]] = mapped_column(String(96), nullable=True)
    invoice_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class RuntimeVault(Base):
    __tablename__ = "runtime_vault"

    key_name: Mapped[str] = mapped_column(String(80), primary_key=True)
    secret_value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    department: Mapped[str] = mapped_column(String(64), nullable=False)
    directive_template: Mapped[str] = mapped_column(Text, nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=60)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    runs_count: Mapped[int] = mapped_column(Integer, default=0)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class GrowthCampaign(Base):
    __tablename__ = "growth_campaigns"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    channel: Mapped[str] = mapped_column(String(48), nullable=False)
    target_audience: Mapped[str] = mapped_column(String(160), nullable=False)
    hook_headline: Mapped[str] = mapped_column(String(240), nullable=False)
    content_body: Mapped[str] = mapped_column(Text, nullable=False)
    cta_url: Mapped[str] = mapped_column(String(255), nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    leads_captured: Mapped[int] = mapped_column(Integer, default=0)
    ad_spend_usd: Mapped[float] = mapped_column(Float, default=0.0)
    attributed_revenue_usd: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="PUBLISHED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SecurityAuditLog(Base):
    __tablename__ = "security_audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(80), default="CEO_ADMIN")
    ip_hint: Mapped[str] = mapped_column(String(64), default="0.0.0.0")
    details: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class BusinessVenture(Base):
    __tablename__ = "business_ventures"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    codename: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    niche: Mapped[str] = mapped_column(String(140), nullable=False)
    tagline: Mapped[str] = mapped_column(String(255), nullable=False)
    monthly_price_usd: Mapped[float] = mapped_column(Float, default=197.0)
    active_customers: Mapped[int] = mapped_column(Integer, default=0)
    mrr_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_revenue_usd: Mapped[float] = mapped_column(Float, default=0.0)
    software_project_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("software_projects.id"), nullable=True
    )
    dedicated_agent_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("agents_registry.id"), nullable=True
    )
    public_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="SCALING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
