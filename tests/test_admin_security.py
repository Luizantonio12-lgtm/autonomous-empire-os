"""Homologação simulada; sem acesso a serviços externos."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock
import httpx
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'apps' / 'api-gateway')]
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
import main
from packages.security import session_controls


class TestApiProtection(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='https://empire.test')
    async def asyncTearDown(self):
        await self.client.aclose()
        main.app.dependency_overrides.clear()
        main._LOGIN_ATTEMPTS.clear()
    async def test_public_health_and_private_resources(self):
        self.assertEqual((await self.client.get('/api/health')).status_code, 200)
        for path in ['/api/dashboard/overview','/api/leads/campaign-status','/api/system/export-monorepo.zip','/api/factory/builds/foo']:
            self.assertEqual((await self.client.get(path)).status_code, 401, path)
        for path in ['/api/vault/secret','/api/leads/autopilot-toggle','/api/webhooks/payments/inv-1/settle','/api/onboarding/configure']:
            self.assertEqual((await self.client.post(path, json={})).status_code, 401, path)
    async def test_internal_secret_required_even_with_loopback(self):
        with patch.dict(os.environ, {'WA_INTERNAL_SECRET': 'x'*64}):
            self.assertEqual((await self.client.get('/api/internal/wa-auth-restore')).status_code, 403)
            self.assertEqual((await self.client.post('/api/webhooks/wa-bridge-inbound',json={})).status_code, 403)
            self.assertFalse(session_controls.valid_internal_secret('bad'))
            self.assertTrue(session_controls.valid_internal_secret('x'*64))
    async def test_missing_origin_rejected_before_login(self):
        self.assertEqual((await self.client.post('/api/security/login',json={})).status_code, 403)
        self.assertEqual((await self.client.post('/api/security/login',headers={'origin':'https://evil.test'},json={})).status_code, 403)
    async def test_no_default_credentials(self):
        with patch.dict(os.environ, {'EMPIRE_CEO_PASSWORD':'empire2026','EMPIRE_JWT_SECRET':'x'*40,'EMPIRE_TOTP_SECRET':'JBSWY3DPEHPK3PXP'}):
            self.assertFalse(session_controls.secure_credentials_configured())
            res=await self.client.post('/api/security/login',headers={'origin':'https://empire.test'},json={'password':'test','totp_code':'123456'})
            self.assertEqual(res.status_code,503)
    async def test_cookie_login_and_csrf(self):
        async def fake_db():
            yield object()
        main.app.dependency_overrides[main.get_db] = fake_db
        with patch('main.secure_credentials_configured',return_value=True), \
             patch('main.valid_session',side_effect=lambda x: x=='secret-token'), \
             patch.object(main.SovereignSecurityGuard,'authenticate_ceo',new=AsyncMock(return_value={'token':'secret-token','role':'EMPIRE_OWNER'})):
            login=await self.client.post('/api/security/login',headers={'origin':'https://empire.test'},json={'password':'a','totp_code':'123456'})
            self.assertEqual(login.status_code,200)
            self.assertNotIn('token',login.json())
            cookie=login.headers['set-cookie'].lower()
            self.assertIn('httponly',cookie)
            self.assertIn('secure',cookie)
            self.assertIn('samesite=strict',cookie)
            self.assertEqual((await self.client.post('/api/security/logout',headers={'origin':'https://evil.test'})).status_code,403)
            self.assertEqual((await self.client.post('/api/security/logout',headers={'origin':'https://empire.test'})).status_code,200)
            self.assertEqual((await self.client.post('/api/security/logout',headers={'origin':'https://empire.test'})).status_code,401)
    async def test_real_totp_and_session_against_api(self):
        import base64, hashlib
        password='stage-only-password-not-production'
        jwt='stage-jwt-secret-not-used-in-production-12345'
        totp=base64.b32encode(b'testing-2fa-secret-20-bytes').decode()
        async def fake_db():
            yield object()
        main.app.dependency_overrides[main.get_db] = fake_db
        with patch.dict(os.environ, {'EMPIRE_CEO_PASSWORD':password,'EMPIRE_JWT_SECRET':jwt,'EMPIRE_TOTP_SECRET':totp}), \
             patch.object(main.SovereignSecurityGuard,'_ceo_password_hash',hashlib.sha256(password.encode()).hexdigest()), \
             patch.object(main.SovereignSecurityGuard,'_jwt_secret',jwt), \
             patch.object(main.SovereignSecurityGuard,'_totp_secret_b32',totp), \
             patch.object(main.SovereignSecurityGuard,'log_audit',new=AsyncMock()), \
             patch('packages.security.auth_guard.event_bus.publish',new=AsyncMock()):
            h={'origin':'https://empire.test'}
            bad=await self.client.post('/api/security/login',headers=h,json={'password':password,'totp_code':'not-a-valid-code'})
            self.assertEqual(bad.status_code,401)
            good=await self.client.post('/api/security/login',headers=h,json={'password':password,'totp_code':main.SovereignSecurityGuard.generate_totp()})
            self.assertEqual(good.status_code,200)
            self.assertEqual((await self.client.get('/api/leads/campaign-status')).status_code,200)
            self.assertEqual((await self.client.post('/api/security/logout',headers=h)).status_code,200)
            self.assertEqual((await self.client.get('/api/leads/campaign-status')).status_code,401)
    async def test_paid_webhook_is_not_processed(self):
        async def fake_db():
            yield object()
        main.app.dependency_overrides[main.get_db] = fake_db
        self.assertEqual((await self.client.post('/api/webhooks/asaas',json={'event':'PAYMENT_RECEIVED'})).status_code,503)


class TestTelemetry(unittest.TestCase):
    def test_websocket_requires_cookie_and_same_origin(self):
        from fastapi.testclient import TestClient
        from starlette.websockets import WebSocketDisconnect
        client = TestClient(main.app, base_url='https://empire.test')
        with patch('main.valid_session', side_effect=lambda value: value == 'valid'):
            with self.assertRaises(WebSocketDisconnect):
                with client.websocket_connect('wss://empire.test/ws/telemetry', headers={'origin':'https://empire.test'}):
                    pass
            with self.assertRaises(WebSocketDisconnect):
                with client.websocket_connect('wss://empire.test/ws/telemetry', headers={'origin':'https://evil.test', 'cookie':'empire_admin=valid'}):
                    pass
            with client.websocket_connect('wss://empire.test/ws/telemetry', headers={'origin':'https://empire.test', 'cookie':'empire_admin=valid'}) as ws:
                self.assertEqual(ws.receive_json()['type'], 'SNAPSHOT')


if __name__ == '__main__':
    unittest.main()
