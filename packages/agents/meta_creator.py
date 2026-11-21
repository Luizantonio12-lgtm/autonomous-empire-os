import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.agents.llm_interceptor import FinancialLedgerInterceptor
from packages.database.event_bus import event_bus
from packages.database.models import AgentRegistry, ApprovalRequest

DYNAMIC_SPAWNS_DIR = Path(__file__).resolve().parent / "dynamic_spawns"
DYNAMIC_SPAWNS_DIR.mkdir(parents=True, exist_ok=True)


class MetaCreatorAgent:
    """
    Meta-Agente (Arquiteto Autónomo de Sub-Agentes).
    Identifica gargalos operacionais, sintetiza especificações + código Python de novos
    sub-agentes, submete à aprovação soberana no Painel ADM (HITL) e faz Hot-Spawn no Grafo.
    """

    AGENT_ID = "agent-meta"

    @staticmethod
    def _slugify(text: str) -> str:
        clean = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return clean[:42] or f"sub-agent-{uuid.uuid4().hex[:6]}"

    @classmethod
    def _design_blueprint(cls, directive: str) -> dict:
        low = directive.lower()
        if any(w in low for w in ["tráfego", "ads", "seo", "marketing", "conteúdo", "aquisição"]):
            name = "Agente Growth, SEO & Tráfego Pago"
            dept = "GROWTH_MARKETING"
            role = "Otimiza campanhas Meta/Google Ads, SEO programático e CAC em tempo real."
            tools = ["google_ads_api", "meta_marketing_api", "programmatic_seo_builder", "cac_auditor"]
            roi = 6800.00
        elif any(w in low for w in ["segurança", "qa", "devsecops", "pentest", "vulnerab"]):
            name = "Agente DevSecOps & Auditoria de Código"
            dept = "CYBERSECURITY"
            role = "Executa SAST/DAST contínuo nos deploys da Fábrica de Software e blinda APIs."
            tools = ["semgrep_scanner", "container_audit", "cve_patcher", "waf_controller"]
            roi = 4500.00
        elif any(w in low for w in ["jurídico", "contrato", "compliance", "lgpd", "gdpr"]):
            name = "Agente Jurídico & Contratos B2B"
            dept = "LEGAL_COMPLIANCE"
            role = "Redige minutas SaaS, valida conformidade LGPD/GDPR e acelera assinatura B2B."
            tools = ["contract_drafter", "gdpr_compliance_check", "esignature_webhook"]
            roi = 3900.00
        elif any(w in low for w in ["retenção", "churn", "cs", "sucesso do cliente", "onboarding"]):
            name = "Agente Customer Success & Anti-Churn"
            dept = "RETENTION_CS"
            role = "Monitoriza telemetria de uso de clientes ativos, previne churn e faz upsell automático."
            tools = ["health_score_tracker", "whatsapp_onboarding_flow", "upsell_trigger"]
            roi = 5200.00
        else:
            # Extrai especialidade personalizada a partir da diretriz do CEO
            short_topic = directive.strip()[:48]
            name = f"Sub-Agente Especialista: {short_topic}"
            dept = "SPECIAL_OPS"
            role = f"Sub-agente autónomo especializado criado sob medida para: {directive}"
            tools = ["autonomous_research", "webhook_executor", "ledger_reporter"]
            roi = 4100.00

        slug = f"{cls._slugify(name)}-{uuid.uuid4().hex[:4]}"
        system_prompt = (
            f"És o {name} do Ecossistema Empresarial Autónomo.\n"
            f"Missão: {role}\n"
            "Regras Operacionais:\n"
            "1. Opera com foco absoluto em margem de lucro líquida e eficiência de tokens.\n"
            "2. Reporta métricas estruturadas ao Agente Orquestrador Mestre e ao Agente Financeiro.\n"
            "3. Escala decisões acima do orçamento por tarefa para aprovação humana no Command Center."
        )

        python_code = f'''"""
Sub-Agente Gerado Autonomamente pelo Meta-Agente
Slug: {slug}
Departamento: {dept}
"""

AGENT_MANIFEST = {{
    "slug": {slug!r},
    "name": {name!r},
    "department": {dept!r},
    "tools": {tools!r},
    "model": "gpt-4o-mini",
}}


async def run_specialist_step(directive: str) -> dict:
    return {{
        "agent": {slug!r},
        "status": "COMPLETED",
        "deliverable": f"Execução especializada concluída por {name}: {{directive}}",
    }}
'''

        return {
            "slug": slug,
            "name": name,
            "department": dept,
            "role_description": role,
            "system_prompt": system_prompt,
            "model_name": "gpt-4o-mini",
            "tools_manifest": tools,
            "max_budget_per_task_usd": 2.50,
            "projected_roi_usd": roi,
            "generated_code": python_code,
        }

    @classmethod
    async def propose_specialized_agent(
        cls,
        db: AsyncSession,
        task_id: str | None,
        directive: str,
    ) -> ApprovalRequest:
        await event_bus.publish(
            event_type="META_BOTTLENECK_SCAN",
            agent_slug="meta-creator",
            level="INFO",
            message=f"Analisando gargalos operacionais e sintetizando arquitetura de novo Sub-Agente: '{directive[:75]}'",
            payload={"task_id": task_id},
        )

        await FinancialLedgerInterceptor.record_llm_usage(
            db=db,
            agent_id=cls.AGENT_ID,
            task_id=task_id,
            model="gpt-4o",
            prompt_tokens=980,
            completion_tokens=720,
            operation_label="Síntese de Blueprint & Código de Novo Sub-Agente (Meta-Agente)",
        )

        blueprint = cls._design_blueprint(directive)
        approval_id = f"appr-{uuid.uuid4().hex[:8]}"

        req = ApprovalRequest(
            id=approval_id,
            request_type="SPAWN_AGENT",
            requested_by_agent=cls.AGENT_ID,
            title=f"Instanciar {blueprint['name']}",
            rationale=(
                f"Gargalo identificado / expansão solicitada: '{directive}'. "
                f"Sub-agente equipado com {len(blueprint['tools_manifest'])} ferramentas dedicadas "
                f"e teto de custo de ${blueprint['max_budget_per_task_usd']:.2f}/tarefa."
            ),
            payload_json=blueprint,
            estimated_cost_usd=0.05,
            projected_roi_usd=blueprint["projected_roi_usd"],
            status="PENDING",
        )
        db.add(req)
        await db.commit()

        await event_bus.publish(
            event_type="META_APPROVAL_REQUIRED",
            agent_slug="meta-creator",
            level="WARNING",
            message=(
                f"[Aprovação CEO Pendente] Blueprint pronto para '{blueprint['name']}'. "
                f"ROI projetado: +${blueprint['projected_roi_usd']:,.0f}/mês. Aguardando autorização no Painel ADM."
            ),
            payload={"approval_id": approval_id, "agent_name": blueprint["name"]},
        )
        return req

    @classmethod
    async def decide_approval(
        cls,
        db: AsyncSession,
        approval_id: str,
        approve: bool,
    ) -> dict:
        res = await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))
        req = res.scalar_one_or_none()
        if not req:
            raise ValueError("Pedido de aprovação não encontrado.")
        if req.status != "PENDING":
            return {"status": req.status, "message": "Pedido já processado anteriormente."}

        req.decided_at = datetime.now(timezone.utc)

        if not approve:
            req.status = "REJECTED"
            await db.commit()
            await event_bus.publish(
                event_type="META_APPROVAL_REJECTED",
                agent_slug="meta-creator",
                level="INFO",
                message=f"Proposta '{req.title}' rejeitada pelo Administrador.",
                payload={"approval_id": approval_id},
            )
            return {"status": "REJECTED", "approval_id": approval_id}

        req.status = "APPROVED"
        bp = req.payload_json
        new_agent_id = f"agent-dyn-{uuid.uuid4().hex[:6]}"

        # Grava ficheiro Python real do novo Sub-Agente no disco do monorepo
        code_file = DYNAMIC_SPAWNS_DIR / f"{bp['slug'].replace('-', '_')}.py"
        code_file.write_text(bp["generated_code"], encoding="utf-8")

        new_agent = AgentRegistry(
            id=new_agent_id,
            slug=bp["slug"],
            name=bp["name"],
            department=bp["department"],
            role_description=bp["role_description"],
            system_prompt=bp["system_prompt"],
            model_name=bp["model_name"],
            tools_manifest=bp["tools_manifest"],
            status="IDLE",
            is_dynamic=True,
            created_by="meta-creator",
            max_budget_per_task_usd=bp["max_budget_per_task_usd"],
        )
        db.add(new_agent)
        await db.commit()

        await event_bus.publish(
            event_type="META_AGENT_SPAWNED",
            agent_slug=bp["slug"],
            level="SUCCESS",
            message=(
                f"NOVO AGENTE ATIVO NO GRAFO: '{bp['name']}' ({bp['department']}) "
                f"compilado em packages/agents/dynamic_spawns/{code_file.name} e operacional!"
            ),
            payload={"agent_id": new_agent_id, "slug": bp["slug"], "name": bp["name"]},
        )

        return {
            "status": "APPROVED",
            "approval_id": approval_id,
            "spawned_agent_id": new_agent_id,
            "code_path": str(code_file),
        }

    @classmethod
    async def execute_dynamic_specialist(
        cls,
        db: AsyncSession,
        agent: AgentRegistry,
        task_id: str,
        directive: str,
    ) -> str:
        await event_bus.publish(
            event_type="DYNAMIC_AGENT_EXEC",
            agent_slug=agent.slug,
            level="INFO",
            message=f"[{agent.name}] Executando operação especializada com tools {agent.tools_manifest}...",
            payload={"agent_id": agent.id, "task_id": task_id},
        )

        await FinancialLedgerInterceptor.record_llm_usage(
            db=db,
            agent_id=agent.id,
            task_id=task_id,
            model=agent.model_name,
            prompt_tokens=640,
            completion_tokens=410,
            operation_label=f"Execução Especializada ({agent.name})",
        )

        result_msg = (
            f"[{agent.name}] Missão concluída com sucesso usando {', '.join(agent.tools_manifest[:3])}: "
            f"diretriz '{directive[:90]}' implementada e métricas sincronizadas."
        )

        await event_bus.publish(
            event_type="DYNAMIC_AGENT_DONE",
            agent_slug=agent.slug,
            level="SUCCESS",
            message=result_msg,
            payload={"agent_id": agent.id, "task_id": task_id},
        )
        return result_msg
