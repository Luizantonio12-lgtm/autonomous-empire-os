"""Fila Asaas restrita a sandbox. Não libera produtos nem liquida faturas.

Persistir antes de responder e validar cobranças separadamente. Para uso em
produção faltam reconciliação transacional, liberação e testes com provedor.
"""
import hashlib
import os
import re
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models import AsaasWebhookInbox, PaymentInvoice, PixInvoiceExpectation
from packages.llm_router.vault import ConfigVault
from packages.payments.asaas_validation import verify_static_pix

SANDBOX_BASE = 'https://api-sandbox.asaas.com/v3'
SAFE_ID = re.compile(r'^[A-Za-z0-9_-]{1,128}$')
UNSAFE_CHARS = re.compile(r'[^A-Za-z0-9_-]')


def stable_event_id(raw_id):
    if SAFE_ID.fullmatch(raw_id):
        return raw_id
    d = hashlib.sha256(raw_id.encode('utf-8','surrogatepass')).hexdigest()[:16]
    b = UNSAFE_CHARS.sub('-', raw_id).strip('-') or 'evento'
    return f'{b[:111]}-{d}'


def sandbox_enabled() -> bool:
    return (os.getenv('ASAAS_SANDBOX_INBOX_ENABLED', '').lower() == 'true'
            and os.getenv('ASAAS_BASE_URL', '').rstrip('/') == SANDBOX_BASE)


def normalize_event(body: object) -> tuple[str, str, str | None]:
    if not isinstance(body, dict):
        raise ValueError('Evento inválido')
    raw_id, event_type = body.get('id'), body.get('event')
    if not isinstance(raw_id, str) or not 1 <= len(raw_id) <= 256:
        raise ValueError('Identificador de evento inválido')
    event_id = stable_event_id(raw_id)
    if not isinstance(event_type, str) or not SAFE_ID.fullmatch(event_type) or len(event_type) > 96:
        raise ValueError('Tipo de evento inválido')
    payment = body.get('payment')
    if payment is None:
        payment_id = None
    elif isinstance(payment, dict):
        payment_id = payment.get('id')
        if not isinstance(payment_id, str) or not SAFE_ID.fullmatch(payment_id):
            raise ValueError('Identificador de pagamento inválido')
    else:
        raise ValueError('Pagamento inválido')
    if event_type == 'PAYMENT_RECEIVED' and not payment_id:
        raise ValueError('Pagamento ausente')
    return event_id, event_type, payment_id


async def record_event(db: AsyncSession, body: object) -> bool:
    """True se criado, False para reentrega idêntica; não processa pagamento."""
    event_id, event_type, payment_id = normalize_event(body)
    db.add(AsaasWebhookInbox(event_id=event_id, event_type=event_type, payment_id=payment_id, status='PENDING_REVIEW'))
    try:
        await db.commit()
        return True
    except IntegrityError:
        await db.rollback()
        existing = await db.get(AsaasWebhookInbox, event_id)
        if not existing or existing.event_type != event_type or existing.payment_id != payment_id:
            raise ValueError('Conflito de identificador de evento')
        return False


async def verify_received_event(db: AsyncSession, event_id: str) -> dict:
    """Consulta cobrança no Sandbox Asaas e registra conferência sem liquidar."""
    if not sandbox_enabled():
        raise RuntimeError('Somente sandbox')
    if not isinstance(event_id, str) or not 1 <= len(event_id) <= 256:
        raise ValueError('Evento inválido')
    event = await db.get(AsaasWebhookInbox, stable_event_id(event_id))
    if not event:
        raise LookupError('Evento não encontrado')
    if event.event_type != 'PAYMENT_RECEIVED' or not event.payment_id:
        return {'status': event.status, 'reason': 'evento_nao_recebido'}
    api_key = await ConfigVault.get_secret(db, 'ASAAS_API_KEY')
    if not api_key:
        raise RuntimeError('Chave Sandbox não configurada')
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            response = await client.get(f'{SANDBOX_BASE}/payments/{event.payment_id}', headers={'access_token': api_key})
            response.raise_for_status()
            payment = response.json()
        if not isinstance(payment, dict):
            raise ValueError('Resposta inválida')
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError('Consulta ao Sandbox indisponível') from exc
    qr_id = payment.get('pixQrCodeId')
    rows = (await db.execute(select(PaymentInvoice, PixInvoiceExpectation)
        .join(PixInvoiceExpectation, PixInvoiceExpectation.invoice_id == PaymentInvoice.id)
        .where(PaymentInvoice.provider == 'ASAAS_PIX', PaymentInvoice.external_id == qr_id))).all()
    invoice_id = None
    if len(rows) != 1:
        verified, reason = False, 'qr_sem_fatura_unica_ou_legado'
    else:
        invoice, expectation = rows[0]
        candidate = SimpleNamespace(external_id=invoice.external_id, expected_amount_brl=Decimal(expectation.amount_brl_cents)/100)
        webhook = {'id': event.event_id, 'event': event.event_type, 'payment': {'id': event.payment_id}}
        verified, reason = verify_static_pix(webhook, payment, candidate)
        if verified:
            invoice_id = invoice.id
    event.status = 'VERIFIED_NOT_SETTLED' if verified else 'NEEDS_REVIEW'
    event.verification_reason = reason
    event.invoice_id = invoice_id
    event.verified_at = datetime.now(timezone.utc)
    await db.commit()
    return {'status': event.status, 'reason': reason, 'invoice_id': invoice_id}
