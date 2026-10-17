"""Exercise access boundaries through real request handlers, without a network listener."""
import sys,unittest,tempfile,json,io,os
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import auth_store
from server import Handler,TOKEN
class AccessTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=auth_store.DB_PATH;auth_store.DB_PATH=Path(self.tmp.name)/'accounts.sqlite3';auth_store.init()
  self.free=auth_store.create_user('free@example.test','ExamplePass123!')['id'];self.paid=auth_store.create_user('paid@example.test','ExamplePass123!')['id']
  auth_store.approve_order(auth_store.create_order(self.paid));self.ft=auth_store.login('free@example.test','ExamplePass123!')[0];self.pt=auth_store.login('paid@example.test','ExamplePass123!')[0]
 def tearDown(self):auth_store.DB_PATH=self.old;self.tmp.cleanup()
 def request(self,path,token='',body=None):
  h=Handler.__new__(Handler);h.path=path;h.server=SimpleNamespace(server_port=8898)
  h.headers={'Host':'127.0.0.1:8898','Origin':'http://127.0.0.1:8898','X-Session-Token':TOKEN,'X-Auth-Token':token,'Content-Type':'application/json'}
  h.send=lambda status,data,ctype='application/json':setattr(h,'result',(status,data))
  if body is None:h.do_GET()
  else:
   raw=json.dumps(body).encode();h.headers['Content-Length']=str(len(raw));h.rfile=io.BytesIO(raw);h.do_POST()
  return h.result
 def test_free_schema_hides_detailed_questions(self):
  for token in ['',self.ft]:
   status,data=self.request('/schema.json',token);self.assertEqual(status,200);self.assertEqual([x['id'] for x in data],['case','household','housing'])
 def test_paid_schema(self):self.assertEqual(len(self.request('/schema.json',self.pt)[1]),12)
 def test_forged_paid_plan_does_not_unlock_pdf(self):
  status,_=self.request('/api/pdf',self.ft,{'data':{'version':1,'sections':{}},'plan':'complete'});self.assertEqual(status,403)
 def test_paid_pdf(self):
  status,data=self.request('/api/pdf',self.pt,{'data':{'version':1,'sections':{}},'plan':'free'});self.assertEqual(status,200);self.assertTrue(data.startswith(b'%PDF'))
 def test_family_example_is_paid_and_separate(self):
  self.assertEqual(self.request('/api/example?profile=family',self.ft)[0],403);status,data=self.request('/api/example?profile=family',self.pt);self.assertEqual(status,200);self.assertTrue(data['sample']);self.assertTrue(data['sections']['case']['category'].startswith('IR1'))
 def test_free_example_denied(self):self.assertEqual(self.request('/api/example',self.ft)[0],403)
 def test_free_detailed_validation_denied(self):
  status,_=self.request('/api/validate',self.ft,{'data':{'version':1,'sections':{'assets':{'debts':'No loans reported'}}}});self.assertEqual(status,403)
 def test_wording_preserves_numbers(self):
  status,data=self.request('/api/polish',self.pt,{'text':' i  have  USD 12000 .','mode':'basic'});self.assertEqual(status,200);self.assertEqual(data['suggestion'],'I have USD 12000.')
 def test_free_wording_denied(self):self.assertEqual(self.request('/api/polish',self.ft,{'text':' i have savings','mode':'basic'})[0],403)
if __name__=='__main__':unittest.main()
