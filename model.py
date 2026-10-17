"""Strict input validation and deterministic dossier content. No AI-generated facts."""
import json, math, re
from pathlib import Path
from datetime import date
from decimal import Decimal
SCHEMA=json.loads((Path(__file__).parent/'schema.json').read_text())
SOURCES=[('Department of State: Public benefits reliance','https://travel.state.gov/content/travel/en/News/visas-news/preventing-public-benefits-reliance.html'),('Department of State: Visa denials','https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/visa-denials.html')]
META=[['factDate','Fact date','date'],['source','Source / basis','text'],['refs','Evidence IDs','text'],['certainty','Fact status','select',['Applicant statement','Document-supported (applicant checked)','Estimate','Unknown']]]

def validate(data):
    if not isinstance(data,dict) or data.get('version')!=1: raise ValueError('Unsupported file format.')
    if not isinstance(data.get('sections'),dict): raise ValueError('Sections are required.')
    out={'version':1,'sample':data.get('sample') is True,'sections':{}}
    for sec in SCHEMA:
        raw=data['sections'].get(sec['id'],[] if 'repeat' in sec else {})
        if 'repeat' in sec:
            if not isinstance(raw,list) or len(raw)>20: raise ValueError('Use at most 20 records per section.')
            out['sections'][sec['id']]=[clean_record(r,sec['fields']+META) for r in raw]
        else: out['sections'][sec['id']]=clean_record(raw,sec['fields']+META)
    ids=[x.get('id','') for x in out['sections']['evidence'] if x.get('id')]
    if len(ids)!=len(set(ids)): raise ValueError('Evidence IDs must be unique.')
    if any(not re.fullmatch(r'[A-Za-z0-9_-]{1,16}',s) for s in ids): raise ValueError('Evidence IDs: use 1–16 letters, numbers, hyphens or underscores.')
    for a in out['sections']['funds']:
        if a.get('currency') and not re.fullmatch('[A-Z]{3}',a['currency']): raise ValueError('Use uppercase three-letter currency codes.')
        if a.get('available') and a.get('balance') and Decimal(a['available'])>Decimal(a['balance']): raise ValueError('Accessible amount cannot exceed the account balance.')
        owner_rows=a.get('_guided',{}).get('owner') or []
        share=owner_rows[0].get('share','') if owner_rows else ''
        if share in ('25%','50%','75%','100%') and a.get('balance') and a.get('available') and Decimal(a['available'])>Decimal(a['balance'])*Decimal(share.rstrip('%'))/100:raise ValueError('Amount available for your move cannot exceed the household ownership share you selected.')
        if a.get('rate') and Decimal(a['rate'])<=0: raise ValueError('Exchange rates must be greater than zero.')
        if a.get('currency')=='USD' and a.get('rate') and Decimal(a['rate'])!=1: raise ValueError('USD exchange rate must equal 1.')
    n=out['sections']['household'].get('adults')
    if n and (Decimal(n)!=int(Decimal(n)) or not 1<=int(Decimal(n))<=20): raise ValueError('Number of adults must be a whole number from 1 to 20.')
    return out

