#!/usr/bin/env python3
"""Faz o 503 devolver o motivo tecnico controlado (sem segredos).

Uso: python3 fix_motivo_503.py   (na raiz do repositorio)
"""
from pathlib import Path

P = Path('apps/api-gateway/main.py')

VELHO = '''async def payment_unavailable_handler(request: Request, exc: PaymentGatewayUnavailable):
    return JSONResponse(status_code=503, content={"ok": False, "detail": "Pagamento indisponível. Tente novamente mais tarde."})'''

NOVO = '''async def payment_unavailable_handler(request: Request, exc: PaymentGatewayUnavailable):
    # Repassa apenas o motivo tecnico controlado (nomes de etapa e codigos HTTP),
    # nunca chaves ou payloads. Mantem a negativa clara para o operador.
    motivo = str(exc).strip()[:160] or "Pagamento indisponível. Tente novamente mais tarde."
    return JSONResponse(status_code=503, content={"ok": False, "detail": motivo})'''


def aplicar() -> None:
    s = P.read_text(encoding='utf-8')
    if 'motivo = str(exc).strip()' in s:
        print('ja aplicado')
        return
    assert s.count(VELHO) == 1, 'trecho do handler nao encontrado'
    P.write_text(s.replace(VELHO, NOVO, 1), encoding='utf-8')
    print('ok')


if __name__ == '__main__':
    aplicar()
    print('Pronto. Depois: git add -A && git commit && git push')
