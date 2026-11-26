import os,sys,unittest
from pathlib import Path
from unittest.mock import patch,AsyncMock,Mock
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'apps/api-gateway')]
os.environ['DATABASE_URL']='sqlite+aiosqlite:///:memory:'
import main
class TestBackgroundOptIn(unittest.IsolatedAsyncioTestCase):
 async def check(self,value,enabled):
  with patch.dict(os.environ,{},clear=False),patch('main.run_seed',new=AsyncMock()),patch.object(main.AutonomousSchedulerDaemon,'start_background_worker',new=Mock()) as scheduler,patch.object(main.AutonomousOutreachEngine,'start_autopilot_daemon',new=Mock()) as outreach:
   os.environ.pop('EMPIRE_BACKGROUND_WORKERS_ENABLED',None)
   if value is not None:os.environ['EMPIRE_BACKGROUND_WORKERS_ENABLED']=value
   await main._boot_seed_and_daemons()
   self.assertEqual(scheduler.called,enabled);self.assertEqual(outreach.called,enabled)
 async def test_missing_off(self):await self.check(None,False)
 async def test_false_off(self):await self.check('false',False)
 async def test_invalid_off(self):await self.check('yes',False)
 async def test_explicit_optin(self):await self.check('true',True)