def clean_record(raw,fields):
    if not isinstance(raw,dict): raise ValueError('Invalid record.')
    out={}
    for f in fields:
        value=raw.get(f[0],'')
        if not isinstance(value,str) or len(value)>1200: raise ValueError(f'{f[1]} must be text of at most 1,200 characters.')
        value=value.strip()
        if any(ord(c)<32 and c not in '\n\t' for c in value): raise ValueError('Control characters are not allowed.')
        if value and f[2]=='number':
            if not re.fullmatch(r'\d{1,12}(\.\d{1,8})?',value): raise ValueError(f'{f[1]} must be a nonnegative number, without commas.')
        if value and f[2]=='date':
            try: date.fromisoformat(value)
            except ValueError: raise ValueError(f'Invalid date for {f[1]}.')
        if value and f[2]=='select' and value not in f[3] and f[0]!='category' and not (len(f)>5 and f[5] and f[5].get('options')): raise ValueError(f'Invalid option for {f[1]}.')
        out[f[0]]=value
    guided=raw.get('_guided',{})
    if not isinstance(guided,dict):raise ValueError('Invalid guided answers.')
    configs={f[0]:f[5] for f in fields if len(f)>5 and f[5] and f[5].get('parts')}
    if set(guided)-set(configs):raise ValueError('Unknown guided field.')
    for key,rows in guided.items():
        config=configs[key]
        if not isinstance(rows,list) or len(rows)>config['maxRows']:raise ValueError('Too many guided rows.')
        clean=[]
        for row in rows:
            if not isinstance(row,dict) or set(row)-{p['key'] for p in config['parts']}:raise ValueError('Invalid guided row.')
            parts=[[p['key'],p['label'],p['type']] for p in config['parts']]
            clean.append(clean_record(row,parts))
        value=format_guided(config,clean)
        if len(value)>1200:raise ValueError('Shorten optional details in '+key+' to fit 1,200 characters.')
        out.setdefault('_guided',{})[key]=clean
        out[key]=value
    return out

def format_guided(config,rows):
    return '\n'.join(filter(None,('; '.join(p['label']+': '+row[p['key']].strip() for p in config['parts'] if row.get(p['key'],'').strip()) for row in rows)))

def compute(data):
    s=data['sections']; flags=[]; liquid=Decimal(0); counted=0
    evidence={r['id']:r for r in s['evidence'] if r.get('id')}
    for sec in SCHEMA:
        records=s[sec['id']] if 'repeat' in sec else [s[sec['id']]]
        if not records or not any(any(r.get(f[0]) for f in sec['fields']) for r in records):
            flags.append(sec['title']+': not provided.')
        for i,r in enumerate(records):
            label=sec['title']+(f' #{i+1}' if 'repeat' in sec else '')
            if not r.get('factDate'): flags.append(label+': fact date missing.')
            elif r['factDate']>date.today().isoformat(): flags.append(label+': fact date is in the future; verify.')
            if not r.get('source'): flags.append(label+': source missing.')
            refs=re.split(r'[,\s]+',r.get('refs','').strip()) if r.get('refs') else []
            if not refs and sec['id']!='evidence': flags.append(label+': no evidence linked.')
            for ref in refs:
                if ref not in evidence: flags.append(label+': unknown evidence ID '+ref+'.')
                elif evidence[ref].get('status')!='Available': flags.append(label+': '+ref+' is '+(evidence[ref].get('status') or 'unclassified')+'.')
    for i,a in enumerate(s['funds']):
        required=['label','owner','balance','currency','available','rate','date','fxdate','fxsource']
        if not all(a.get(k) for k in required): flags.append(f'Account {i+1}: excluded from USD subtotal until balance, owner, access, currency, dates and FX basis are complete.');continue
        ownership=a.get('_guided',{}).get('owner') or [{}]
        if ownership[0].get('access') in ('Consent required; not yet obtained','Not yet confirmed'):
            flags.append(f'Account {i+1}: excluded until withdrawal permission is confirmed.');continue
        liquid+=Decimal(a['available'])*Decimal(a['rate']);counted+=1
    b=s['budget']; costs=['rent','utilities','food','transport','insurance','health','care','debt','other']
    complete=all(b.get(k)!='' for k in costs+['arrival','reserve'])
    monthly=sum((Decimal(b[k]) for k in costs if b.get(k)),Decimal(0))
    runway=None
    if complete and counted==len(s['funds']) and counted and monthly>0:
        runway=max(Decimal(0),liquid-Decimal(b['arrival'])-Decimal(b['reserve']))/monthly
    if not complete: flags.append('Budget: incomplete; runway is unavailable. Blank is not zero.')
    if complete and monthly==0: flags.append('Budget: monthly costs total zero; verify before relying on this plan.')
    for section,key,bkey in [('housing','cost','rent'),('insurance','premium','insurance')]:
        if s[section].get(key) and b.get(bkey) and Decimal(s[section][key])!=Decimal(b[bkey]): flags.append(section.title()+': amount differs from settlement budget.')
    adults=s['household'].get('adults')
    if not adults or int(Decimal(adults))!=len(s['work']): flags.append('Adult count does not match employment records or is missing.')
    if s['insurance'].get('status')!='Active coverage': flags.append('Insurance: confirm start conditions and how any coverage gap would be funded.' if s['insurance'].get('status') in ('Written quote received','Enrollment pending') else 'Insurance: medical-cost and coverage plan needs clarification.')
    if s['benefits'].get('status') in ['', 'Unknown / need advice']: flags.append('Benefits history: clarification / qualified advice needed.')
    for r in s['evidence']:
        if r.get('status')!='Available': flags.append((r.get('id') or 'Evidence item')+': '+(r.get('status') or 'availability unknown')+'.')
        if not r.get('date'): flags.append((r.get('id') or 'Evidence item')+': document date missing.')
    essentials={'case':['name','category'],'household':['members','adults','care'],'housing':['location','status','plan','cost'],'assets':['assets','debts'],'work':['person','status','employment','search','education','license','fallback'],'applications':['person','employer','role','date','status'],'support':['status'],'insurance':['status','plan','premium','terms','dates','care'],'budget':['basis'],'benefits':['status'],'evidence':['id','title','date','status','supports']}
    for sec in SCHEMA:
        records=s[sec['id']] if 'repeat' in sec else [s[sec['id']]]
        for i,r in enumerate(records):
            if not any(r.get(f[0]) for f in sec['fields']): continue
            missing=[k for k in essentials.get(sec['id'],[]) if not r.get(k)]
            if missing:flags.append(sec['title']+(f' #{i+1}' if 'repeat' in sec else '')+': clarify '+', '.join(missing)+'.')
    labels=[a.get('label','').lower() for a in s['funds'] if a.get('label')]
    if len(labels)!=len(set(labels)):flags.append('Duplicate account aliases: check for double-counted funds.')
    return {'liquid':str(liquid.quantize(Decimal('.01'))),'counted':counted,'accounts':len(s['funds']),'monthly':str(monthly.quantize(Decimal('.01'))),'budgetComplete':complete,'runway':str(runway.quantize(Decimal('.1'))) if runway is not None else None,'flags':list(dict.fromkeys(flags))}

