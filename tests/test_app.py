import sys,unittest
from pathlib import Path
from io import BytesIO
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model import validate,compute,SCHEMA
from pdfgen import generate
from pypdf import PdfReader

def fixture():
 d=validate({'version':1,'sample':True,'sections':{}});s=d['sections']
 for sec in SCHEMA:
  if not sec.get('repeat'):s[sec['id']].update(factDate='2026-10-16',source='Fictional applicant interview',certainty='Applicant statement')
 s['case'].update(name='Example Applicant',category='EB-2 NIW',asof='2026-10-16',notice='No actual notice supplied.')
 s['household'].update(members='Two adults and two children, ages 4 and 2.',adults='2',care='Childcare pending.')
 s['housing'].update(location='Example Illinois city',status='Searching',cost='1600',plan='Rental search; no lease signed.')
 s['funds']=[dict(label='Savings A',owner='Adult A, 100%',balance='50000',available='50000',currency='USD',rate='1',date='2026-10-01',fxdate='2026-10-01',fxsource='USD denomination',factDate='2026-10-16',source='Fictional statement',certainty='Applicant statement',refs='E01')]
 s['assets'].update(assets='None reported.',debts='None reported.')
 s['work']=[dict(person=p,status='Seeking work',education='Research doctorate.' if p=='Adult A' else 'Not supplied.',search='No offer asserted.',factDate='2026-10-16',source='Fictional interview',certainty='Applicant statement') for p in ['Adult A','Adult B']]
 s['support'].update(status='No support relied on')
 s['insurance'].update(status='Inquiry sent; quote pending',plan='Family major medical inquiry.',premium='1000',terms='Estimated premium; deductible unknown.')
 for k in ['rent','utilities','food','transport','insurance','health','care','debt','other','arrival','reserve']:s['budget'][k]='0'
 s['budget'].update(rent='1600',utilities='200',food='600',transport='300',insurance='1000',health='100',arrival='5000',reserve='10000',basis='Fictional estimates; not market quotes.')
 s['benefits'].update(status='None reported by applicant')
 s['evidence']=[dict(id='E01',title='Example savings statement',date='2026-10-01',status='Requested',supports='Savings A; training only.',factDate='2026-10-16',source='Fictional index',certainty='Applicant statement')]
 return validate(d)
class AppTests(unittest.TestCase):
 def test_fx_and_runway(self):
  d=fixture();r=compute(d);self.assertEqual(r['liquid'],'50000.00');self.assertEqual(r['monthly'],'3800.00');self.assertEqual(r['runway'],'9.2');d['sections']['funds'][0].update(currency='EUR',rate='1.10');self.assertEqual(compute(d)['liquid'],'55000.00')
 def test_unknown_not_zero(self):
  d=fixture();d['sections']['budget']['food']='';self.assertIsNone(compute(d)['runway'])
 def test_incomplete_fx_excluded(self):
  d=fixture();d['sections']['funds'][0]['fxsource']='';r=compute(d);self.assertEqual(r['liquid'],'0.00');self.assertIsNone(r['runway'])
 def test_invalid_money(self):
  for v in ['-3','NaN','Infinity','1e7']:
   d=fixture();d['sections']['funds'][0]['balance']=v
   with self.assertRaises(ValueError):validate(d)
 def test_share(self):
  d=fixture();d['sections']['funds'][0]['available']='60000'
  with self.assertRaises(ValueError):validate(d)
 def test_evidence(self):
  d=fixture();self.assertTrue(any('E01 is Requested' in f for f in compute(d)['flags']));d['sections']['evidence']*=2
  with self.assertRaises(ValueError):validate(d)
 def test_three_page_example_and_review(self):
  b=generate(fixture(),True,'2026-10-16');r=PdfReader(BytesIO(b));self.assertEqual(len(r.pages),3);text=''.join(p.extract_text() for p in r.pages)
  for term in ['CHARGEREADY','Review confirmed','quote pending','E01','50000.00']:self.assertIn(term,text)
  out=Path(__file__).resolve().parents[1]/'output';out.mkdir(exist_ok=True);(out/'fictional-example.pdf').write_bytes(b)
 def test_blank_draft(self):self.assertLessEqual(len(PdfReader(BytesIO(generate(validate({'version':1,'sections':{}})))).pages),3)
 def test_overflow_rejected(self):
  d=fixture()
  for sec in SCHEMA:
   if not sec.get('repeat'):
    for f in sec['fields']:
     if f[2]=='textarea':d['sections'][sec['id']][f[0]]='Long content '*90
  try:self.assertLessEqual(len(PdfReader(BytesIO(generate(d))).pages),3)
  except ValueError as e:self.assertIn('three-page',str(e))
 def test_escape(self):
  d=fixture();d['sections']['case']['name']='<script>alert(1)</script>';self.assertIn('<script>',PdfReader(BytesIO(generate(d))).pages[0].extract_text())
 def test_free_has_no_pdf(self):
  with self.assertRaisesRegex(ValueError,'Free has no PDF'):generate(fixture(),plan='free')
 def test_handwritten_fields(self):
  text=''.join(p.extract_text() for p in PdfReader(BytesIO(generate(fixture()))).pages)
  for term in ['Case number:', 'Full legal name:', 'Interview date / post:', 'Signature:']:self.assertIn(term,text)
 def test_budget_conflict(self):
  d=fixture();d['sections']['housing']['cost']='1700';self.assertTrue(any('differs' in f for f in compute(d)['flags']))
if __name__=='__main__':unittest.main()
