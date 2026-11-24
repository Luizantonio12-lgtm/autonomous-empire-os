import asyncio
import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.event_bus import event_bus
from packages.database.models import BusinessVenture, OmnichannelInteraction, PaymentInvoice
from packages.database.session import AsyncSessionLocal
from packages.integrations.whatsapp_evolution import EvolutionWhatsAppManager
from packages.leads.lead_hunter import RealLeadHunter
from packages.llm_router import MultiModelLLMGateway
from packages.payments import PaymentGatewayManager


SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")

BUYING_KEYWORDS = (
    "quero testar",
    "quero assinar",
    "quero ativar",
    "assinar",
    "ativar",
    "fechar",
    "pix",
    "libera",
    "pode liberar",
    "como pago",
    "manda o pix",
    "gera o pix",
    "gera o teste",
)

OBJECTION_KEYWORDS = (
    "caro",
    "desconto",
    "apertado",
    "sem dinheiro",
    "mais barato",
    "valor menor",
    "taxa",
    "49",
)

VIP_TURNKEY_KEYWORDS = (
    "197",
    "chave na mão",
    "chave na mao",
    "entregar pronto",
    "entrega pronto",
    "configurado",
    "vocês configuram",
    "voces configuram",
    "setup vip",
    "pronto hoje",
)

ROTATION_CITIES = (
    "Ribeirão Preto SP",
    "Barretos SP",
    "São José do Rio Preto SP",
    "Franca SP",
    "Guaíra SP",
    "Uberaba MG",
    "Uberlândia MG",
    "Araraquara SP",
    "São Carlos SP",
    "Sertãozinho SP",
    "Catanduva SP",
    "Bebedouro SP",
    "Olímpia SP",
    "Jaboticabal SP",
    "Campinas SP",
    "Bauru SP",
    "Piracicaba SP",
    "Sorocaba SP",
    "Jundiaí SP",
    "Londrina PR",
    "Maringá PR",
    "Goiânia GO",
)

ROTATION_NICHES = (
    "Clínica Odontológica",
    "Imobiliária",
    "Oficina Mecânica",
    "Estética Automotiva",
    "Pizzaria",
    "Academia",
    "Agência de Marketing",
    "Clínica Estética",
    "Hamburgueria",
    "Pet Shop",
    "Barbearia",
    "Salão de Beleza",
    "Restaurante",
)


