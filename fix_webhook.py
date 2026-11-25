import hashlib
from pathlib import Path
p=Path('packages/payments/asaas_sandbox_inbox.py');s=p.read_text(encoding='utf-8')
if 'stable_event_id' in s:
 print('ja corrigido')
else:
 s=s.replace('import os\nimport re\n','import hashlib\nimport os\nimport re\n',1)
 a="SAFE_ID = re.compile(r'^[A-Za-z0-9_-]{1,128}$')\n"
 assert a in s
 s=s.replace(a,a+"UNSAFE_CHARS = re.compile(r'[^A-Za-z0-9_-]')\n\n\ndef stable_event_id(raw_id):\n    if SAFE_ID.fullmatch(raw_id):\n        return raw_id\n    d = hashlib.sha256(raw_id.encode('utf-8','surrogatepass')).hexdigest()[:16]\n    b = UNSAFE_CHARS.sub('-', raw_id).strip('-') or 'evento'\n    return f'{b[:111]}-{d}'\n",1)
 o="    event_id, event_type = body.get('id'), body.get('event')\n    if not isinstance(event_id, str) or not SAFE_ID.fullmatch(event_id):\n        raise ValueError('Identificador de evento inválido')\n"
 assert o in s
 s=s.replace(o,"    raw_id, event_type = body.get('id'), body.get('event')\n    if not isinstance(raw_id, str) or not 1 <= len(raw_id) <= 256:\n        raise ValueError('Identificador de evento inválido')\n    event_id = stable_event_id(raw_id)\n",1)
 v="    if not SAFE_ID.fullmatch(event_id):\n        raise ValueError('Evento inválido')\n    event = await db.get(AsaasWebhookInbox, event_id)\n"
 assert v in s
 s=s.replace(v,"    if not isinstance(event_id, str) or not 1 <= len(event_id) <= 256:\n        raise ValueError('Evento inválido')\n    event = await db.get(AsaasWebhookInbox, stable_event_id(event_id))\n",1)
 p.write_text(s,encoding='utf-8')
 t=Path('tests/test_asaas_sandbox_inbox.py');q=t.read_text(encoding='utf-8')
 m="\n\nif __name__ == '__main__': unittest.main()"
 if 'ampersand' not in q and m in q:
  n="\n\n    async def test_official_event_id_with_ampersand_is_accepted_idempotently(self):\n        body={'id':'evt_05b708f961d739ea7eba7e4db318f621&368604920','event':'PAYMENT_RECEIVED','payment':{'object':'payment','id':'pay_080225913252'}}\n        r=await self.client.post('/api/webhooks/asaas',headers=self.headers(),json=body)\n        self.assertEqual(r.status_code,200); self.assertTrue(r.json()['recorded'])\n        r=await self.client.post('/api/webhooks/asaas',headers=self.headers(),json=body)\n        self.assertEqual(r.status_code,200); self.assertFalse(r.json()['recorded'])"
  t.write_text(q.replace(m,n+m,1),encoding='utf-8')
 print('corrigido')
