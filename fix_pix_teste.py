#!/usr/bin/env python3
"""Adiciona o Pix de teste (Sandbox) no painel e devolve o codigo copia e cola na API.

Uso: python3 fix_pix_teste.py   (executar na raiz do repositorio)
"""
from pathlib import Path

API = Path('apps/api-gateway/main.py')
APP = Path('apps/command-center/src/App.tsx')


def api():
    s = API.read_text(encoding='utf-8')
    if '"pix_copy_paste": inv.pix_copy_paste,\n        "pix_qr_svg": inv.pix_qr_svg,\n    }\n\n\n@app.post("/api/webhooks/payments/{invoice_id}/settle")' in s:
        print('api: ja aplicado')
        return
    velho = '    return {"ok": True, "invoice_id": inv.id}\n\n\n@app.post("/api/webhooks/payments/{invoice_id}/settle")'
    assert s.count(velho) == 1, 'trecho da API nao encontrado'
    novo = ('    return {\n        "ok": True,\n        "invoice_id": inv.id,\n'
            '        "pix_copy_paste": inv.pix_copy_paste,\n        "pix_qr_svg": inv.pix_qr_svg,\n    }\n\n\n'
            '@app.post("/api/webhooks/payments/{invoice_id}/settle")')
    API.write_text(s.replace(velho, novo, 1), encoding='utf-8')
    print('api: ok')


def app():
    s = APP.read_text(encoding='utf-8')
    if 'createSandboxTestPix' not in s:
        st = "  const [sandboxBusy, setSandboxBusy] = useState(false);"
        assert s.count(st) == 1, 'estado sandboxBusy nao encontrado'
        s = s.replace(st, st +
            "\n  const [sandboxPix, setSandboxPix] = useState<{ invoice_id: string; pix_copy_paste: string; pix_qr_svg: string } | null>(null);"
            "\n  const [sandboxPixBusy, setSandboxPixBusy] = useState(false);"
            "\n  const [sandboxPixError, setSandboxPixError] = useState<string | null>(null);", 1)
        fn = "  const copyText = (id: string, text: string) => {"
        assert s.count(fn) == 1, 'funcao copyText nao encontrada'
        nova = '''  const createSandboxTestPix = async () => {
    if (sandboxPixBusy) return;
    setSandboxPixBusy(true);
    setSandboxPixError(null);
    setSandboxPix(null);
    try {
      const res = await fetch('/api/payments/invoices', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: 'ASAAS_PIX',
          client_name: 'Teste Sandbox Empire',
          client_email: 'teste@sandbox.local',
          description: 'Teste de conciliacao Sandbox',
          amount_usd: 0.8849,
        }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        setSandboxPixError(json?.detail || 'Nao foi possivel gerar o Pix de teste no Sandbox.');
        return;
      }
      setSandboxPix({
        invoice_id: String(json.invoice_id || ''),
        pix_copy_paste: typeof json.pix_copy_paste === 'string' ? json.pix_copy_paste : '',
        pix_qr_svg: typeof json.pix_qr_svg === 'string' ? json.pix_qr_svg : '',
      });
    } catch {
      setSandboxPixError('Falha de rede ao criar o Pix de teste. Nada foi cobrado.');
    } finally {
      setSandboxPixBusy(false);
    }
  };

'''
        s = s.replace(fn, nova + fn, 1)
    if 'Gerar Pix de teste' not in s:
        anc = '                <p className="text-xs text-amber-300">Ambiente de teste. Verificar não marca pagamento como pago, não movimenta dinheiro e não libera produtos.</p>'
        assert s.count(anc) == 1, 'aviso do sandbox nao encontrado'
        bloco = anc + '''
                <div className="rounded-xl border border-slate-800 bg-slate-950 p-3 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-white">Pix de teste (R$ 5,00)</span>
                    <button
                      onClick={() => void createSandboxTestPix()}
                      disabled={sandboxPixBusy}
                      className="rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-bold text-slate-950 disabled:opacity-60"
                    >
                      {sandboxPixBusy ? 'Gerando...' : 'Gerar Pix de teste'}
                    </button>
                  </div>
                  {sandboxPixError && <p role="alert" className="text-xs text-rose-300">{sandboxPixError}</p>}
                  {sandboxPix && sandboxPix.pix_copy_paste && (
                    <div className="space-y-2">
                      <p className="text-[11px] text-slate-400 break-all">Fatura: {sandboxPix.invoice_id}</p>
                      {sandboxPix.pix_qr_svg && (
                        <div
                          className="shrink-0"
                          dangerouslySetInnerHTML={{
                            __html: sandboxPix.pix_qr_svg
                              .replace('width="192"', 'width="144"')
                              .replace('height="192"', 'height="144"'),
                          }}
                        />
                      )}
                      <textarea
                        readOnly
                        value={sandboxPix.pix_copy_paste}
                        onClick={(e) => e.currentTarget.select()}
                        className="w-full h-20 rounded-lg bg-slate-900 border border-slate-700 p-2 text-[11px] font-mono text-slate-200"
                      />
                      <button
                        onClick={() => copyText('sandbox-pix', sandboxPix.pix_copy_paste)}
                        className="rounded-lg bg-slate-700 px-3 py-1.5 text-xs text-white"
                      >
                        {copiedId === 'sandbox-pix' ? 'Copiado!' : 'Copiar codigo Pix'}
                      </button>
                      <p className="text-[11px] text-slate-400">Pague este codigo em outra conta Sandbox para testar o recebimento. Nada e liquidado aqui.</p>
                    </div>
                  )}
                </div>'''
        s = s.replace(anc, bloco, 1)
    APP.write_text(s, encoding='utf-8')
    print('app: ok')


if __name__ == '__main__':
    api()
    app()
    print('Pronto. Depois rode: cd apps/command-center && npm run build')