class AutonomousOutreachEngine:
    """
    Motor 100% Autónomo Zero-Clique de Prospecção & Fechamento 24/7 no WhatsApp Real:
      1. Roda em background contínuo sem precisar clicar em nenhum botão;
      2. Rotaciona automaticamente por +170 combinações de Cidades × Nichos lucrativos;
      3. Respeita janela comercial brasileira (08h-20h30 BRT) e limite diário anti-banimento;
      4. Responde clientes 24/7 e emite Pix Asaas (plano cheio ou Ativação Expressa R$ 49,90)!
    """

    # Por segurança, não iniciar envios automaticamente após deploy/reinício.
    _autopilot_enabled: bool = False
    _daemon_task: asyncio.Task | None = None
    _running_campaign: bool = False
    _rotation_index: int = 0
    _daily_date: str = ""
    _daily_sent_count: int = 0
    _total_sent_session: int = 0
    _daily_limit: int = 50
    _next_cycle_epoch: float = 0.0
    _first_connect_batch_done: bool = False

    _last_campaign_stats: dict = {
        "running": False,
        "target_query": "Aguardando 1º ciclo automático...",
        "queued": 0,
        "sent": 0,
        "skipped_no_wa": 0,
        "last_contacted": "",
    }

    @classmethod
    def _build_target_pair(cls, idx: int) -> tuple[str, str]:
        city = ROTATION_CITIES[idx % len(ROTATION_CITIES)]
        niche = ROTATION_NICHES[(idx // len(ROTATION_CITIES)) % len(ROTATION_NICHES)]
        return niche, city

    @classmethod
    def _refresh_daily_counter(cls) -> None:
        today_str = datetime.now(SAO_PAULO_TZ).strftime("%Y-%m-%d")
        if cls._daily_date != today_str:
            cls._daily_date = today_str
            cls._daily_sent_count = 0

    @classmethod
    def get_campaign_status(cls) -> dict:
        cls._refresh_daily_counter()
        next_niche, next_city = cls._build_target_pair(cls._rotation_index)
        rem_sec = max(0, int(cls._next_cycle_epoch - time.time())) if cls._next_cycle_epoch else 0
        return {
            **cls._last_campaign_stats,
            "autopilot_enabled": cls._autopilot_enabled,
            "next_target": f"{next_niche} — {next_city}",
            "sent_today": cls._daily_sent_count,
            "daily_limit": cls._daily_limit,
            "total_sent_session": cls._total_sent_session,
            "next_cycle_in_sec": rem_sec,
        }

    @classmethod
    def set_autopilot(cls, enabled: bool) -> dict:
        cls._autopilot_enabled = bool(enabled)
        if cls._autopilot_enabled:
            cls._next_cycle_epoch = time.time() + 3
        return cls.get_campaign_status()

    @classmethod
    def start_autopilot_daemon(cls) -> None:
        if cls._daemon_task and not cls._daemon_task.done():
            return
        cls._daemon_task = asyncio.create_task(cls._autopilot_loop())

    @classmethod
    async def stop_autopilot_daemon(cls) -> None:
        if cls._daemon_task and not cls._daemon_task.done():
            cls._daemon_task.cancel()
            try:
                await cls._daemon_task
            except asyncio.CancelledError:
                pass

    @classmethod
    async def _autopilot_loop(cls) -> None:
        await asyncio.sleep(8)
        while True:
            try:
                cls._refresh_daily_counter()

                if not cls._autopilot_enabled:
                    await asyncio.sleep(10)
                    continue

                if cls._running_campaign:
                    await asyncio.sleep(10)
                    continue

                async with AsyncSessionLocal() as db:
                    wa_state = await EvolutionWhatsAppManager.get_status(db)

                if wa_state.get("status") != "CONNECTED":
                    cls._first_connect_batch_done = False
                    await asyncio.sleep(15)
                    continue

                if cls._daily_sent_count >= cls._daily_limit:
                    cls._last_campaign_stats["target_query"] = (
                        f"Meta segura diária atingida ({cls._daily_sent_count}/{cls._daily_limit}) — Closer IA ativo 24h"
                    )
                    cls._next_cycle_epoch = time.time() + 1800
                    await asyncio.sleep(1800)
                    continue

                now_br = datetime.now(SAO_PAULO_TZ)
                in_business_hours = 8 <= now_br.hour <= 20
                if in_business_hours:
                    async with AsyncSessionLocal() as db:
                        await cls.run_abandoned_pix_and_ghost_recovery(db)

                if not in_business_hours and cls._first_connect_batch_done:
                    cls._last_campaign_stats["target_query"] = (
                        "Pausa noturna anti-banimento (retoma às 08h00 BRT) — Closer IA ativo 24h"
                    )
                    cls._next_cycle_epoch = time.time() + 900
                    await asyncio.sleep(900)
                    continue

                niche, city = cls._build_target_pair(cls._rotation_index)
                cls._rotation_index += 1

                async with AsyncSessionLocal() as db:
                    res = await cls.start_autonomous_batch(
                        db=db,
                        niche=niche,
                        city=city,
                        max_leads=4,
                    )

                # Aguarda o lote atual terminar
                while cls._running_campaign:
                    await asyncio.sleep(5)

                sent_in_batch = cls._last_campaign_stats.get("sent", 0)
                if sent_in_batch > 0:
                    cls._first_connect_batch_done = True
                    pause_sec = random.randint(480, 720)  # 8 a 12 min entre cidades com entregas
                else:
                    pause_sec = 20  # Se a cidade não teve WhatsApp novo, avança rápido para a próxima!

                cls._next_cycle_epoch = time.time() + pause_sec
                await asyncio.sleep(pause_sec)

            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(25)

    @classmethod
    async def send_single_lead_now(cls, db: AsyncSession, business_name: str, phone_digits: str,
                                   message: str, venture_name: str = "AgendaCorte Pro AI",
                                   price_usd: float = 19.0) -> dict:
        # Até existir consentimento verificável e deduplicação durável, nem o
        # painel nem o piloto enviam abordagens de marketing automaticamente.
        return {"ok": False, "error": "OUTBOUND_DISABLED", "message": "Abordagem automática desativada até revisão de consentimento."}

    @classmethod
    async def start_autonomous_batch(cls, db: AsyncSession, niche: str, city: str,
                                     venture_id: str | None = None,
                                     public_base_url: str = "https://autonomous-empire-os.onrender.com",
                                     max_leads: int = 5) -> dict:
        return {"ok": False, "error": "OUTBOUND_DISABLED", "message": "Campanhas automáticas desativadas até revisão de consentimento."}

    @classmethod
    async def _background_cadence_worker(cls, leads: list[dict]) -> None:
        try:
            for idx, lead in enumerate(leads):
                async with AsyncSessionLocal() as db:
                    wa_state = await EvolutionWhatsAppManager.get_status(db)
                    if wa_state.get("status") != "CONNECTED":
                        break

                    outbound_msg = lead.get("warm_opener") or lead["whatsapp_pitch"]
                    res = await cls.send_single_lead_now(
                        db=db,
                        business_name=lead["business_name"],
                        phone_digits=lead["phone_digits"],
                        message=outbound_msg,
                        venture_name=lead["venture_name"],
                        price_usd=lead["price_usd"],
                    )
                    if res.get("ok"):
                        cls._last_campaign_stats["sent"] += 1
                        cls._last_campaign_stats["last_contacted"] = lead["business_name"]
                    else:
                        cls._last_campaign_stats["skipped_no_wa"] += 1

                if idx < len(leads) - 1:
                    await asyncio.sleep(random.uniform(32.0, 50.0))
        finally:
            cls._running_campaign = False
            cls._last_campaign_stats["running"] = False
            if cls._last_campaign_stats.get("sent", 0) > 0:
                await event_bus.publish(
                    event_type="AUTO_CAMPAIGN_FINISHED",
                    agent_slug="sales-closer",
                    level="SUCCESS",
                    message=(
                        f"Ciclo autónomo concluído ({cls._last_campaign_stats['target_query']}): "
                        f"{cls._last_campaign_stats['sent']} propostas reais entregues no WhatsApp! Próxima cidade na fila automática."
                    ),
                )

    @classmethod
    async def run_abandoned_pix_and_ghost_recovery(cls, db: AsyncSession) -> dict:
        # Follow-up automático desligado para não repetir mensagens ou cobrar
        # alguém sem confirmar consentimento e status do pagamento no provedor.
        return {"ok": False, "recovered": 0, "reason": "FOLLOWUP_DISABLED"}
