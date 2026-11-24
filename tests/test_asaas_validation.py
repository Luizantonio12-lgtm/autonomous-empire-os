"""Validação offline; sem conexão ao Asaas, banco ou webhook real."""
import unittest
from decimal import Decimal
from types import SimpleNamespace
from packages.payments.asaas_validation import valid_webhook_token, verify_static_pix


class VerifyAsaas(unittest.TestCase):
    def setUp(self):
        self.event = {'id':'evt_1','event':'PAYMENT_RECEIVED','payment':{'id':'pay_1'}}
        self.payment = {'id':'pay_1','status':'RECEIVED','billingType':'PIX','pixQrCodeId':'real-qr-id','value':49.90}
        self.invoice = SimpleNamespace(external_id='real-qr-id',expected_amount_brl=Decimal('49.90'))
    def check(self):
        return verify_static_pix(self.event, self.payment, self.invoice)[0]
    def test_valid(self):
        self.assertTrue(self.check())
    def test_token(self):
        self.assertFalse(valid_webhook_token('', ''))
        self.assertFalse(valid_webhook_token('secret', 'incorrect'))
        self.assertTrue(valid_webhook_token('secret', 'secret'))
    def test_wrong_payment(self):
        self.payment['id'] = 'pay_2'
        self.assertFalse(self.check())
    def test_wrong_qr(self):
        self.payment['pixQrCodeId'] = 'other-qr'
        self.assertFalse(self.check())
    def test_unpaid(self):
        self.payment['status'] = 'PENDING'
        self.assertFalse(self.check())
    def test_wrong_amount(self):
        self.payment['value'] = '49.89'
        self.assertFalse(self.check())
    def test_legacy_without_exact_brl(self):
        del self.invoice.expected_amount_brl
        self.assertFalse(self.check())
    def test_synthetic_qr(self):
        self.invoice.external_id = 'ext_1234'
        self.payment['pixQrCodeId'] = 'ext_1234'
        self.assertFalse(self.check())
    def test_nan(self):
        self.payment['value'] = 'NaN'
        self.assertFalse(self.check())
    def test_event_not_received(self):
        self.event['event'] = 'PAYMENT_CONFIRMED'
        self.assertFalse(self.check())
    def test_missing_event_id(self):
        del self.event['id']
        self.assertFalse(self.check())

if __name__ == '__main__':
    unittest.main()
