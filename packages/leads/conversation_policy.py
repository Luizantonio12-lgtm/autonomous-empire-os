"""Modo conservador de atendimento: respostas breves e sem prospecção ativa.

A reserva do ID acontece antes da resposta. Isso prioriza não duplicar: se o
processo cair após a reserva, a resposta pode não ser enviada. Identificações
@lid sem associação confiável a um número não são tratadas automaticamente.
"""
import hashlib
import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models import OmnichannelInteraction, WhatsAppContactPreference, WhatsAppHandoffWindow, WhatsAppInboundClaim, WhatsAppReplyDelivery, WhatsAppReplyWindow


def canonical_phone_jid(jid: str) -> str | None:
    jid = (jid or '').strip().lower()
    if not (jid.endswith('@s.whatsapp.net') or jid.endswith('@c.us')):
        return None
    phone = jid.split('@', 1)[0].split(':', 1)[0]
    if not phone.isascii() or not phone.isdigit() or not 12 <= len(phone) <= 15:
        return None
    # Brasil: celular antigo de oito dígitos, quando o prefixo móvel é inequívoco.
    if phone.startswith('55') and len(phone) == 12 and phone[4] in '6789':
        phone = phone[:4] + '9' + phone[4:]
    return phone


def message_hash_for(phone_jid: str, message_id: str) -> str | None:
    contact = canonical_phone_jid(phone_jid)
    if not contact or not isinstance(message_id, str) or not 1 <= len(message_id) <= 128 or any(ord(c) < 32 for c in message_id):
        return None
    return hashlib.sha256(f'{contact}|{message_id}'.encode()).hexdigest()


def normalize_text(text: str) -> str:
    text = unicodedata.normalize('NFKD', (text or '').lower())
    return ''.join(c for c in text if not unicodedata.combining(c)).strip()


def asks_to_stop(text: str) -> bool:
    s = normalize_text(text)
    simple = re.sub(r'[^a-z0-9 ]', '', s).strip()
    if simple in {'pare', 'parar', 'sair', 'cancelar', 'descadastrar', 'nao quero', 'nao tenho interesse'}:
        return True
    return bool(re.search(r'\b(nao (me )?(mande|envie|chame|contate|ligue)|nao quero receber|pare de (me )?(mandar|enviar)|remova? (meu numero|meu contato))\b', s))


def choose_reply(message: str, *, first: bool, image: bool = False, audio: bool = False) -> str:
    """Respostas fixas; não chama IA nem promete resultados ou recebimento."""
    if image:
        return 'Recebi sua imagem. Se for um comprovante, o pagamento precisa ser confirmado pela equipe no Asaas.'
    if audio:
        return 'Recebi seu áudio. Pode me contar por escrito como posso ajudar?'
    s = normalize_text(message)
    if re.search(r'\b(obrigad[oa]|valeu|agradeco)\b', s):
        return 'Por nada! Se precisar, estou à disposição.'
    if re.search(r'\b(pix|pagar|pagamento|cobranca|comprovante)\b', s):
        return 'Posso ajudar com sua dúvida sobre pagamento. A equipe precisa confirmar os dados antes de qualquer cobrança.'
    if re.search(r'\b(preco|valor|custa|quanto|planos?)\b', s):
        return 'O teste foi anunciado por R$ 49,90 para 15 dias. Nossa equipe pode confirmar as condições e a disponibilidade.'
    if re.search(r'\b(demo|demonstracao|testar|teste|funciona)\b', s):
        return 'Posso explicar a proposta. Qual é o tipo do seu negócio e o que você precisa no WhatsApp?'
    if first:
        return 'Olá! Sou o assistente virtual da equipe. Como posso ajudar?'
    return 'Entendi. Qual informação você precisa?'


async def reserve_handoff(db: AsyncSession, contact: str) -> bool:
    """Reserva atômica, no máximo um comando ⚡ por contato a cada 24h."""
    now = datetime.now(timezone.utc)
    db.add(WhatsAppHandoffWindow(contact_key=contact, last_sent_at=now))
    try:
        await db.commit()
        return True
    except IntegrityError:
        await db.rollback()
    result = await db.execute(update(WhatsAppHandoffWindow)
        .where(WhatsAppHandoffWindow.contact_key == contact,
               WhatsAppHandoffWindow.last_sent_at <= now - timedelta(hours=24))
        .values(last_sent_at=now))
    await db.commit()
    return result.rowcount == 1


