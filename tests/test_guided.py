import unittest,json,subprocess
from pathlib import Path
from io import BytesIO
from pypdf import PdfReader
from model import validate,presentation,SCHEMA,format_guided
from pdfgen import generate
ROOT=Path(__file__).resolve().parents[1]
class GuidedTests(unittest.TestCase):
 def test_choices_cover_every_section_without_default_assertions(self):
  for section in SCHEMA:self.assertTrue(any(len(f)>5 and f[5] for f in section['fields']),section['id'])
  d=validate({'version':1,'sections':{}})
  self.assertEqual(d['sections']['household']['members'],'')
  self.assertEqual(presentation(d)['funds_table']['rows'],[])
 def test_canonical_wording_replaces_forged_summary_and_preserves_choices(self):
  rows=[{'relationship':'Spouse / partner','age':'37','move':'Accompanying now'}]
  d=validate({'version':1,'sections':{'household':{'members':'Invented job offer','_guided':{'members':rows}}}})
  record=d['sections']['household'];self.assertIn('Relationship: Spouse / partner',record['members']);self.assertNotIn('job offer',record['members'])
  self.assertEqual(validate(d),d)
  self.assertEqual(record['_guided']['members'][0]['age'],'37')
  self.assertIsNotNone(presentation(d)['sections'][1]['records'][0]['fields'][0]['table'])
 def test_invalid_structured_numbers_dates_and_unknown_fields_rejected(self):
  cases=[('members',[{'age':'-2'}]),('members',[{'invented':'x'}]),('members',[{}]*11)]
  for key,rows in cases:
   with self.subTest(rows=rows):
    with self.assertRaises(ValueError):validate({'version':1,'sections':{'household':{'_guided':{key:rows}}}})
  with self.assertRaises(ValueError):validate({'version':1,'sections':{'insurance':{'_guided':{'dates':[{'quote':'not-a-date'}]}}}})
 def test_custom_answer_and_legacy_narrative_preserved(self):
  d=validate({'version':1,'sections':{'housing':{'status':'Temporary employer housing','plan':'Existing saved wording'},'funds':[{'currency':'XYZ'}]}})
  self.assertEqual(d['sections']['housing']['status'],'Temporary employer housing');self.assertEqual(d['sections']['housing']['plan'],'Existing saved wording')
  self.assertNotIn('_guided',d['sections']['housing'])
 def test_partial_choices_do_not_imply_zero_or_unanswered_facts(self):
  d=validate({'version':1,'sections':{'assets':{'_guided':{'assets':[{'type':'Vehicle'}]}}}})
  self.assertEqual(d['sections']['assets']['assets'],'Asset type: Vehicle')
  self.assertNotIn('0',d['sections']['assets']['assets'])
 def test_ownership_share_and_pending_access_do_not_overstate_cash(self):
  from model import compute
  account={'label':'Example','owner':'Applicant','balance':'1000','available':'1000','currency':'USD','rate':'1','fxsource':'USD','date':'2026-10-17','fxdate':'2026-10-17','_guided':{'owner':[{'owner':'Applicant','share':'50%','access':'Sole authority'}]}}
  with self.assertRaisesRegex(ValueError,'ownership share'):validate({'version':1,'sections':{'funds':[account]}})
  account['available']='500';account['_guided']['owner'][0]['access']='Consent required; not yet obtained'
  d=validate({'version':1,'sections':{'funds':[account]}});self.assertEqual(compute(d)['liquid'],'0.00');self.assertIn('withdrawal permission',' '.join(compute(d)['flags']))
 def test_shared_formatter_matches_browser_for_unicode_and_rows(self):
  f=next(x for sec in SCHEMA if sec['id']=='household' for x in sec['fields'] if x[0]=='members')
  rows=[{'alias':'Example A','relationship':'Applicant','age':'38'},{'alias':'Example B','relationship':'Other dependent','age':'0'}]
  script="import {formatRows} from './public/guided.mjs';console.log(formatRows("+json.dumps(f[5])+','+json.dumps(rows)+'));'
  actual=subprocess.check_output(['node','--input-type=module','-e',script],cwd=ROOT,text=True).rstrip('\n')
  self.assertEqual(actual,format_guided(f[5],rows))
 def test_funds_and_household_tables_appear_in_pdf(self):
  d=validate({'version':1,'sample':True,'sections':{'case':{'name':'Fictional table example'},'household':{'_guided':{'members':[{'alias':'Example A','relationship':'Applicant','age':'38'}]}},'funds':[{'label':'Example savings','owner':'Applicant','balance':'1234','currency':'USD','available':'1000','rate':'1','fxsource':'USD account; no conversion','date':'2026-10-17','fxdate':'2026-10-17'}]}})
  p=presentation(d);text=' '.join(' '.join(page.extract_text().split()) for page in PdfReader(BytesIO(generate(d))).pages)
  self.assertIn('Example savings',text);self.assertIn('Accessible:',text);self.assertIn('Example A',text);self.assertEqual(p['funds_table']['rows'][0][1],'Balance: 1234 USD\nAccessible: 1000 USD')
if __name__=='__main__':unittest.main()
