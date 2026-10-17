import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import auth_store as store
from model import validate
from review_engine import preparation_report,clean_ai_result
from server import Handler
class ReviewTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=store.DB_PATH;store.DB_PATH=Path(self.tmp.name)/'reviews.sqlite3';store.init();self.uid=store.create_user('review@example.test','ReviewPassword123!')['id'];self.app=store.applications(self.uid)[0]['id'];store.approve_order(store.create_order(self.uid,application_id=self.app))
 def tearDown(self):store.DB_PATH=self.old;self.tmp.cleanup()
 def test_five_reviews_then_purchase_and_refund(self):
  for i in range(5):
   rid='test_review_'+str(i).zfill(8);store.reserve_review(self.uid,self.app,rid,'snapshot');store.finish_review(self.app,rid,{'summary':'Example'})
  self.assertEqual(store.review_balance(self.uid,self.app)['remaining'],0)
  with self.assertRaises(PermissionError):store.reserve_review(self.uid,self.app,'test_review_exhausted','snapshot')
  order=store.create_order(self.uid,application_id=self.app,product='ai_reviews');store.approve_order(order)
  self.assertEqual(store.review_balance(self.uid,self.app)['remaining'],5);self.assertTrue(store.has_complete(self.uid,self.app))
  store.transition_order(order,'refunded',reason='Test refund');self.assertEqual(store.review_balance(self.uid,self.app)['remaining'],0);self.assertTrue(store.has_complete(self.uid,self.app))
 def test_failure_refunds_credit_and_replay_returns_encrypted_result(self):
  rid='same_review_request_123';store.reserve_review(self.uid,self.app,rid,'snapshot');self.assertEqual(store.review_balance(self.uid,self.app)['remaining'],4)
  with self.assertRaises(store.ConflictError):store.reserve_review(self.uid,self.app,rid,'snapshot')
  store.finish_review(self.app,rid,None);self.assertEqual(store.review_balance(self.uid,self.app)['remaining'],5)
  store.reserve_review(self.uid,self.app,rid,'snapshot');store.finish_review(self.app,rid,{'summary':'Sensitive fictional review text'})
  cached=store.reserve_review(self.uid,self.app,rid,'snapshot')['cached'];self.assertIn('Sensitive',cached);self.assertEqual(store.review_balance(self.uid,self.app)['remaining'],4)
  with store._db() as c:raw=c.execute('SELECT result_blob FROM ai_reviews WHERE id=?',(rid,)).fetchone()[0]
  self.assertNotIn('Sensitive',raw)
  with self.assertRaises(store.ConflictError):store.reserve_review(self.uid,self.app,rid,'other snapshot')
 def test_reviews_scoped_to_owned_application(self):
  other=store.create_user('other@example.test','AnotherPassword123!')['id']
  with self.assertRaises(PermissionError):store.review_balance(other,self.app)
  with self.assertRaises(PermissionError):store.previous_reviews(other,self.app)
  with self.assertRaises(PermissionError):store.reserve_review(other,self.app,'foreign_request_123','snapshot')
 def test_preparation_score_not_wealth_or_approval(self):
  d=validate({'version':1,'sections':{'funds':[{'balance':'1','available':'1'}]}});low=preparation_report(d);d['sections']['funds'][0].update(balance='999999',available='999999');self.assertEqual(low['score'],preparation_report(d)['score']);self.assertIn('not an automatic visa refusal',low['tasks'][0]['why']);self.assertIn('not',low['score_explanation'].lower())
 def test_mocked_ai_result_consumes_once_and_failure_does_not(self):
  handler=object.__new__(Handler);handler.send=lambda status,body:(status,body);handler.ai_text=lambda *args:json.dumps({'summary':'Check your medical-cost plan.','suggestions':[{'section':'insurance','why':'No written quote recorded.','steps':['Ask for a dated quote.'],'documents':['Written quote']} ]})
  raw={'data':{'version':1,'sections':{}},'consent':True,'request_id':'mocked_review_request_123'}
  with patch.dict(os.environ,{'OPENAI_API_KEY':'mocked','OPENAI_MODEL':'mocked-model'}):
   status,body=handler.full_review({'id':self.uid},{'id':self.app},raw);self.assertEqual(status,200);self.assertEqual(body['balance']['remaining'],4)
   handler.ai_text=lambda *a:(_ for _ in ()).throw(AssertionError('Replay must not call model'))
   self.assertTrue(handler.full_review({'id':self.uid},{'id':self.app},raw)[1]['reused'])
   handler.ai_text=lambda *a:'invalid result';raw['request_id']='failed_review_request_123'
   with self.assertRaises(ValueError):handler.full_review({'id':self.uid},{'id':self.app},raw)
   self.assertEqual(store.review_balance(self.uid,self.app)['remaining'],4)
 def test_refund_of_used_pack_does_not_take_newly_purchased_reviews(self):
  for i in range(5):
   rid='base_review_'+str(i).zfill(8);store.reserve_review(self.uid,self.app,rid,'x');store.finish_review(self.app,rid,{})
  first=store.create_order(self.uid,application_id=self.app,product='ai_reviews');store.approve_order(first)
  for i in range(3):
   rid='extra_review_'+str(i).zfill(8);store.reserve_review(self.uid,self.app,rid,'x');store.finish_review(self.app,rid,{})
  self.assertEqual(store.review_balance(self.uid,self.app)['remaining'],2)
  store.transition_order(first,'refunded',reason='Test refund');self.assertEqual(store.review_balance(self.uid,self.app)['remaining'],0)
  second=store.create_order(self.uid,application_id=self.app,product='ai_reviews');store.approve_order(second)
  self.assertEqual(store.review_balance(self.uid,self.app)['remaining'],5)
 def test_parallel_reservations_cannot_exceed_five(self):
  from concurrent.futures import ThreadPoolExecutor
  def reserve(n):
   try:store.reserve_review(self.uid,self.app,'parallel_review_'+str(n).zfill(8),'snapshot');return True
   except PermissionError:return False
  with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(reserve,range(8)))
  self.assertEqual(sum(results),5);self.assertEqual(store.review_balance(self.uid,self.app)['remaining'],0)
 def test_simple_first_interview_has_no_notice_date_requirement(self):
  d=validate({'version':1,'sections':{'case':{'name':'Example','category':'IR1 — Spouse of a U.S. citizen','stage':'Preparing before my first interview'}}});p=preparation_report(d);self.assertFalse(any(task['section']=='case' for task in p['tasks']));self.assertEqual(d['sections']['case']['interview'],'')
if __name__=='__main__':unittest.main()
