"""Testes locais isolados: nenhuma rede, Asaas, Neon ou WhatsApp real."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'apps' / 'api-gateway')]
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
import main
from packages.payments.gateways import PaymentGatewayManager, PaymentGatewayUnavailable
from packages.security.auth_guard import SovereignSecurityGuard


class FakeDB:
    def __init__(self):
        self.objects = []
        self.commits = 0
    def add(self, obj):
        self.objects.append(obj)
    async def commit(self):
        self.commits += 1


class FakeResponse:
    def __init__(self, body):
        self.status_code = 200
        self.body = body
    def json(self):
        return self.body


class FakeAsaas:
    def __init__(self, *args, **kwargs):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        return False
    async def get(self, url, **kw):
        return FakeResponse({'data': [{'status': 'ACTIVE', 'key': 'test-key'}]})
    async def post(self, url, **kw):
        assert kw['json']['value'] == 49.90
        return FakeResponse({'id': 'qr-test', 'payload': 'real-provider-payload'})


class HardeningTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_fake_pix_or_database_invoice(self):
        db = FakeDB()
        with patch('packages.payments.gateways.ConfigVault.get_secret', new=AsyncMock(return_value='')):
            with self.assertRaises(PaymentGatewayUnavailable):
                await PaymentGatewayManager.create_invoice(db, 'ASAAS_PIX', 'Teste', 'x@example.com', 'Teste', 8.8319)
        self.assertEqual(db.objects, [])
        self.assertEqual(db.commits, 0)

    async def test_provider_payload_without_image_is_not_fake_qr(self):
        db = FakeDB()
        with patch.dict(os.environ, {'ASAAS_SANDBOX_INBOX_ENABLED': 'true', 'ASAAS_BASE_URL': 'https://api-sandbox.asaas.com/v3'}), \
             patch('packages.payments.gateways.ConfigVault.get_secret', new=AsyncMock(return_value='test')), \
             patch('packages.payments.gateways.httpx.AsyncClient', FakeAsaas), \
             patch('packages.payments.gateways.event_bus.publish', new=AsyncMock()):
            inv = await PaymentGatewayManager.create_invoice(db, 'ASAAS_PIX', 'Teste', 'x@example.com', 'Teste', 8.8319)
        self.assertEqual(inv.pix_copy_paste, 'real-provider-payload')
        self.assertIsNone(inv.pix_qr_svg)
        self.assertEqual(inv.amount_usd, 8.8319)
        self.assertEqual(db.commits, 1)

    async def test_fake_stripe_link_not_created(self):
        db = FakeDB()
        with patch('packages.payments.gateways.ConfigVault.get_secret', new=AsyncMock(return_value='')):
            with self.assertRaises(PaymentGatewayUnavailable):
                await PaymentGatewayManager.create_invoice(db, 'STRIPE', 'Teste', 'x@example.com', 'Teste', 10)
        self.assertFalse(db.objects)

    async def test_webhooks_fail_closed(self):
        async def fake_db():
            yield FakeDB()
        main.app.dependency_overrides[main.get_db] = fake_db
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
                r = await client.post('/api/webhooks/payments/inv-demo/settle')
                self.assertEqual(r.status_code, 401)
                r = await client.post('/api/webhooks/asaas', json={'event':'PAYMENT_RECEIVED', 'payment':{'id':'fake'}})
                self.assertEqual(r.status_code, 503)
        finally:
            main.app.dependency_overrides.clear()

    async def test_no_totp_secret_in_overview(self):
        info = SovereignSecurityGuard.get_security_overview()
        for key in ('totp_secret_b32', 'otpauth_uri', 'current_totp_demo', 'default_password_hint', 'totp_qr_svg'):
            self.assertNotIn(key, info)


if __name__ == '__main__':
    unittest.main()
