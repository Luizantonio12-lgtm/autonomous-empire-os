import asyncio
from datetime import datetime, timezone
from sqlalchemy import select

from packages.database.event_bus import event_bus
from packages.database.models import ScheduledJob
from packages.database.session import AsyncSessionLocal
from packages.orchestrator.empire_graph import execute_empire_directive
from packages.security import SovereignSecurityGuard


class AutonomousSchedulerDaemon:
    """
    Motor Autónomo 24/7 (Cron & Heartbeat Loop).
    Quando o Piloto Automático está ATIVO, executa ciclicamente os pipelines
    de Vendas, Conteúdo/Tráfego e Auditoria Financeira sem intervenção humana,
    respeitando rigorosamente o Global Kill-Switch.
    """

    _autopilot_enabled: bool = False
    _total_cycles_executed: int = 0
    _bg_task: asyncio.Task | None = None

    @classmethod
    def get_state(cls) -> dict:
        return {
            "autopilot_enabled": cls._autopilot_enabled,
            "total_cycles_executed": cls._total_cycles_executed,
            "kill_switch_blocked": SovereignSecurityGuard._kill_switch_active,
        }

    @classmethod
    async def set_autopilot(cls, enabled: bool) -> dict:
        if enabled and SovereignSecurityGuard._kill_switch_active:
            raise ValueError("Desativa primeiro o Global Kill-Switch antes de ligar o Piloto Automático.")
        cls._autopilot_enabled = enabled
        await event_bus.publish(
            event_type="AUTOPILOT_STATE_CHANGED",
            agent_slug="master-orchestrator",
            level="SUCCESS" if enabled else "WARNING",
            message=(
                "PILOTO AUTOMÁTICO 24/7 ATIVADO! Os departamentos estão agora operando em ciclos autónomos contínuos."
                if enabled
                else "Piloto Automático 24/7 colocado em espera manual."
            ),
        )
        return cls.get_state()

    @classmethod
    async def run_single_job(cls, job_id: str) -> dict:
        if SovereignSecurityGuard._kill_switch_active:
            raise ValueError("Sistema congelado pelo Global Kill-Switch.")

        async with AsyncSessionLocal() as db:
            res = await db.execute(select(ScheduledJob).where(ScheduledJob.id == job_id))
            job = res.scalar_one_or_none()
            if not job:
                raise ValueError("Cron Job não encontrado.")

            directive = job.directive_template
            dept = job.department
            job_name = job.name

        await event_bus.publish(
            event_type="CRON_JOB_TRIGGERED",
            agent_slug="master-orchestrator",
            level="INFO",
            message=f"[Scheduler 24/7] Executando pipeline recorrente '{job_name}' -> [{dept}]",
            payload={"job_id": job_id},
        )

        exec_out = await execute_empire_directive(
            directive=directive,
            title=f"[Cron 24/7] {job_name}",
            forced_department=dept,
            priority="HIGH",
        )

        async with AsyncSessionLocal() as db:
            res = await db.execute(select(ScheduledJob).where(ScheduledJob.id == job_id))
            job = res.scalar_one_or_none()
            if job:
                job.runs_count = (job.runs_count or 0) + 1
                job.last_run_at = datetime.now(timezone.utc)
                job.last_result = exec_out.get("result_summary", "Ciclo concluído")
                await db.commit()

        cls._total_cycles_executed += 1
        return {"job_id": job_id, "summary": exec_out.get("result_summary")}

    @classmethod
    async def _daemon_loop(cls) -> None:
        while True:
            try:
                await asyncio.sleep(5)
                if not cls._autopilot_enabled or SovereignSecurityGuard._kill_switch_active:
                    continue

                now = datetime.now(timezone.utc)
                due_job_ids: list[str] = []

                async with AsyncSessionLocal() as db:
                    res = await db.execute(
                        select(ScheduledJob).where(ScheduledJob.is_enabled.is_(True))
                    )
                    for job in res.scalars().all():
                        if job.last_run_at is None:
                            due_job_ids.append(job.id)
                        else:
                            last = job.last_run_at
                            if last.tzinfo is None:
                                last = last.replace(tzinfo=timezone.utc)
                            elapsed = (now - last).total_seconds()
                            if elapsed >= max(10, job.interval_seconds):
                                due_job_ids.append(job.id)

                for jid in due_job_ids:
                    if not cls._autopilot_enabled or SovereignSecurityGuard._kill_switch_active:
                        break
                    await cls.run_single_job(jid)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(5)

    @classmethod
    def start_background_worker(cls) -> None:
        if cls._bg_task is None or cls._bg_task.done():
            cls._bg_task = asyncio.create_task(cls._daemon_loop())

    @classmethod
    async def stop_background_worker(cls) -> None:
        if cls._bg_task and not cls._bg_task.done():
            cls._bg_task.cancel()
            try:
                await cls._bg_task
            except asyncio.CancelledError:
                pass
