"""Validação preliminar de Pix estático. Não altera o banco nem liquida pagamentos.

Um chamador deve buscar a cobrança por HTTPS diretamente no Asaas, com a API key
privada, após autenticar o webhook; payloads recebidos não são prova suficiente.
Não está conectado à produção nem substitui deduplicação transacional e outbox.
"""
from decimal import Decimal, InvalidOperation
import hmac


def valid_webhook_token(expected: str, received: str) -> bool:
    """Nunca aceita token vazio; não é permitido usar API key como token."""
    if not isinstance(expected, str) or not isinstance(received, str):
        return False
    if not expected or not received:
        return False
    return hmac.compare_digest(expected.encode('utf-8'), received.encode('utf-8'))


def verify_static_pix(event: dict, provider_payment: dict, invoice) -> tuple[bool, str]:
    """Verifica identidade e valor de uma fatura nova usando dados do provedor.

    Requer invoice.expected_amount_brl como decimal exato e invoice.external_id
    persistido a partir do ID REAL do QR Asaas. O modelo atual não possui essa
    coluna: migração e teste de pagamentos legados são necessários antes do uso.
    """
    if not isinstance(event, dict) or not isinstance(provider_payment, dict):
        return False, 'formato_invalido'
    message_payment = event.get('payment')
    if not isinstance(message_payment, dict):
        return False, 'pagamento_ausente'
    event_id = event.get('id')
    payment_id = message_payment.get('id')
    if not isinstance(event_id, str) or not event_id or not isinstance(payment_id, str) or not payment_id:
        return False, 'identificadores_ausentes'
    if event.get('event') != 'PAYMENT_RECEIVED':
        return False, 'evento_nao_recebido'
    if provider_payment.get('id') != payment_id:
        return False, 'id_pagamento_divergente'
    if provider_payment.get('status') != 'RECEIVED' or provider_payment.get('billingType') != 'PIX':
        return False, 'status_ou_tipo_invalido'
    qr_id = getattr(invoice, 'external_id', None)
    if not isinstance(qr_id, str) or not qr_id or qr_id.startswith('ext_'):
        return False, 'qr_invalido'
    if provider_payment.get('pixQrCodeId') != qr_id:
        return False, 'qr_divergente'
    expected = getattr(invoice, 'expected_amount_brl', None)
    if expected is None:
        return False, 'valor_exato_indisponivel'
    try:
        amount = Decimal(str(provider_payment.get('value')))
        target = Decimal(str(expected))
        if not amount.is_finite() or not target.is_finite() or amount <= 0 or target <= 0 or amount != target:
            return False, 'valor_divergente'
    except (InvalidOperation, ValueError, TypeError):
        return False, 'valor_invalido'
    return True, 'verificado_nao_liquidado'
