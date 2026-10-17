"""The PDF renders the same presentation model, labels and facts as the app review."""
from io import BytesIO
from html import escape
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,KeepTogether
from model import SCHEMA,presentation,SOURCES
FONT=Path(__file__).parent/'fonts'/'DejaVuSans.ttf'
pdfmetrics.registerFont(TTFont('Body',str(FONT)));pdfmetrics.registerFont(TTFont('BodyBold',str(FONT.with_name('DejaVuSans-Bold.ttf'))));BODY,BOLD='Body','BodyBold'
INK=colors.HexColor('#203b36');GREEN=colors.HexColor('#234f40');PALE=colors.HexColor('#edf3ee');GOLD=colors.HexColor('#b58a4b')
class NumberedCanvas(canvas.Canvas):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.pages=[]
    def showPage(self):self.pages.append(dict(self.__dict__));self._startPage()
    def save(self):
        for state in self.pages:
            self.__dict__.update(state);self.setFillColor(INK);self.setFont(BODY,7.5);self.drawRightString(572,24,f'{self._pageNumber} / {len(self.pages)}');super().showPage()
        super().save()
def generate(data,attested=False,review_date='',plan='complete'):
    if plan!='complete':raise ValueError('PDF export is available only with Complete. Free has no PDF.')
    p=presentation(data);analysis=p['analysis'];cmap=pdfmetrics.getFont(BODY).face.charToGlyph
    unsupported=set()
    for sec in p['sections']:
        for r in sec['records']:
            for value in [f['value'] for f in r['fields']]+[r['date'],r['source'],r['status'],r['refs']]:unsupported.update(ch for ch in value if ord(ch)>31 and ord(ch) not in cmap)
    if unsupported:raise ValueError('Some characters cannot be printed accurately with the current document font. Enter an accurate applicant-approved Latin-script transliteration for: '+''.join(sorted(unsupported))[:40]+'. Your original answers remain saved.')
    for size in (9,8.5,8):
        output=_build(data,p,attested,review_date,size)
        from pypdf import PdfReader
        if len(PdfReader(BytesIO(output)).pages)<=3:return output
    raise ValueError('The dossier exceeds the readable three-page limit. Shorten long narratives or evidence descriptions using the wording tools; keep full supporting records separately. All your answers remain saved; nothing was silently omitted.')
