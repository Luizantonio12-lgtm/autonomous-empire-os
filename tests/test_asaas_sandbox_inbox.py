"""Inbox sandbox testada em SQLite e respostas Asaas simuladas; sem rede."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'apps' / 'api-gateway')]
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
import main
from packages.database.models import Base, AsaasWebhookInbox, PaymentInvoice, PixInvoiceExpectation
from packages.payments.asaas_sandbox_inbox import verify_received_event

TOKEN='qwerty1234-sandbox-secret-ABCDE-6789abcdef'
ENV={'ASAAS_SANDBOX_INBOX_ENABLED':'true','ASAAS_BASE_URL':'https://api-sandbox.asaas.com/v3','ASAAS_WEBHOOK_TOKEN':TOKEN}


class TestSandboxInbox(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine=create_async_engine('sqlite+aiosqlite:///:memory:')
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.sessions=async_sessionmaker(self.engine,expire_on_commit=False)
        async def fake_db():
            async with self.sessions() as db:
                yield db
        main.app.dependency_overrides[main.get_db]=fake_db
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='https://empire.test')
        self.env=patch.dict(os.environ,ENV)
        self.env.start()
        self.vault=patch('main.ConfigVault.get_secret',new=AsyncMock(return_value='sandbox-api-key'))
        self.vault.start()
    async def asyncTearDown(self):
        self.vault.stop(); self.env.stop()
        main.app.dependency_overrides.clear()
        await self.client.aclose(); await self.engine.dispose()
    def headers(self):
        return {'asaas-access-token':TOKEN}
    def event(self):
        return {'id':'evt_1','event':'PAYMENT_RECEIVED','payment':{'id':'pay_1','value':49.90}}
    async def test_auth_and_exactly_once_recording(self):
        self.assertEqual((await self.client.post('/api/webhooks/asaas',json=self.event())).status_code,401)
        r=await self.client.post('/api/webhooks/asaas',headers=self.headers(),json=self.event())
        self.assertEqual(r.status_code,200); self.assertEqual(r.json(),{'ok':True,'recorded':True,'settled':False})
        r=await self.client.post('/api/webhooks/asaas',headers=self.headers(),json=self.event())
        self.assertEqual(r.status_code,200); self.assertFalse(r.json()['recorded'])
        async with self.sessions() as db:
            events=(await db.execute(select(AsaasWebhookInbox))).scalars().all()
            self.assertEqual(len(events),1); self.assertEqual(events[0].status,'PENDING_REVIEW')
    async def test_duplicate_id_different_payment_rejected(self):
        await self.client.post('/api/webhooks/asaas',headers=self.headers(),json=self.event())
        altered=self.event(); altered['payment']['id']='pay_other'
        self.assertEqual((await self.client.post('/api/webhooks/asaas',headers=self.headers(),json=altered)).status_code,400)
    async def test_bad_event_and_big_body_rejected(self):
        self.assertEqual((await self.client.post('/api/webhooks/asaas',headers=self.headers(),json={'id':'../../x','event':'PAYMENT_RECEIVED'})).status_code,400)
        self.assertEqual((await self.client.post('/api/webhooks/asaas',headers=self.headers(),content=b'x'*65537)).status_code,413)
    async def test_sandbox_only(self):
        with patch.dict(os.environ,{'ASAAS_BASE_URL':'https://api.asaas.com/v3'}):
            self.assertEqual((await self.client.post('/api/webhooks/asaas',headers=self.headers(),json=self.event())).status_code,503)
    async def test_automatic_check_is_admin_only_and_never_settles(self):
        await self.client.post('/api/webhooks/asaas',headers=self.headers(),json=self.event())
        self.assertEqual((await self.client.get('/api/payments/asaas-inbox')).status_code,401)
        self.assertEqual((await self.client.post('/api/payments/asaas-inbox/evt_1/verify')).status_code,401)
        async with self.sessions() as db:
            db.add(PaymentInvoice(id='inv-1',provider='ASAAS_PIX',external_id='qr-1',client_name='Teste',client_email='x@example.com',description='Teste',amount_usd=8.8319,status='PENDING'))
            db.add(PixInvoiceExpectation(invoice_id='inv-1',amount_brl_cents=4990))
            await db.commit()
        class Resp:
            def raise_for_status(self): pass
            def json(self): return {'id':'pay_1','status':'RECEIVED','billingType':'PIX','pixQrCodeId':'qr-1','value':49.90}
        class FakeRemote:
            def __init__(self,*args,**kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self,*args): pass
            async def get(self,url,**kwargs): return Resp()
        owner={'origin':'https://empire.test','cookie':'empire_admin=valid'}
        with patch('main.valid_session',side_effect=lambda value: value=='valid'):
            lst=await self.client.get('/api/payments/asaas-inbox',headers=owner)
            self.assertTrue(lst.json()['sandbox_only'])
            self.assertEqual(lst.json()['items'][0]['status'],'PENDING_REVIEW')
            bad=await self.client.post('/api/payments/asaas-inbox/evt_1/verify',headers={'origin':'https://evil.test','cookie':'empire_admin=valid'})
            self.assertEqual(bad.status_code,403)
            with patch('packages.payments.asaas_sandbox_inbox.httpx.AsyncClient',FakeRemote):
                ok=await self.client.post('/api/payments/asaas-inbox/evt_1/verify',headers=owner)
            self.assertEqual(ok.json()['status'],'VERIFIED_NOT_SETTLED')
            self.assertEqual((await self.client.get('/api/payments/asaas-inbox',headers=owner)).json()['items'][0]['status'],'VERIFIED_NOT_SETTLED')
        async with self.sessions() as db:
            self.assertEqual((await db.get(PaymentInvoice,'inv-1')).status,'PENDING')
    async def test_real_invoice_creation_blocked_in_this_branch(self):
        from packages.payments.gateways import PaymentGatewayManager, PaymentGatewayUnavailable
        with patch.dict(os.environ,{'ASAAS_BASE_URL':'https://api.asaas.com/v3'}):
            async with self.sessions() as db:
                with self.assertRaises(PaymentGatewayUnavailable):
                    await PaymentGatewayManager.create_invoice(db,'ASAAS_PIX','Teste','x@example.com','Teste',8.8319)
                self.assertEqual((await db.execute(select(PaymentInvoice))).scalars().all(),[])
    async def test_new_invoice_records_exact_cents_and_one_payment(self):
        from packages.payments.gateways import PaymentGatewayManager
        class Resp:
            status_code=200
            def __init__(self,body): self.body=body
            def json(self): return self.body
        class FakeRemote:
            def __init__(self,*args,**kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self,*args): pass
            async def get(self,url,**kwargs):
                return Resp({'data':[{'status':'ACTIVE','key':'sandbox-key'}]})
            async def post(self,url,**kwargs):
                self_test=kwargs['json']
                assert self_test['value'] == 49.90
                assert self_test['allowsMultiplePayments'] is False
                return Resp({'id':'qr-test','payload':'sandbox-pix-payload'})
        async with self.sessions() as db:
            with patch('packages.payments.gateways.httpx.AsyncClient',FakeRemote), patch('packages.payments.gateways.event_bus.publish',new=AsyncMock()):
                inv=await PaymentGatewayManager.create_invoice(db,'ASAAS_PIX','Teste','x@example.com','Teste',8.8319)
            expected=await db.get(PixInvoiceExpectation,inv.id)
            self.assertEqual(expected.amount_brl_cents,4990)
            self.assertEqual(inv.status,'PENDING')
    async def test_verified_never_marks_invoice_paid(self):
        async with self.sessions() as db:
            db.add(PaymentInvoice(id='inv-1',provider='ASAAS_PIX',external_id='qr-1',client_name='Teste',client_email='x@example.com',description='Teste',amount_usd=8.8319,status='PENDING'))
            db.add(PixInvoiceExpectation(invoice_id='inv-1',amount_brl_cents=4990))
            await db.commit()
        await self.client.post('/api/webhooks/asaas',headers=self.headers(),json=self.event())
        class Resp:
            def raise_for_status(self): pass
            def json(self): return {'id':'pay_1','status':'RECEIVED','billingType':'PIX','pixQrCodeId':'qr-1','value':49.90}
        class FakeRemote:
            def __init__(self,*args,**kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self,*args): pass
            async def get(self,url,**kwargs):
                assert url == 'https://api-sandbox.asaas.com/v3/payments/pay_1'
                return Resp()
        async with self.sessions() as db:
            with patch('packages.payments.asaas_sandbox_inbox.httpx.AsyncClient',FakeRemote):
                result=await verify_received_event(db,'evt_1')
            self.assertEqual(result['status'],'VERIFIED_NOT_SETTLED')
            self.assertEqual(result['invoice_id'],'inv-1')
            self.assertEqual((await db.get(PaymentInvoice,'inv-1')).status,'PENDING')

    async def test_official_event_id_with_ampersand_is_accepted_idempotently(self):
        body={'id':'evt_05b708f961d739ea7eba7e4db318f621&368604920','event':'PAYMENT_RECEIVED','payment':{'object':'payment','id':'pay_080225913252'}}
        r=await self.client.post('/api/webhooks/asaas',headers=self.headers(),json=body)
        self.assertEqual(r.status_code,200); self.assertTrue(r.json()['recorded'])
        r=await self.client.post('/api/webhooks/asaas',headers=self.headers(),json=body)
        self.assertEqual(r.status_code,200); self.assertFalse(r.json()['recorded'])

if __name__ == '__main__': unittest.main()
