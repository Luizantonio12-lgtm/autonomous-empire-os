import os,sys,unittest
from pathlib import Path
from unittest.mock import patch
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'apps/api-gateway')]
os.environ['DATABASE_URL']='sqlite+aiosqlite:///:memory:'
import main
class TestOpportunities(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='https://empire.test')
 async def asyncTearDown(self):await self.client.aclose()
 async def test_private(self):
  for path in ['/api/opportunities','/api/opportunities/view']:self.assertEqual((await self.client.get(path)).status_code,401)
 async def test_list(self):
  with patch('main.valid_session',return_value=True):
   r=await self.client.get('/api/opportunities');self.assertEqual(r.status_code,200);data=r.json();self.assertEqual(len(data['records']),6);self.assertFalse(data['outbound_enabled']);self.assertFalse(data['automated_search'])
 async def test_view(self):
  with patch('main.valid_session',return_value=True):
   r=await self.client.get('/api/opportunities/view');self.assertEqual(r.status_code,200);self.assertIn("fetch('/api/opportunities'",r.text)
 async def test_no_write(self):
  with patch('main.valid_session',return_value=True):
   r=await self.client.post('/api/opportunities',headers={'origin':'https://empire.test'},json={});self.assertEqual(r.status_code,405)
