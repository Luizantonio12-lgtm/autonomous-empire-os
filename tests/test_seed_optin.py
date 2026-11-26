import os,sys,unittest
from pathlib import Path
from unittest.mock import patch,AsyncMock
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'apps/api-gateway')]
os.environ['DATABASE_URL']='sqlite+aiosqlite:///:memory:'
import main
class TestSeedOptIn(unittest.IsolatedAsyncioTestCase):
 async def check(self,value,enabled):
  with patch.dict(os.environ,{'EMPIRE_BACKGROUND_WORKERS_ENABLED':'false'}),patch('main.run_seed',new=AsyncMock()) as seed:
   os.environ.pop('EMPIRE_SEED_ENABLED',None)
   if value is not None:os.environ['EMPIRE_SEED_ENABLED']=value
   await main._boot_seed_and_daemons();self.assertEqual(seed.called,enabled)
 async def test_default(self):await self.check(None,False)
 async def test_false(self):await self.check('false',False)
 async def test_invalid(self):await self.check('yes',False)
 async def test_true(self):await self.check('true',True)
 async def test_no_exception_leak(self):
  with patch.dict(os.environ,{'EMPIRE_BACKGROUND_WORKERS_ENABLED':'false','EMPIRE_SEED_ENABLED':'true'}),patch('main.run_seed',new=AsyncMock(side_effect=RuntimeError('secret-example-do-not-log'))),patch('builtins.print') as output:
   await main._boot_seed_and_daemons();self.assertNotIn('secret-example-do-not-log',str(output.call_args_list))
