#!/usr/bin/env python3
"""Faz o pagamento informar o motivo tecnico da recusa ao criar o Pix no Sandbox.

Uso: python3 fix_diag_pix.py   (na raiz do repositorio)
Sem segredos: apenas nomes de etapa e codigos HTTP.
"""
from pathlib import Path

P = Path('packages/payments/gateways.py')


def aplicar():
    s = P.read_text(encoding='utf-8')
    if 'pix_fail_reason' in s:
        print('ja aplicado')
        return

    alvo = '        if provider_clean == "STRIPE":'
    assert s.count(alvo) == 1, 'inicio do bloco nao encontrado'
    s = s.replace(alvo, '        pix_fail_reason = "etapa_desconhecida"\n' + alvo, 1)

    a = ('            if asaas_key:\n'
         '                try:')
    assert s.count(a) == 1, 'trecho da chave nao encontrado'
    s = s.replace(a,
                  '            if not asaas_key:\n'
                  '                pix_fail_reason = "chave_api_sandbox_ausente"\n' + a, 1)

    b = ('                        if keys_resp.status_code < 300:\n'
         '                            items = keys_resp.json().get("data", [])')
    assert s.count(b) == 1, 'trecho de listar chaves nao encontrado'
    s = s.replace(b,
                  '                        if keys_resp.status_code >= 300:\n'
                  '                            pix_fail_reason = f"listar_chaves_http_{keys_resp.status_code}"\n' + b, 1)

    c = ('                            if create_key_resp.status_code < 300:\n'
         '                                address_key = create_key_resp.json().get("key")')
    assert s.count(c) == 1, 'trecho de criar chave nao encontrado'
    s = s.replace(c,
                  '                            if create_key_resp.status_code >= 300:\n'
                  '                                pix_fail_reason = f"criar_chave_http_{create_key_resp.status_code}"\n' + c, 1)

    d = ('                        # 2. Gera QR Code Pix oficial escaneável em Reais (BRL)\n'
         '                        if address_key:')
    assert s.count(d) == 1, 'trecho do QR nao encontrado'
    s = s.replace(d,
                  '                        if not address_key and pix_fail_reason == "etapa_desconhecida":\n'
                  '                            pix_fail_reason = "sem_chave_pix_ativa"\n' + d, 1)

    e = ('                            if qr_resp.status_code < 300:\n'
         '                                qdata = qr_resp.json()')
    assert s.count(e) == 1, 'trecho de resposta do QR nao encontrado'
    s = s.replace(e,
                  '                            if qr_resp.status_code >= 300:\n'
                  '                                pix_fail_reason = f"criar_qrcode_http_{qr_resp.status_code}"\n' + e, 1)

    f = '                raise PaymentGatewayUnavailable("Não foi possível criar Pix real no Asaas.")'
    assert s.count(f) == 1, 'mensagem final nao encontrada'
    s = s.replace(f,
                  '                raise PaymentGatewayUnavailable(\n'
                  '                    f"Sandbox recusou a criação do Pix ({pix_fail_reason})."\n'
                  '                )', 1)

    P.write_text(s, encoding='utf-8')
    print('ok')


if __name__ == '__main__':
    aplicar()
    print('Pronto. Depois: git add -A && git commit && git push')
