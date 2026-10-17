import unittest,tempfile,os,json
from pathlib import Path
from unittest.mock import patch
import auth_store as s
import services
class ServiceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=s.DB_PATH;s.DB_PATH=Path(self.tmp.name)/'db.sqlite3';s.init();self.uid=s.create_user('buyer@example.test','BuyerPassword123!')['id'];self.app=s.applications(self.uid)[0]['id'];self.order=s.create_order(self.uid);s.attach_provider(self.order,'PROVIDER123');self.env=patch.dict(os.environ,{'PAYPAL_MERCHANT_ID':'MERCHANT','PAYPAL_CLIENT_ID':'test','PAYPAL_CLIENT_SECRET':'test','PAYPAL_WEBHOOK_ID':'test'});self.env.start()
 def tearDown(self):self.env.stop();s.DB_PATH=self.old;self.tmp.cleanup()
 def response(self):return {'id':'PROVIDER123','status':'COMPLETED','purchase_units':[{'reference_id':str(self.order),'custom_id':str(self.app),'payee':{'merchant_id':'MERCHANT'},'payments':{'captures':[{'id':'CAPTURE123','status':'COMPLETED','amount':{'currency_code':'USD','value':'5.00'}}]}}]}
 def test_verified_payment_grants_only_owned_application(self):
  r=self.response();services.verify_completed(s.get_order(self.order),r,'event-a');self.assertTrue(s.has_complete(self.uid,self.app));self.assertFalse(services.verify_completed(s.get_order(self.order),r,'event-a'))
 def test_wrong_amount_and_payee_rejected(self):
  for kind in ('amount','merchant'):
   r=self.response()
   if kind=='amount':r['purchase_units'][0]['payments']['captures'][0]['amount']['value']='0.05'
   else:r['purchase_units'][0]['payee']['merchant_id']='WRONG'
   with self.assertRaises(ValueError):services.verify_completed(s.get_order(self.order),r,'bad-'+kind)
  self.assertFalse(s.has_complete(self.uid,self.app))
 def test_missing_webhook_signature_rejected_without_transport(self):
  with patch('services.paypal_token') as token:
   with self.assertRaises(PermissionError):services.webhook({}, {'id':'event'})
   token.assert_not_called()
 def test_invalid_webhook_signature_rejected(self):
  headers={x:'test' for x in ['PAYPAL-AUTH-ALGO','PAYPAL-CERT-URL','PAYPAL-TRANSMISSION-ID','PAYPAL-TRANSMISSION-SIG','PAYPAL-TRANSMISSION-TIME']}
  with patch('services.paypal_token',return_value='token'),patch('services._json_request',return_value={'verification_status':'FAILURE'}):
   with self.assertRaises(PermissionError):services.webhook(headers,{'id':'bad'})
 def test_local_email_link_is_private(self):
  with patch.dict(os.environ,{'SMTP_HOST':'','VISA_ENV':'development'}):mode=services.send_account_link('buyer@example.test','verify','secret-test','http://127.0.0.1:8898')
  files=list((s.DB_PATH.parent/'mail-preview').glob('*.json'));self.assertEqual(mode,'local-preview');self.assertEqual(len(files),1);self.assertEqual(files[0].stat().st_mode&0o777,0o600)
if __name__=='__main__':unittest.main()

class RefundLinkTests(unittest.TestCase):
 def test_refund_link_reconciles_completed_capture(self):
  with tempfile.TemporaryDirectory() as tmp:
   old=s.DB_PATH;s.DB_PATH=Path(tmp)/'db.sqlite3'
   try:
    s.init();uid=s.create_user('refund@example.test','RefundPassword123!')['id'];order=s.create_order(uid);s.attach_provider(order,'ORDER123');s.transition_order(order,'paid',reference='CAPTURE123');self.assertTrue(s.has_complete(uid))
    headers={x:'test' for x in ['PAYPAL-AUTH-ALGO','PAYPAL-CERT-URL','PAYPAL-TRANSMISSION-ID','PAYPAL-TRANSMISSION-SIG','PAYPAL-TRANSMISSION-TIME']}
    event={'id':'REFUNDEVENT','event_type':'PAYMENT.CAPTURE.REFUNDED','resource':{'id':'REFUND123','links':[{'rel':'up','href':'https://api-m.sandbox.paypal.com/v2/payments/captures/CAPTURE123'}]}}
    with patch.dict(os.environ,{'PAYPAL_WEBHOOK_ID':'test'}),patch('services.paypal_ready',return_value=True),patch('services.paypal_token',return_value='token'),patch('services._json_request',return_value={'verification_status':'SUCCESS'}):services.webhook(headers,event)
    self.assertFalse(s.has_complete(uid))
   finally:s.DB_PATH=old