def _build(data,p,attested,review_date,size):
    out=BytesIO();doc=SimpleDocTemplate(out,pagesize=(612,792),leftMargin=40,rightMargin=40,topMargin=64,bottomMargin=45,title='ChargeReady | Applicant-prepared settlement dossier',author='Applicant')
    body=ParagraphStyle('body',fontName=BODY,fontSize=size,leading=size*1.25,textColor=INK,spaceAfter=2)
    small=ParagraphStyle('meta',parent=body,fontSize=max(7.5,size-.5),leading=max(9,size*1.15),textColor=colors.HexColor('#52655b'))
    group_head=ParagraphStyle('group_head',parent=small,keepWithNext=True)
    head=ParagraphStyle('head',fontName=BOLD,fontSize=11,leading=14,spaceBefore=5,spaceAfter=3,textColor=GREEN,keepWithNext=True)
    title=ParagraphStyle('title',parent=head,fontSize=18,leading=22)
    para=lambda t,style=body:Paragraph(escape(str(t)).replace('\n','<br/>'),style)
    def table(rows,widths,header=False):
        t=Table([[para(v) for v in row] for row in rows],colWidths=widths,repeatRows=1 if header else 0,hAlign='LEFT')
        rules=[('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#d6e1d9'))]
        if header:rules.append(('BACKGROUND',(0,0),(-1,0),PALE))
        t.setStyle(TableStyle(rules));return t
    story=[para('Public-charge preparation summary',title),para(('FICTIONAL TEACHING EXAMPLE | ' if data.get('sample') else '')+('APPLICANT REVIEWED' if attested else 'DRAFT - NOT YET REVIEWED')+' | Prepared on '+__import__('datetime').date.today().isoformat(),small),para('Private details - complete by hand after printing',head),table([['Full legal name: __________________________','Case number: ___________________________'],['Interview date / post: _____________________','Other reference (optional): ________________']],[266,266]),Spacer(1,6)]
    a=p['analysis'];story.append(table([['Accessible funds (USD)','Monthly budget (USD)','Conservative runway'],[a['liquid']+' ('+str(a['counted'])+'/'+str(a['accounts'])+' accounts)',a['monthly']+(' (partial)' if not a['budgetComplete'] else ''),a['runway']+' months' if a['runway'] is not None else 'Not calculable']],[177,177,178],True))
    story.append(para('Applicant-reported, not independently verified. Blank is unknown, not zero. Runway deducts one-time costs and protected reserves; excludes earnings, promised support and non-liquid assets.',small))
    for index,sec in enumerate(p['sections'],1):
        story.append(para(f'{index:02d}  '+sec['title'],head));records=sec['records']
        if not records:story.append(para('Not provided.'));continue
        if sec['id']=='funds':
            tab=p['funds_table'];story.append(table([tab['headers']]+tab['rows'],[177,160,195],True))
            for note in tab['notes']:story.append(para(note,small))
            for i,r in enumerate(records,1):story.append(para('Account '+str(i)+' | Answer recorded / updated: '+r['date']+' | Basis: '+r['source']+' | Answer type: '+r['status']+' | Documents: '+r['refs'],small))
            continue
        if sec['id']=='evidence':
            common_date=records[0]['date'] if all(r['date']==records[0]['date'] for r in records) else None
            common_source=records[0]['source'] if all(r['source']==records[0]['source'] for r in records) else None
            if common_date or common_source:story.append(para('Shared evidence metadata: '+('Answer recorded / updated: '+common_date+' | ' if common_date else '')+('Basis: '+common_source if common_source else ''),small))
            rows=[['Evidence ID / Document date','Document title / issuer','Availability / Facts supported / page reference']]
            for r in records:
                v={f['key']:f['value'] for f in r['fields']};extra=(' | Basis: '+r['source'] if not common_source else '')+(' | Answer recorded / updated: '+r['date'] if not common_date else '')
                rows.append([v['id']+'\n'+v['date'],v['title']+extra+'\nAnswer type: '+r['status'],v['status']+'\n'+v['supports']+(' | Documents: '+r['refs'] if r['refs']!='None linked' else '')])
            story.append(table(rows,[91,204,237],True));continue
        if sec['id']=='applications' and any(any(f['value']!='Not provided' for f in r['fields']) for r in records):
            rows=[['Adult / employer','Role / date / status','Next step / evidence']]
            for r in records:
                v={f['key']:f['value'] for f in r['fields']};rows.append([v['person']+' / '+v['employer'],v['role']+' / '+v['date']+' / '+v['status'],v['next']+'\nAnswer recorded / updated: '+r['date']+' | Basis: '+r['source']+' | Answer type: '+r['status']+' | Documents: '+r['refs']])
            story.append(table(rows,[135,167,230],True));continue
        for ri,r in enumerate(records,1):
            if len(records)>1:story.append(para('Record '+str(ri),small))
            provided=[f for f in r['fields'] if f['value']!='Not provided']
            if sec['id']=='budget':
                values={f['key']:f for f in r['fields']};numeric=[f for f in r['fields'] if f['key']!='basis'];rows=[['Settlement budget item','USD','Settlement budget item','USD']]
                for n in range(0,len(numeric),2):
                    cells=[]
                    for f in numeric[n:n+2]:cells.extend([f['label'],f['value']])
                    rows.append(cells+['']*(4-len(cells)))
                story.append(table(rows,[183,83,183,83],True));story.append(para(values['basis']['label']+': '+values['basis']['value']))
            else:
                text='; '.join(f['label']+': '+f['value'] for f in provided if not f.get('table')) or ('Not provided.' if not provided else '')
                if text:story.append(para(text))
                for field in provided:
                    if field.get('table'):
                        story.append(para(field['label'],group_head));tab=field['table'];n=len(tab['headers']);story.append(table([tab['headers']]+tab['rows'],[532/n]*n,True))
                missing=[f['label'] for f in r['fields'] if f['value']=='Not provided']
                if missing and provided:story.append(para('Not provided: '+', '.join(missing),small))
            story.append(para('Answer recorded / updated: '+r['date']+' | Basis: '+r['source']+' | Answer type: '+r['status']+' | Documents: '+r['refs'],small))
    story.append(para('Personalized evidence & consistency checklist',head));story.append(para('; '.join(p['analysis']['flags']) or 'No automated completeness flags. Facts and documents have not been independently verified.'))
    story.append(para('Applicant review',head));story.append(para('I reviewed every section. To the best of my knowledge, the facts are accurate as dated; estimates, unknowns and missing evidence are identified. I will correct changes and provide supporting documents. '+('Review confirmed on '+review_date+'.' if attested else 'DRAFT - review not yet confirmed.')));story.append(para('Signature: _________________________________    Date: ________________'))
    story.append(para('Preparation sources',head));story.append(para('Follow current official instructions and any specific embassy request. This dossier does not determine eligibility or replace an official worksheet. '+' | '.join(t+': '+u for t,u in SOURCES),small))
    def page(c,d):
        c.setFillColor(GREEN);c.rect(0,752,612,40,fill=1,stroke=0);c.setFillColor(GOLD);c.rect(39,763,4,10,fill=1,stroke=0);c.rect(46,763,4,16,fill=1,stroke=0);c.rect(53,763,4,21,fill=1,stroke=0);c.setFont(BOLD,10);c.setFillColor(colors.white);c.drawString(65,768,'CHARGEREADY  /  PUBLIC-CHARGE PREPARATION')
        c.setFillColor(INK);c.setFont(BODY,7.5);c.drawString(40,24,'Independent preparation. Not government-affiliated, legal advice or a guarantee of approval.')
    try:doc.build(story,onFirstPage=page,onLaterPages=page,canvasmaker=NumberedCanvas)
    except Exception as e:
        from reportlab.platypus.doctemplate import LayoutError
        if isinstance(e,LayoutError):raise ValueError('A field is too long for a readable three-page dossier. Shorten that narrative; all answers remain saved.')
        raise
    return out.getvalue()