def section_text(sec,data):
    records=data['sections'][sec['id']] if 'repeat' in sec else [data['sections'][sec['id']]]
    result=[]
    for i,r in enumerate(records):
        vals=[f'{short_label(sec["id"],f)}: {r[f[0]]}' for f in sec['fields'] if r.get(f[0])]
        if not vals: continue
        text=('Record '+str(i+1)+'. ' if 'repeat' in sec else '')+'; '.join(vals)+'.'
        text+=' [As of '+(r.get('factDate') or 'not stated')+'; '+(r.get('certainty') or 'status not stated')+'; source: '+(r.get('source') or 'not stated')+'; evidence: '+(r.get('refs') or 'none linked')+']'
        result.append(text)
    return result or ['Not provided.']


def short_label(section,field):
    labels={
      'case':['Applicant','Category','Post','Interview','Notice','Dossier date'],
      'household':['Members','Adults','Dependent care'],
      'housing':['Location','Arrival','Status','Housing plan','Monthly USD'],
      'funds':['Account alias','Owner/share','Balance','Currency','Accessible','USD/unit','FX date','FX source','Balance date','Restrictions'],
      'assets':['Assets','Liabilities','Realization'],
      'applications':['Adult','Employer / institution','Role / reference','Application or contact date','Application status','Next step / deadline'],
      'work':['Adult','Status','Current work/income','U.S. work/search','Education','Licensing','Interim plan'],
      'support':['Status','Commitment','Capacity/affidavit'],
      'insurance':['Status','Plan/members','Premium USD/mo','Terms','Dates/conditions','Care/gap funding'],
      'budget':['Housing','Utilities','Food','Transport','Insurance','Health reserve','Care/education','Debt/support','Other','One-time costs','Emergency reserve','Basis'],
      'benefits':['Status','History/context'],
      'evidence':['ID','Document/issuer','Document date','Availability','Supports/reference']}
    sec=next(s for s in SCHEMA if s['id']==section)
    return field[1]


