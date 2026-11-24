import base64
import binascii
import hashlib
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.agents.llm_interceptor import FinancialLedgerInterceptor
from packages.database.event_bus import event_bus
from packages.database.models import PaymentInvoice, PixInvoiceExpectation
from packages.llm_router.vault import ConfigVault


def generate_matrix_qr_svg(payload_text: str, accent_color: str = "#10b981") -> str:
    """
    Gera QR Matrix SVG autónomo (zero dependências externas) para pré-visualização
    instantânea quando em modo sandbox sem chave real.
    """
    size = 21
    digest = hashlib.sha256(payload_text.encode("utf-8")).digest()
    cells: list[str] = []

    def is_finder(r: int, c: int) -> bool:
        for fr, fc in ((0, 0), (0, size - 7), (size - 7, 0)):
            if fr <= r < fr + 7 and fc <= c < fc + 7:
                lr, lc = r - fr, c - fc
                if lr in (0, 6) or lc in (0, 6) or (2 <= lr <= 4 and 2 <= lc <= 4):
                    return True
                return False
        return False

    bit_idx = 0
    for r in range(size):
        for c in range(size):
            in_finder_zone = (
                (r < 8 and c < 8)
                or (r < 8 and c >= size - 8)
                or (r >= size - 8 and c < 8)
            )
            if in_finder_zone:
                on = is_finder(r, c)
            else:
                byte_val = digest[(bit_idx // 8) % len(digest)]
                on = bool((byte_val >> (bit_idx % 8)) & 1)
                bit_idx += 1

            if on:
                fill = accent_color if in_finder_zone else "#f8fafc"
                cells.append(
                    f'<rect x="{12 + c * 8}" y="{12 + r * 8}" width="7" height="7" rx="1.2" fill="{fill}"/>'
                )

    svg_dim = 24 + size * 8
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_dim} {svg_dim}" width="192" height="192">'
        f'<rect width="{svg_dim}" height="{svg_dim}" rx="14" fill="#020617" stroke="#1e293b" stroke-width="2"/>'
        + "".join(cells)
        + "</svg>"
    )


class PaymentGatewayUnavailable(Exception):
    """Não foi possível criar uma cobrança real no provedor."""