async def reserve_reply(db: AsyncSession, contact: str) -> bool:
    """Uma resposta automática por contato em 60 segundos; não agenda reenvio."""
    now = datetime.now(timezone.utc)
    db.add(WhatsAppReplyWindow(contact_key=contact, last_reserved_at=now))
    try:
        await db.commit()
        return True
    except IntegrityError:
        await db.rollback()
    result = await db.execute(update(WhatsAppReplyWindow)
        .where(WhatsAppReplyWindow.contact_key == contact,
               WhatsAppReplyWindow.last_reserved_at <= now - timedelta(seconds=60))
        .values(last_reserved_at=now))
    await db.commit()
    return result.rowcount == 1


async def handle_inbound(db: AsyncSession, *, message_id: str, phone_jid: str, message: str,
                         name: str, audio: bool = False, image: bool = False, handoff: bool = False) -> dict:
    """Reserva uma única vez e retorna texto. Não realiza envio direto ao WhatsApp."""
    contact = canonical_phone_jid(phone_jid)
    if not contact:
        return {'reply': '', 'reason': 'UNRESOLVED_CONTACT'}
    if not isinstance(message_id, str) or not 1 <= len(message_id) <= 128 or any(ord(c) < 32 for c in message_id):
        return {'reply': '', 'reason': 'MISSING_MESSAGE_ID'}
    # A chave do evento inclui a identidade estável do número, não somente o @lid.
    event_key = message_hash_for(phone_jid, message_id)
    db.add(WhatsAppInboundClaim(message_hash=event_key, contact_key=contact))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        if await db.get(WhatsAppInboundClaim, event_key):
            return {'reply': '', 'reason': 'DUPLICATE_EVENT'}
        raise
    preference = await db.get(WhatsAppContactPreference, contact)
    stop = not handoff and asks_to_stop(message)
    if preference:
        return {'reply': '', 'reason': 'OPTED_OUT'}
    if handoff and not await reserve_handoff(db, contact):
        return {'reply': '', 'reason': 'HANDOFF_RATE_LIMIT'}
    if not stop and not await reserve_reply(db, contact):
        db.add(OmnichannelInteraction(
            id=f'omni-{uuid.uuid4().hex[:10]}', channel='WHATSAPP_REAL_AUTO', department='SALES',
            contact_name=(name or 'Cliente')[:80], contact_handle=contact,
            inbound_message='[imagem recebida]' if image else ('[áudio recebido]' if audio else message[:1000]),
            agent_response='', sentiment='NEEDS_REVIEW', deal_stage='WAIT_HUMAN_REVIEW', deal_value_usd=0.0,
        ))
        await db.commit()
        return {'reply': '', 'reason': 'REPLY_COOLDOWN'}
    if stop:
        db.add(WhatsAppContactPreference(contact_key=contact, opted_out_at=datetime.now(timezone.utc)))
        reply = 'Entendido. Não enviaremos mais mensagens automáticas para você.'
        stage = 'OPT_OUT'
    else:
        previous = (await db.execute(select(OmnichannelInteraction.id).where(
            OmnichannelInteraction.channel == 'WHATSAPP_REAL_AUTO',
            OmnichannelInteraction.contact_handle == contact,
        ).limit(1))).first()
        reply = choose_reply(message, first=not bool(previous), image=image, audio=audio)
        stage = 'IN_NEGOTIATION'
    interaction_id = f'omni-{uuid.uuid4().hex[:10]}'
    db.add(OmnichannelInteraction(
        id=interaction_id, channel='WHATSAPP_REAL_AUTO', department='SALES',
        contact_name=(name or 'Cliente')[:80], contact_handle=contact,
        inbound_message='[imagem recebida]' if image else ('[áudio recebido]' if audio else message[:1000]),
        agent_response=reply, sentiment='OPT_OUT' if stop else 'QUESTION', deal_stage=stage, deal_value_usd=0.0,
    ))
    db.add(WhatsAppReplyDelivery(message_hash=event_key, interaction_id=interaction_id, status='PREPARED'))
    await db.commit()
    return {'reply': reply, 'reason': 'REPLY_PREPARED'}