def funds_table(data):
    headers=['Account / ownership','Original / accessible funds','Conversion / dates']
    rows=[];notes=[]
    for r in data['sections']['funds']:
        get=lambda k:r.get(k) or 'Not provided'
        rows.append([get('label')+'\n'+get('owner'),'Balance: '+get('balance')+' '+get('currency')+'\nAccessible: '+get('available')+' '+get('currency'),get('rate')+' USD / unit\nSource: '+get('fxsource')+'\nFX date: '+get('fxdate')+'\nBalance date: '+get('date')])
        notes.append(get('label')+' — Restrictions / recent deposits: '+get('restrictions'))
    return {'headers':headers,'rows':rows,'notes':notes}

def guided_table(field,record):
    config=field[5] if len(field)>5 else None
    rows=record.get('_guided',{}).get(field[0])
    if not config or not config.get('rows') or not rows:return None
    parts=[p for p in config['parts'] if any(row.get(p['key']) for row in rows)]
    if not parts:return None
    first=parts if len(parts)<=6 else parts[:3];rest=[] if len(parts)<=6 else parts[3:]
    return {'headers':[p['label'] for p in first]+(['Other details'] if rest else []),'rows':[[row.get(p['key']) or 'Not provided' for p in first]+(['; '.join(p['label']+': '+row[p['key']] for p in rest if row.get(p['key'])) or 'Not provided'] if rest else []) for row in rows if any(row.values())]}

def presentation(data):
    analysis=compute(data)
    sections=[]
    for sec in SCHEMA:
        records=data['sections'][sec['id']] if sec.get('repeat') else [data['sections'][sec['id']]]
        sections.append({'id':sec['id'],'title':sec['title'],'records':[{'fields':[{'key':f[0],'label':f[1],'value':r.get(f[0]) or 'Not provided','table':guided_table(f,r)} for f in sec['fields'] if f[0]!='language' and not (len(f)>5 and f[5] and (f[5].get('advanced') or f[5].get('hidden')) and not r.get(f[0]))],'date':r.get('factDate') or 'Not stated','source':r.get('source') or 'Not stated','status':r.get('certainty') or 'Not stated','refs':r.get('refs') or 'None linked'} for r in records]})
    checklist=[]
    for flag in analysis['flags']:
        section_id=next((sec['id'] for sec in SCHEMA if flag.startswith(sec['title'])),None)
        if section_id is None:
            section_id=next((value for prefix,value in [('Account ','funds'),('Insurance:','insurance'),('Budget:','budget'),('Support:','support')] if flag.startswith(prefix)),None)
        if section_id is None and flag.startswith('Adult count'):section_id='work'
        checklist.append({'section_id':section_id,'issue':flag,'action':('Request or update the document; keep its status accurate.' if any(w in flag.lower() for w in ['evidence','missing','requested','document']) else 'Confirm the fact, date or amount and correct the relevant section.' )})
    practice=[]
    for sec in SCHEMA:
        records=data['sections'][sec['id']] if sec.get('repeat') else [data['sections'][sec['id']]]
        if any(any(r.values()) for r in records):practice.append({'section':sec['title'],'question':sec['question'],'basis':'Practice prompt, not a prediction of what an officer will ask.'})
    return {'sections':sections,'funds_table':funds_table(data),'analysis':analysis,'checklist':checklist,'practice':practice,'notice':'Applicant-prepared; facts and evidence have not been independently verified.'}
