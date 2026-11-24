import asyncio
import random
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.event_bus import event_bus
from packages.database.models import BusinessVenture, OmnichannelInteraction
from packages.database.session import AsyncSessionLocal
from packages.integrations.whatsapp_evolution import EvolutionWhatsAppManager
from packages.leads.lead_hunter import RealLeadHunter
from packages.llm_router import MultiModelLLMGateway
from packages.payments import PaymentGatewayManager


SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")

BUYING_KEYWORDS = (
    "quero",
    "assinar",
    "ativar",
    "fechar",
    "pix",
    "testar",
    "teste",
    "sim",
    "bora",
    "pode mandar",
    "pode liberar",
    "como pago",
    "manda o link",
    "tenho interesse",
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
    "Barbearia",
    "Pizzaria",
    "Salão de Beleza",
    "Hamburgueria",
    "Pet Shop",
    "Clínica Estética",
    "Clínica Odontológica",
    "Oficina Mecânica",
)


class AutonomousOutreachEngine:
    """
    Motor 100% Autónomo Zero-Clique de Prospecção & Fechamento 24/7 no WhatsApp Real:
      1. Roda em background contínuo sem precisar clicar em nenhum botão;
      2. Rotaciona automaticamente por +170 combinações de Cidades × Nichos lucrativos;
      3. Respeita janela comercial brasileira (08h-20h30 BRT) e limite diário anti-banimento;
      4. Responde clientes 24/7 e emite Pix Asaas (plano cheio ou Ativação Expressa R$ 49,90)!
    """

    _autopilot_enabled: bool = True
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
    async def send_single_lead_now(
        cls,
        db: AsyncSession,
        business_name: str,
        phone_digits: str,
        message: str,
        venture_name: str = "AgendaCorte Pro AI",
        price_usd: float = 19.0,
    ) -> dict:
        wa_state = await EvolutionWhatsAppManager.get_status(db)
        if wa_state.get("status") != "CONNECTED":
            return {"ok": False, "error": "WHATSAPP_NOT_CONNECTED"}

        res = await EvolutionWhatsAppManager.send_real_whatsapp(phone_digits, message)
        if not res.get("ok"):
            return res

        cls._refresh_daily_counter()
        cls._daily_sent_count += 1
        cls._total_sent_session += 1

        interaction = OmnichannelInteraction(
            id=f"omni-{uuid.uuid4().hex[:10]}",
            channel="WHATSAPP_REAL_AUTO",
            department="SALES",
            contact_name=business_name[:80],
            contact_handle=phone_digits,
            inbound_message=f"[Disparo Autónomo — {venture_name}]",
            agent_response=message[:1500],
            sentiment="OUTBOUND_SENT",
            deal_stage="CONTACTED_AUTO",
            deal_value_usd=price_usd,
        )
        db.add(interaction)
        await db.commit()

        await event_bus.publish(
            event_type="AUTO_WHATSAPP_SENT",
            agent_slug="sales-closer",
            level="SUCCESS",
            message=f"📲 [Piloto 24/7] Agente abordou sozinho: {business_name} ({phone_digits})!",
        )
        return {"ok": True, "jid": res.get("jid")}

    @classmethod
    async def start_autonomous_batch(
        cls,
        db: AsyncSession,
        niche: str,
        city: str,
        venture_id: str | None = None,
        public_base_url: str = "https://autonomous-empire-os.onrender.com",
        max_leads: int = 5,
    ) -> dict:
        wa_state = await EvolutionWhatsAppManager.get_status(db)
        if wa_state.get("status") != "CONNECTED":
            return {
                "ok": False,
                "error": "WHATSAPP_NOT_CONNECTED",
                "message": "Conecta primeiro o teu WhatsApp com o Código de 8 Dígitos para os agentes poderem enviar mensagens sozinhos!",
            }

        if cls._running_campaign:
            return {
                "ok": True,
                "already_running": True,
                "stats": cls.get_campaign_status(),
            }

        hunt = await RealLeadHunter.hunt_real_businesses(
            db=db,
            niche=niche,
            city=city,
            venture_id=venture_id,
            public_base_url=public_base_url,
        )
        leads_with_phone = [l for l in hunt.get("leads", []) if l.get("phone_digits")]

        existing_res = await db.execute(select(OmnichannelInteraction.contact_handle))
        already_contacted = {str(r[0]) for r in existing_res.all() if r[0]}
        fresh_leads = [l for l in leads_with_phone if l["phone_digits"] not in already_contacted][:max_leads]

        cls._running_campaign = True
        cls._last_campaign_stats = {
            "running": True,
            "target_query": f"{niche} — {city}",
            "queued": len(fresh_leads),
            "sent": 0,
            "skipped_no_wa": 0,
            "last_contacted": cls._last_campaign_stats.get("last_contacted", ""),
        }

        asyncio.create_task(cls._background_cadence_worker(fresh_leads))

        return {
            "ok": True,
            "queued_with_phone": len(fresh_leads),
            "total_found": hunt.get("count", 0),
            "leads": hunt.get("leads", []),
            "stats": cls.get_campaign_status(),
        }

    @classmethod
    async def _background_cadence_worker(cls, leads: list[dict]) -> None:
        try:
            for idx, lead in enumerate(leads):
                async with AsyncSessionLocal() as db:
                    wa_state = await EvolutionWhatsAppManager.get_status(db)
                    if wa_state.get("status") != "CONNECTED":
                        break

                    res = await cls.send_single_lead_now(
                        db=db,
                        business_name=lead["business_name"],
                        phone_digits=lead["phone_digits"],
                        message=lead["whatsapp_pitch"],
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
    async def handle_real_whatsapp_reply(
        cls,
        db: AsyncSession,
        phone: str,
        contact_name: str,
        message: str,
    ) -> str:
        hist_res = await db.execute(
            select(OmnichannelInteraction)
            .where(OmnichannelInteraction.contact_handle == phone)
            .order_by(desc(OmnichannelInteraction.created_at))
            .limit(4)
        )
        history = hist_res.scalars().all()

        ven_res = await db.execute(select(BusinessVenture))
        ventures = ven_res.scalars().all()
        chosen_venture = ventures[0] if ventures else None
        hist_blob = " ".join(f"{h.inbound_message} {h.agent_response}" for h in history) + " " + message
        for v in ventures:
            if v.name.lower() in hist_blob.lower():
                chosen_venture = v
                break

        ven_name = chosen_venture.name if chosen_venture else "AgendaCorte Pro AI"
        price_usd = chosen_venture.monthly_price_usd if chosen_venture else 19.0
        price_brl = f"{round(price_usd * 5.65, 2):.2f}".replace(".", ",")
        pub_url = (
            f"https://autonomous-empire-os.onrender.com{chosen_venture.public_url}"
            if chosen_venture
            else "https://autonomous-empire-os.onrender.com"
        )

        low_msg = message.lower()
        has_price_objection = any(kw in low_msg for kw in OBJECTION_KEYWORDS)
        wants_to_buy = any(kw in low_msg for kw in BUYING_KEYWORDS)

        pix_block = ""
        deal_stage = "IN_NEGOTIATION"
        billed_usd = price_usd

        if has_price_objection:
            # Isca irresistível de caixa rápido: Ativação Expressa R$ 49,90 (8.8319 * 5.65 = 49.90)
            billed_usd = 8.8319
            inv = await PaymentGatewayManager.create_invoice(
                db=db,
                provider="ASAAS_PIX",
                client_name=contact_name[:75],
                client_email="cliente@whatsapp.com.br",
                description=f"Ativacao {ven_name}",
                amount_usd=billed_usd,
            )
            if inv.pix_copy_paste:
                pix_block = (
                    f"\n\n🔥 *Condição Especial Liberada — Ativação + 15 Dias de Uso ({ven_name}) por apenas R$ 49,90 no Pix:*\n\n"
                    f"{inv.pix_copy_paste}\n\n"
                    f"É só copiar e colar no seu banco que já liberamos seu sistema personalizado agora!"
                )
                deal_stage = "PIX_PROMO_49_SENT"
        elif wants_to_buy:
            inv = await PaymentGatewayManager.create_invoice(
                db=db,
                provider="ASAAS_PIX",
                client_name=contact_name[:75],
                client_email="cliente@whatsapp.com.br",
                description=f"{ven_name} Mensal",
                amount_usd=price_usd,
            )
            if inv.pix_copy_paste:
                pix_block = (
                    f"\n\n✅ *Aqui está o seu Pix Copia e Cola oficial ({ven_name} — R$ {price_brl}/mês):*\n\n"
                    f"{inv.pix_copy_paste}\n\n"
                    f"Assim que confirmar o Pix, nosso sistema já libera seu painel automaticamente!"
                )
                deal_stage = "PIX_SENT_AUTO"

        llm_reply = await MultiModelLLMGateway.complete(
            db=db,
            agent_id="agent-sales",
            task_id=None,
            system_prompt=(
                f"És o consultor comercial humano e simpático do SaaS '{ven_name}' (R$ {price_brl}/mês no Pix, sem fidelidade). "
                "Responde no WhatsApp em português do Brasil natural, curto (máximo 3 frases diretas), tirando a dúvida do cliente "
                + (
                    "e avisando que liberaste uma ativação promocional de 15 dias por apenas R$ 49,90 com o Pix Copia e Cola logo abaixo."
                    if has_price_objection and pix_block
                    else (
                        "e avisando que já geraste o Pix Copia e Cola logo abaixo para ativar agora."
                        if pix_block
                        else f"e perguntando se podes liberar a ativação promocional hoje (temos teste de 15 dias por R$ 49,90 ou plano completo R$ {price_brl}/mês) com demonstração em {pub_url}."
                    )
                )
            ),
            user_prompt=f"Cliente ({contact_name}) respondeu no WhatsApp: '{message}'",
            operation_label=f"Closer WhatsApp Autónomo ({contact_name})",
            strategy="MARGIN_OPTIMIZED",
            local_fallback_text=(
                f"Show, {contact_name}! Com o *{ven_name}* sua loja atende e vende no automático 24h pelo WhatsApp."
                + (
                    ""
                    if pix_block
                    else f" Posso liberar nossa ativação promocional de 15 dias por R$ 49,90 no Pix para você testar hoje?"
                )
            ),
        )

        final_reply = llm_reply.content.strip() + pix_block

        interaction = OmnichannelInteraction(
            id=f"omni-{uuid.uuid4().hex[:10]}",
            channel="WHATSAPP_REAL_AUTO",
            department="SALES",
            contact_name=contact_name[:80],
            contact_handle=phone,
            inbound_message=message[:1000],
            agent_response=final_reply[:1800],
            sentiment="BUYING_INTENT" if (wants_to_buy or has_price_objection) else "QUESTION",
            deal_stage=deal_stage,
            deal_value_usd=round(billed_usd, 2) if pix_block else 0.0,
        )
        db.add(interaction)
        await db.commit()

        await event_bus.publish(
            event_type="AUTO_WHATSAPP_CLOSER_REPLY",
            agent_slug="sales-closer",
            level="SUCCESS",
            message=(
                f"🤖💬 [Closer IA] Cliente '{contact_name}' respondeu ('{message[:45]}') -> "
                + ("Pix Asaas enviado automaticamente no WhatsApp!" if pix_block else "Dúvida respondida sozinha no WhatsApp!")
            ),
        )

        if pix_block:
            brl_sent = "49,90 (Promo 15 dias)" if has_price_objection else f"{price_brl}/mês"
            await EvolutionWhatsAppManager.notify_owner_vip(
                f"🔔 *[ALERTA VIP • CLIENTE PEDIU PIX!]*\n\n"
                f"🏪 *Cliente:* {contact_name} (+{phone})\n"
                f"📦 *Sistema:* {ven_name}\n"
                f"💳 *Cobrança enviada:* R$ {brl_sent}\n"
                f"💬 *Mensagem dele:* \"{message[:120]}\"\n\n"
                f"🤖 Seu Agente Closer já enviou o Pix Copia e Cola na conversa!"
            )

        return final_reply
