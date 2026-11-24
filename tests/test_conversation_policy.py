"""Sem WhatsApp real; valida respostas e reservas persistentes."""
import unittest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from packages.database.models import Base, OmnichannelInteraction, WhatsAppHandoffWindow, WhatsAppInboundClaim, WhatsAppReplyWindow
from packages.leads.auto_outreach import AutonomousOutreachEngine
from packages.leads.conversation_policy import asks_to_stop, canonical_phone_jid, handle_inbound, choose_reply


class ConversationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with self.engine.begin() as c:
            await c.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
    async def asyncTearDown(self):
        await self.engine.dispose()
    async def talk(self, message_id, msg, phone='5516993862008@s.whatsapp.net', **kw):
        async with self.sessions() as db:
            return await handle_inbound(db,message_id=message_id,phone_jid=phone,message=msg,name='Teste',**kw)
    async def test_distinct_question_and_duplicate_across_sessions(self):
        a=await self.talk('abc','Oi')
        b=await self.talk('abc','Oi')
        c=await self.talk('def','Quanto custa?')
        self.assertEqual(a['reply'],'Olá! Sou o assistente virtual da equipe. Como posso ajudar?')
        self.assertEqual(b['reason'],'DUPLICATE_EVENT')
        self.assertEqual(b['reply'],'')
        self.assertEqual(c['reason'],'REPLY_COOLDOWN')
        async with self.sessions() as db:
            self.assertEqual(len((await db.execute(select(WhatsAppInboundClaim))).scalars().all()),2)
            rows=(await db.execute(select(OmnichannelInteraction))).scalars().all()
            self.assertEqual(len(rows),2)
            self.assertIn('WAIT_HUMAN_REVIEW', [r.deal_stage for r in rows])
            window=await db.get(WhatsAppReplyWindow,'5516993862008')
            window.last_reserved_at=datetime.now(timezone.utc)-timedelta(seconds=61)
            await db.commit()
        d=await self.talk('ghi','Quanto custa?')
        self.assertIn('R$ 49,90',d['reply'])
    async def test_missing_id_or_lid_no_send(self):
        self.assertEqual((await self.talk('', 'Oi'))['reason'],'MISSING_MESSAGE_ID')
        self.assertEqual((await self.talk('1','Oi',phone='987654321@lid'))['reason'],'UNRESOLVED_CONTACT')
    async def test_phone_alias_normalization(self):
        self.assertEqual(canonical_phone_jid('551698762345@s.whatsapp.net'),canonical_phone_jid('5516998762345@s.whatsapp.net'))
        self.assertIsNone(canonical_phone_jid('123456789012@lid'))
        self.assertIsNone(canonical_phone_jid('5516998762345@g.us'))
    async def test_stop_and_persistent_suppression(self):
        a=await self.talk('one','Não me mande mais mensagens')
        self.assertIn('Não enviaremos mais',a['reply'])
        b=await self.talk('two','Oi')
        c=await self.talk('three','[CEO_HANDOFF_TRIGGER]',handoff=True)
        self.assertEqual(b['reason'],'OPTED_OUT'); self.assertEqual(c['reply'],'')
    async def test_handoff_limit_and_customer_can_still_ask(self):
        a=await self.talk('magic1','[CEO_HANDOFF_TRIGGER]',handoff=True)
        b=await self.talk('magic2','[CEO_HANDOFF_TRIGGER]',handoff=True)
        c=await self.talk('question','Qual o preço?')
        self.assertTrue(a['reply']); self.assertEqual(b['reason'],'HANDOFF_RATE_LIMIT')
        self.assertEqual(c['reason'],'REPLY_COOLDOWN')
        async with self.sessions() as db:
            row=await db.get(WhatsAppHandoffWindow,'5516993862008')
            row.last_sent_at=datetime.now(timezone.utc)-timedelta(hours=25)
            window=await db.get(WhatsAppReplyWindow,'5516993862008')
            window.last_reserved_at=datetime.now(timezone.utc)-timedelta(seconds=61)
            await db.commit()
        self.assertTrue((await self.talk('magic3','[CEO_HANDOFF_TRIGGER]',handoff=True))['reply'])
    async def test_no_false_paid_and_stop_rules(self):
        self.assertIn('precisa ser confirmado', choose_reply('foto', first=True, image=True))
        self.assertIn('por escrito', choose_reply('audio', first=True, audio=True))
        self.assertTrue(asks_to_stop('Não me envie mensagens'))
        self.assertFalse(asks_to_stop('quero parar de perder clientes'))
    async def test_bridge_endpoint_duplicate_and_stop(self):
        import os
        import httpx
        import main
        from unittest.mock import patch
        async def fake_db():
            async with self.sessions() as db:
                yield db
        main.app.dependency_overrides[main.get_db]=fake_db
        body={'remote_jid':'5516993862008@s.whatsapp.net','phone_jid':'5516993862008@s.whatsapp.net','phone':'5516993862008','message_id':'bridge-1','message':'Oi'}
        try:
            with patch.dict(os.environ,{'WA_INTERNAL_SECRET':'s'*64}):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='https://example.test') as c:
                    h={'x-wa-internal-secret':'s'*64}
                    a=await c.post('/api/webhooks/wa-bridge-inbound',json=body,headers=h)
                    b=await c.post('/api/webhooks/wa-bridge-inbound',json=body,headers=h)
                    self.assertEqual(a.status_code,200)
                    self.assertIn('assistente virtual',a.json()['auto_reply'])
                    self.assertEqual(b.json()['reason'],'DUPLICATE_EVENT')
                    self.assertEqual(b.json()['auto_reply'],'')
                    body['message_id']='bridge-2'; body['message']='Pare'
                    stop=await c.post('/api/webhooks/wa-bridge-inbound',json=body,headers=h)
                    self.assertEqual(stop.json()['auto_reply'],'Entendido. Não enviaremos mais mensagens automáticas para você.')
        finally:
            main.app.dependency_overrides.clear()
    async def test_review_inbox_and_delivery_report(self):
        import os
        import httpx
        import main
        from unittest.mock import patch
        async def fake_db():
            async with self.sessions() as db:
                yield db
        main.app.dependency_overrides[main.get_db]=fake_db
        jid='5516993862008@s.whatsapp.net'
        base={'remote_jid':jid,'phone_jid':jid,'phone':'5516993862008','message_id':'review-1','message':'Oi'}
        try:
            with patch.dict(os.environ,{'WA_INTERNAL_SECRET':'s'*64}), patch('main.valid_session',side_effect=lambda cookie: cookie=='valid'):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='https://empire.test') as c:
                    internal={'x-wa-internal-secret':'s'*64}
                    owner={'cookie':'empire_admin=valid','origin':'https://empire.test'}
                    self.assertEqual((await c.get('/api/conversations')).status_code,401)
                    self.assertEqual((await c.post('/api/webhooks/wa-bridge-inbound',json=base,headers=internal)).status_code,200)
                    resp=await c.get('/api/conversations',headers=owner)
                    self.assertEqual(resp.json()['items'][0]['delivery_status'],'PREPARED')
                    payload={'phone_jid':jid,'message_id':'review-1','result':'SUBMITTED'}
                    self.assertEqual((await c.post('/api/internal/wa-delivery-status',json=payload)).status_code,403)
                    self.assertTrue((await c.post('/api/internal/wa-delivery-status',json=payload,headers=internal)).json()['updated'])
                    payload['result']='UNCERTAIN'
                    self.assertFalse((await c.post('/api/internal/wa-delivery-status',json=payload,headers=internal)).json()['updated'])
                    self.assertEqual((await c.get('/api/conversations',headers=owner)).json()['items'][0]['delivery_status'],'SUBMITTED')
                    base['message_id']='review-2'; base['message']='Quanto custa?'
                    await c.post('/api/webhooks/wa-bridge-inbound',json=base,headers=internal)
                    pending=(await c.get('/api/conversations?pending_only=true',headers=owner)).json()['items']
                    self.assertEqual(len(pending),1)
                    self.assertEqual(pending[0]['delivery_status'],'NO_AUTO_REPLY')
                    p=f"/api/conversations/{pending[0]['id']}/reviewed"
                    self.assertEqual((await c.post(p,headers={'cookie':'empire_admin=valid','origin':'https://evil.test'})).status_code,403)
                    self.assertEqual((await c.post(p,headers=owner)).json(),{'ok':True,'sent':False})
                    self.assertEqual((await c.get('/api/conversations?pending_only=true',headers=owner)).json()['items'],[])
        finally:
            main.app.dependency_overrides.clear()
    async def test_automatic_marketing_and_followups_off(self):
        async with self.sessions() as db:
            with unittest.mock.patch('packages.leads.auto_outreach.EvolutionWhatsAppManager.send_real_whatsapp',new=unittest.mock.AsyncMock()) as send:
                a=await AutonomousOutreachEngine.send_single_lead_now(db,'Empresa','5516999999999','oi')
                b=await AutonomousOutreachEngine.run_abandoned_pix_and_ghost_recovery(db)
                self.assertFalse(a['ok']); self.assertEqual(b['reason'],'FOLLOWUP_DISABLED')
                send.assert_not_awaited()

if __name__=='__main__': unittest.main()
