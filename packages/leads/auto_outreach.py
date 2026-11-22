import asyncio
import random
import uuid
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.event_bus import event_bus
from packages.database.models import BusinessVenture, OmnichannelInteraction
from packages.database.session import AsyncSessionLocal
from packages.integrations.whatsapp_evolution import EvolutionWhatsAppManager
from packages.leads.lead_hunter import RealLeadHunter
from packages.llm_router import MultiModelLLMGateway
from packages.payments import PaymentGatewayManager


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


class AutonomousOutreachEngine:
    """
    Motor 100% Autónomo de Prospecção & Fechamento no WhatsApp Real:
      1. Procura empresas reais com telefone na cidade escolhida;
      2. Dispara mensagens reais uma a uma com intervalo anti-banimento humano (22-35s);
      3. Quando o dono do estabelecimento responde no WhatsApp, o Agente Closer IA
         tira dúvidas sozinho e emite/envia o Pix Copia-e-Cola oficial do Asaas na hora!
    """

    _running_campaign: bool = False
    _last_campaign_stats: dict = {
        "running": False,
        "target_query": "",
        "queued": 0,
        "sent": 0,
        "skipped_no_wa": 0,
        "last_contacted": "",
    }

    @classmethod
    def get_campaign_status(cls) -> dict:
        return dict(cls._last_campaign_stats)

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
            message=f"📲 [WhatsApp Real] Agente enviou proposta automaticamente para {business_name} ({phone_digits})!",
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
        max_leads: int = 6,
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

        # Filtra números que já foram abordados anteriormente para nunca repetir spam!
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
            "last_contacted": "",
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

                # Intervalo humano anti-banimento entre envios (22 a 34 segundos)
                if idx < len(leads) - 1:
                    await asyncio.sleep(random.uniform(22.0, 34.0))
        finally:
            cls._running_campaign = False
            cls._last_campaign_stats["running"] = False
            await event_bus.publish(
                event_type="AUTO_CAMPAIGN_FINISHED",
                agent_slug="sales-closer",
                level="SUCCESS",
                message=(
                    f"Ciclo autónomo concluído ({cls._last_campaign_stats['target_query']}): "
                    f"{cls._last_campaign_stats['sent']} propostas reais entregues no WhatsApp! Agente Closer em escuta 24/7."
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
        # Recupera histórico deste cliente para saber qual SaaS lhe foi ofertado
        hist_res = await db.execute(
            select(OmnichannelInteraction)
            .where(OmnichannelInteraction.contact_handle == phone)
            .order_by(desc(OmnichannelInteraction.created_at))
            .limit(4)
        )
        history = hist_res.scalars().all()

        # Identifica qual produto SaaS corresponde à conversa
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
        wants_to_buy = any(kw in low_msg for kw in BUYING_KEYWORDS)

        pix_block = ""
        deal_stage = "IN_NEGOTIATION"
        if wants_to_buy:
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
                    "e avisando que já geraste o Pix Copia e Cola logo abaixo para ativar agora."
                    if pix_block
                    else f"e perguntando se podes gerar o Pix de ativação (R$ {price_brl}/mês) ou se ele quer ver a demonstração em {pub_url}."
                )
            ),
            user_prompt=f"Cliente ({contact_name}) respondeu no WhatsApp: '{message}'",
            operation_label=f"Closer WhatsApp Autónomo ({contact_name})",
            strategy="MARGIN_OPTIMIZED",
            local_fallback_text=(
                f"Show, {contact_name}! Com o *{ven_name}* sua operação roda no automático 24h pelo WhatsApp sem perder nenhum cliente."
                + (
                    ""
                    if pix_block
                    else f" Posso gerar seu acesso agora por R$ {price_brl}/mês no Pix?"
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
            sentiment="BUYING_INTENT" if wants_to_buy else "QUESTION",
            deal_stage=deal_stage,
            deal_value_usd=price_usd if wants_to_buy else 0.0,
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
        return final_reply
