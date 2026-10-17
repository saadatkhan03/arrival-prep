import unittest,sys,threading,json,urllib.request,urllib.error,os,tempfile
import auth_store
from pathlib import Path
from unittest.mock import patch
from io import BytesIO
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Handler,TOKEN,ThreadingHTTPServer
class HTTPTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.old_db=auth_store.DB_PATH;cls.tmp=tempfile.TemporaryDirectory();auth_store.DB_PATH=Path(cls.tmp.name)/'test.sqlite3';auth_store.init();cls.uid=auth_store.create_user('http@example.test','HttpExamplePass123!')['id'];auth_store.approve_order(auth_store.create_order(cls.uid));cls.auth=auth_store.login('http@example.test','HttpExamplePass123!')[0]
  cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);cls.port=cls.server.server_port;cls.base=f'http://127.0.0.1:{cls.port}';cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();auth_store.DB_PATH=cls.old_db;cls.tmp.cleanup()
 def req(self,path,body=None,extra=None):
  headers={'Content-Type':'application/json','Origin':self.base,'X-Session-Token':TOKEN,'X-Auth-Token':self.auth};headers.update(extra or {})
  req=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
  try:
   with urllib.request.urlopen(req) as r:return r.status,r.read(),r.headers
  except urllib.error.HTTPError as e:return e.code,e.read(),e.headers
 def test_security_headers(self):
  code,body,h=self.req('/');self.assertEqual(code,200);self.assertEqual(h['Cache-Control'],'no-store');self.assertIn("frame-ancestors 'none'",h['Content-Security-Policy'])
 def test_no_source_access(self):self.assertEqual(self.req('/../sources/private-reference.pdf')[0],404)
 def test_bad_origin(self):self.assertEqual(self.req('/api/validate',{'data':{}},{'Origin':'https://evil.example'})[0],403)
 def test_bad_token(self):self.assertEqual(self.req('/api/validate',{'data':{}},{'X-Session-Token':'bad'})[0],403)
 def test_bad_host(self):self.assertEqual(self.req('/',extra={'Host':'evil.example'})[0],403)
 def test_validation(self):self.assertEqual(self.req('/api/validate',{'data':{'version':1,'sections':{}}})[0],200)
 def test_review_requires_identity(self):self.assertEqual(self.req('/api/pdf',{'data':{'version':1,'sections':{}},'attested':True,'reviewDate':'2026-10-16'})[0],400)
 def test_ai_consent(self):self.assertEqual(self.req('/api/ai',{'consent':False,'section':'insurance','answer':{}})[0],400)
 def test_ai_disabled(self):
  with patch.dict(os.environ,{'OPENAI_API_KEY':'','OPENAI_MODEL':''}):self.assertEqual(self.req('/api/ai',{'consent':True,'section':'insurance','answer':{}})[0],503)
 def test_ai_payload_contract(self):
  # Invoke handler method directly, mocking provider transport. No remote request.
  handler=object.__new__(Handler);handler.user=lambda:{'id':self.uid};captured={};handler.send=lambda status,body,ctype=None:(status,body)
  def fake(req,timeout):
   captured.update(json.loads(req.data));return BytesIO(json.dumps({'output':[{'content':[{'type':'output_text','text':'What is the date of the quote?'}]}]}).encode())
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','OPENAI_MODEL':'configured-model'}),patch('server.urllib.request.urlopen',side_effect=fake):
   status,body=handler.ai({'consent':True,'section':'insurance','answer':{'status':'Inquiry sent; quote pending'}})
  self.assertEqual(status,200);self.assertIn('date',body['question']);self.assertFalse(captured['store']);self.assertEqual(captured['model'],'configured-model');self.assertNotIn('funds',captured['input'])

 def test_cookie_session_is_httponly_and_has_no_bearer_in_json(self):
  status,body,headers=self.req('/api/auth/login',{'email':'http@example.test','password':'HttpExamplePass123!'}, {'X-Auth-Token':''})
  self.assertEqual(status,200);self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('SameSite=Strict',headers['Set-Cookie']);self.assertNotIn('token',json.loads(body))
  cookie=headers['Set-Cookie'].split(';')[0];status,body,_=self.req('/api/me',extra={'X-Auth-Token':'','Cookie':cookie});self.assertEqual(json.loads(body)['user']['id'],self.uid)
  self.assertEqual(self.req('/api/auth/logout',{}, {'X-Auth-Token':'','Cookie':cookie})[0],200)
  self.assertIsNone(json.loads(self.req('/api/me',extra={'X-Auth-Token':'','Cookie':cookie})[1])['user'])
 def test_private_assets_never_served(self):
  for path in ['/private/visaready.sqlite3','/.env','/auth_store.py','/sample-profile.json','/docs/schema.json']:
   self.assertEqual(self.req(path)[0],404,path)
 def test_polish_rejects_reversed_negation(self):
  handler=object.__new__(Handler);handler.user=lambda:{'id':self.uid};handler.send=lambda status,body,ctype=None:(status,body)
  def fake(req,timeout):return BytesIO(json.dumps({'output':[{'content':[{'type':'output_text','text':'I have received an offer. My savings are USD 12000.'}]}]}).encode())
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test','OPENAI_MODEL':'model'}),patch('server.urllib.request.urlopen',side_effect=fake):
   with self.assertRaisesRegex(ValueError,'protected'):handler.polish({'text':'I have not received an offer. My savings are USD 12000.','mode':'ai','consent':True})