class PaymentGatewayManager:
    """
    Conector Financeiro de Produção:
      - STRIPE: Cria Checkout Sessions reais via API REST Stripe (quando STRIPE_SECRET_KEY ativa)
      - ASAAS_PIX: Gera QR Code Pix Banco Central real (EMV + imagem escaneável) via Asaas API v3
      - Webhook Conciliador: Liquida faturas PENDING -> PAID e credita automaticamente o FinancialLedger.
    """

    @classmethod
    async def create_invoice(
        cls,
        db: AsyncSession,
        provider: str,  # STRIPE | ASAAS_PIX
        client_name: str,
        client_email: str,
        description: str,
        amount_usd: float,
    ) -> PaymentInvoice:
        inv_id = f"inv-{uuid.uuid4().hex[:8]}"
        provider_clean = provider.upper()
        # Enquanto a reconciliação segura está em homologação, esta branch
        # não cria cobranças reais, inclusive pelo painel administrativo.
        from packages.payments.asaas_sandbox_inbox import sandbox_enabled
        if provider_clean != 'ASAAS_PIX' or not sandbox_enabled():
            raise PaymentGatewayUnavailable('Cobranças disponíveis apenas no Sandbox Asaas de teste.')
        checkout_url: str | None = None
        pix_copy_paste: str | None = None
        pix_qr_svg: str | None = None
        external_id = f"ext_{uuid.uuid4().hex[:12]}"
        amount_brl_cents: int | None = None

        if provider_clean == "STRIPE":
            stripe_key = await ConfigVault.get_secret(db, "STRIPE_SECRET_KEY")
            if stripe_key:
                try:
                    async with httpx.AsyncClient(timeout=12.0) as client:
                        resp = await client.post(
                            "https://api.stripe.com/v1/checkout/sessions",
                            headers={"Authorization": f"Bearer {stripe_key}"},
                            data={
                                "mode": "payment",
                                "customer_email": client_email,
                                "success_url": "https://autonomous-empire-os.onrender.com/?paid=1",
                                "cancel_url": "https://autonomous-empire-os.onrender.com/",
                                "line_items[0][price_data][currency]": "usd",
                                "line_items[0][price_data][product_data][name]": description,
                                "line_items[0][price_data][unit_amount]": int(round(amount_usd * 100)),
                                "line_items[0][quantity]": 1,
                                "metadata[empire_invoice_id]": inv_id,
                            },
                        )
                        if resp.status_code < 300:
                            sdata = resp.json()
                            external_id = sdata["id"]
                            checkout_url = sdata.get("url")
                except Exception:
                    pass

            if not checkout_url:
                raise PaymentGatewayUnavailable("Não foi possível criar checkout Stripe real.")

        else:  # ASAAS_PIX (Produção Real Banco Central)
            asaas_key = await ConfigVault.get_secret(db, "ASAAS_API_KEY")
            asaas_base = os.getenv("ASAAS_BASE_URL", "https://api.asaas.com/v3").rstrip("/")
            asaas_headers = {
                "access_token": asaas_key or "",
                "User-Agent": "AutonomousEmpireOS/3.0",
                "Content-Type": "application/json",
            }
            if asaas_key:
                try:
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        # 1. Obtém chave Pix EVP ativa da conta Asaas (ou cria automaticamente)
                        address_key: str | None = None
                        keys_resp = await client.get(
                            f"{asaas_base}/pix/addressKeys",
                            headers=asaas_headers,
                        )
                        if keys_resp.status_code < 300:
                            items = keys_resp.json().get("data", [])
                            active_keys = [k for k in items if k.get("status") == "ACTIVE"]
                            if active_keys:
                                address_key = active_keys[0].get("key")

                        if not address_key:
                            create_key_resp = await client.post(
                                f"{asaas_base}/pix/addressKeys",
                                headers=asaas_headers,
                                json={"type": "EVP"},
                            )
                            if create_key_resp.status_code < 300:
                                address_key = create_key_resp.json().get("key")

                        # 2. Gera QR Code Pix oficial escaneável em Reais (BRL)
                        if address_key:
                            brl_amount = max((Decimal(str(amount_usd)) * Decimal('5.65')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), Decimal('1.00'))
                            brl_value = float(brl_amount)
                            amount_brl_cents = int(brl_amount * 100)
                            clean_desc = (description or "NexusFlow AI").strip()[:35]
                            qr_resp = await client.post(
                                f"{asaas_base}/pix/qrCodes/static",
                                headers=asaas_headers,
                                json={
                                    "addressKey": address_key,
                                    "description": clean_desc,
                                    "value": brl_value,
                                    "format": "ALL",
                                    "allowsMultiplePayments": False,
                                    "externalReference": inv_id,
                                },
                            )
                            if qr_resp.status_code < 300:
                                qdata = qr_resp.json()
                                external_id = qdata.get("id", external_id)
                                pix_copy_paste = qdata.get("payload")
                                encoded_img = qdata.get("encodedImage")
                                if isinstance(encoded_img, str) and len(encoded_img) <= 1_000_000:
                                    try:
                                        raw = base64.b64decode(encoded_img, validate=True)
                                    except (ValueError, binascii.Error):
                                        raw = b''
                                    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
                                        safe_image = base64.b64encode(raw).decode('ascii')
                                        pix_qr_svg = (
                                            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192" width="192" height="192">'
                                            '<rect width="192" height="192" rx="12" fill="#ffffff"/>'
                                            f'<image href="data:image/png;base64,{safe_image}" x="8" y="8" width="176" height="176"/>'
                                            "</svg>"
                                        )
                except Exception:
                    pass

            if not pix_copy_paste or not isinstance(external_id, str) or not external_id or external_id.startswith('ext_') or amount_brl_cents is None:
                # Nunca apresentar um payload sintético ou QR sem ID conciliável.
                raise PaymentGatewayUnavailable("Não foi possível criar Pix real no Asaas.")
            # Sem imagem do provedor, ofereça apenas o código copia e cola.
            # generate_matrix_qr_svg não é um codificador QR válido.

        invoice = PaymentInvoice(
            id=inv_id,
            provider=provider_clean,
            external_id=external_id,
            client_name=client_name,
            client_email=client_email,
            description=description,
            # Preserve a precisão usada na conversão para BRL; registros antigos
            # arredondados a dois decimais ainda exigem revisão individual.
            amount_usd=round(amount_usd, 4),
            status="PENDING",
            checkout_url=checkout_url,
            pix_copy_paste=pix_copy_paste,
            pix_qr_svg=pix_qr_svg,
        )
        db.add(invoice)
        if provider_clean == 'ASAAS_PIX' and amount_brl_cents is not None:
            db.add(PixInvoiceExpectation(invoice_id=inv_id, amount_brl_cents=amount_brl_cents))
        await db.commit()

        await event_bus.publish(
            event_type="PAYMENT_INVOICE_CREATED",
            agent_slug="finance-cfo",
            level="INFO",
            message=f"[{provider_clean}] Cobrança emitida ({inv_id}) para {client_name}: ${amount_usd:,.2f} USD.",
            payload={"invoice_id": inv_id, "provider": provider_clean, "amount_usd": amount_usd},
        )
        return invoice

    @classmethod
    async def reconcile_paid_webhook(
        cls,
        db: AsyncSession,
        invoice_id: str,
    ) -> PaymentInvoice:
        res = await db.execute(select(PaymentInvoice).where(PaymentInvoice.id == invoice_id))
        inv = res.scalar_one_or_none()
        if not inv:
            raise ValueError(f"Fatura {invoice_id} não encontrada.")
        if inv.status == "PAID":
            return inv

        inv.status = "PAID"
        inv.paid_at = datetime.now(timezone.utc)

        # Se a fatura corresponder a uma Empresa SaaS ativa, atualiza MRR e Clientes Pagantes automaticamente!
        from packages.database.models import BusinessVenture

        v_res = await db.execute(select(BusinessVenture))
        for venture in v_res.scalars().all():
            if venture.name.lower() in (inv.description or "").lower():
                venture.active_customers = (venture.active_customers or 0) + 1
                venture.mrr_usd = round((venture.mrr_usd or 0.0) + inv.amount_usd, 2)
                venture.total_revenue_usd = round((venture.total_revenue_usd or 0.0) + inv.amount_usd, 2)
                break

        await db.commit()

        await FinancialLedgerInterceptor.record_custom_transaction(
            db=db,
            entry_type="REVENUE",
            category=f"GATEWAY_{inv.provider}",
            amount_usd=inv.amount_usd,
            description=f"Liquidação {inv.provider} ({inv.id}) — {inv.client_name}: {inv.description}",
            agent_id="agent-finance",
            metadata={
                "invoice_id": inv.id,
                "external_id": inv.external_id,
                "provider": inv.provider,
            },
        )

        await event_bus.publish(
            event_type="PAYMENT_WEBHOOK_SETTLED",
            agent_slug="finance-cfo",
            level="SUCCESS",
            message=f"WEBHOOK {inv.provider} CONFIRMADO! +${inv.amount_usd:,.2f} USD liquidados por {inv.client_name}.",
            payload={"invoice_id": inv.id, "amount_usd": inv.amount_usd},
        )

        try:
            import re
            from packages.database.models import OmnichannelInteraction
            from packages.integrations.whatsapp_evolution import EvolutionWhatsAppManager

            brl_paid = f"{round(inv.amount_usd * 5.65, 2):.2f}".replace(".", ",")
            await EvolutionWhatsAppManager.notify_owner_vip(
                f"💰🚀 *[VENDA CONFIRMADA NO PIX!]*\n\n"
                f"💵 *Valor Recebido:* R$ {brl_paid}\n"
                f"🏪 *Cliente:* {inv.client_name}\n"
                f"📦 *Descrição:* {inv.description}\n\n"
                f"✅ Pagamento conciliado no Asaas e somado ao Caixa Real do seu Empire OS!"
            )

            # Entrega automática pós-Pix no WhatsApp do comprador (Ideia #3, #4 e #5)!
            buyer_phone = ""
            email_prefix = (inv.client_email or "").split("@")[0]
            email_digits = re.sub(r"\D", "", email_prefix)
            if len(email_digits) >= 10:
                buyer_phone = email_digits
            else:
                om_res = await db.execute(
                    select(OmnichannelInteraction)
                    .where(OmnichannelInteraction.contact_name == inv.client_name)
                    .order_by(OmnichannelInteraction.created_at.desc())
                    .limit(1)
                )
                om = om_res.scalar_one_or_none()
                if om and om.contact_handle:
                    d = re.sub(r"\D", "", om.contact_handle)
                    if len(d) >= 10:
                        buyer_phone = d

            if buyer_phone:
                code_tag = inv.id[-6:].upper()
                if "trickspace" in (inv.description or "").lower():
                    pro_key = f"TSPRO-{code_tag}-VIP"
                    await EvolutionWhatsAppManager.send_real_whatsapp(
                        buyer_phone,
                        f"🎮⚡ *[TRICKSPACE ZEROLAG v2.6 PRO LIBERADO!]*\n\n"
                        f"Pagamento Pix confirmado, *{inv.client_name}*!\n\n"
                        f"🔑 *Sua Chave Pro Vitalícia:* `{pro_key}`\n"
                        f"📥 *Baixar APK Oficial (1 Toque):*\n"
                        f"https://github.com/Luizantonio12-lgtm/autonomous-empire-os/releases/download/v3.0-downloads/TrickSpace-ZeroLag-v2.6.apk\n\n"
                        f"Instale, toque em '🔋 Blindar Bateria' e ative a Bolinha Flutuante. Bom jogo! 🔥",
                    )
                else:
                    portal_url = f"https://autonomous-empire-os.onrender.com/meu-robo/{inv.id}"
                    ref_url = f"https://autonomous-empire-os.onrender.com/vitrine?ref={code_tag}"
                    await EvolutionWhatsAppManager.send_real_whatsapp(
                        buyer_phone,
                        f"🎉🚀 *[PAGAMENTO CONFIRMADO • SEU ROBÔ IA ESTÁ LIBERADO!]*\n\n"
                        f"Seja muito bem-vindo(a), *{inv.client_name}*! Configure agora em 1 minuto os horários, serviços/preços e chave Pix da sua empresa no seu Portal Exclusivo:\n"
                        f"👉 {portal_url}\n\n"
                        f"🎁 *Bônus Indique & Ganhe 1 Mês Grátis:* mande seu link abaixo para 1 amigo dono de negócio — se ele ativar, você ganha +30 dias grátis:\n"
                        f"{ref_url}",
                    )
        except Exception:
            pass

        return inv

    @classmethod
    async def handle_asaas_webhook(
        cls,
        db: AsyncSession,
        body: dict,
    ) -> dict:
        event = str(body.get("event", ""))
        payment = body.get("payment") or {}
        if event not in ("PAYMENT_RECEIVED", "PAYMENT_CONFIRMED"):
            return {"ignored": True, "event": event}

        ext_ref = payment.get("externalReference")
        pix_qr_id = payment.get("pixQrCodeId")
        pay_id = payment.get("id")

        filters = []
        if ext_ref:
            filters.append(PaymentInvoice.id == str(ext_ref))
        if pix_qr_id:
            filters.append(PaymentInvoice.external_id == str(pix_qr_id))
        if pay_id:
            filters.append(PaymentInvoice.external_id == str(pay_id))

        if filters:
            res = await db.execute(select(PaymentInvoice).where(or_(*filters)))
            inv = res.scalars().first()
            if inv:
                settled = await cls.reconcile_paid_webhook(db, inv.id)
                return {"settled": True, "invoice_id": settled.id}

        # Caso seja um Pix recebido diretamente na chave EVP fora de uma fatura prévia
        brl_val = float(payment.get("value") or 0.0)
        if brl_val > 0:
            usd_equiv = round(brl_val / 5.65, 2)
            await FinancialLedgerInterceptor.record_custom_transaction(
                db=db,
                entry_type="REVENUE",
                category="GATEWAY_ASAAS_PIX",
                amount_usd=usd_equiv,
                description=f"Pix Real Recebido no Asaas (R$ {brl_val:,.2f} BRL) — ref {pay_id}",
                agent_id="agent-finance",
                metadata={"asaas_payment_id": pay_id, "value_brl": brl_val},
            )
            await event_bus.publish(
                event_type="PAYMENT_WEBHOOK_SETTLED",
                agent_slug="finance-cfo",
                level="SUCCESS",
                message=f"PIX REAL RECEBIDO NO ASAAS! R$ {brl_val:,.2f} (+${usd_equiv:,.2f} USD) creditados no Caixa.",
                payload={"value_brl": brl_val, "amount_usd": usd_equiv},
            )
            try:
                from packages.integrations.whatsapp_evolution import EvolutionWhatsAppManager

                brl_fmt = f"{brl_val:.2f}".replace(".", ",")
                await EvolutionWhatsAppManager.notify_owner_vip(
                    f"💰🚀 *[PIX REAL RECEBIDO NO ASAAS!]*\n\n"
                    f"💵 *Valor Creditado:* R$ {brl_fmt}\n"
                    f"🔖 *Referência:* {pay_id}\n\n"
                    f"✅ O saldo do seu Empire OS já foi atualizado automaticamente!"
                )
            except Exception:
                pass
            return {"settled": True, "direct_pix": True, "value_brl": brl_val}

        return {"ignored": True}
