import unittest,json
from pathlib import Path
from io import BytesIO
from pypdf import PdfReader
from model import validate,presentation
from pdfgen import generate
class PresentationTests(unittest.TestCase):
 def test_app_and_pdf_share_section_names_and_values(self):
  data=validate(json.loads((Path(__file__).resolve().parents[1]/'sample-profile.json').read_text()));p=presentation(data);raw=generate(data,True,'2026-10-17');reader=PdfReader(BytesIO(raw));text=' '.join(' '.join(page.extract_text().split()) for page in reader.pages)
  for sec in p['sections']:self.assertIn(sec['title'],text)
  for value in ['60720.00','6495.00','6.0','Example research institute','E14','Review confirmed']:self.assertIn(value,text)
  self.assertLessEqual(len(reader.pages),3)
 def test_family_example_works_without_interview_date(self):
  d=validate(json.loads((Path(__file__).resolve().parents[1]/'sample-family-profile.json').read_text()));self.assertTrue(d['sample']);self.assertEqual(d['sections']['case']['interview'],'');r=PdfReader(BytesIO(generate(d,True,'2026-10-17')));self.assertLessEqual(len(r.pages),3);text=' '.join(p.extract_text() for p in r.pages);self.assertIn('IR1',text);self.assertIn('CHARGEREADY',text)
 def test_unsupported_characters_fail_explicitly(self):
  data=validate({'version':1,'sections':{'case':{'name':'中文测试'}}})
  with self.assertRaisesRegex(ValueError,'transliteration'):generate(data)
if __name__=='__main__':unittest.main()
