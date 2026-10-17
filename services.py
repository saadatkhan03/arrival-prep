"""Configured email and PayPal adapters. Tests replace transport; no credentials are bundled."""
import base64,json,os,smtplib,ssl,time,urllib.request,uuid,re
from email.message import EmailMessage
from pathlib import Path
import auth_store

def send_account_link(email,kind,token,origin):
    url=origin+'/#'+kind+'='+token
    body=('Confirm your ChargeReady email address' if kind=='verify' else 'Reset your ChargeReady password')+'\n\n'+url+'\n\nIf this was not you, ignore this message. Resetting access to saved summaries also requires your private recovery code.'
    host=os.getenv('SMTP_HOST')
    if not host:
        if os.getenv('VISA_ENV')=='production':raise ValueError('Email service is not configured.')
        out=auth_store.DB_PATH.parent/'mail-preview';out.mkdir(mode=0o700,exist_ok=True)
        p=out/(str(time.time_ns())+'-'+kind+'.json');p.write_text(json.dumps({'to':email,'kind':kind,'url':url,'message':body}));p.chmod(0o600)
        return 'local-preview'
    msg=EmailMessage();msg['Subject']='ChargeReady - '+('verify your email' if kind=='verify' else 'password reset');msg['From']=os.environ['SMTP_FROM'];msg['To']=email;msg.set_content(body)
    with smtplib.SMTP(host,int(os.getenv('SMTP_PORT','587')),timeout=15) as smtp:
        smtp.starttls(context=ssl.create_default_context());smtp.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD']);smtp.send_message(msg)
    return 'email'

def paypal_ready():return all(os.getenv(x) for x in ['PAYPAL_CLIENT_ID','PAYPAL_CLIENT_SECRET','PAYPAL_MERCHANT_ID','PAYPAL_WEBHOOK_ID'])
def paypal_base():return 'https://api-m.paypal.com' if os.getenv('PAYPAL_ENV')=='live' else 'https://api-m.sandbox.paypal.com'
def _json_request(path,method='POST',body=None,token=None,headers=None):
    hs={'Content-Type':'application/json'};hs.update(headers or {})
    if token:hs['Authorization']='Bearer '+token
    req=urllib.request.Request(paypal_base()+path,method=method,data=json.dumps(body).encode() if body is not None else None,headers=hs)
    with urllib.request.urlopen(req,timeout=20) as response:return json.load(response)
def paypal_token():
    basic=base64.b64encode((os.environ['PAYPAL_CLIENT_ID']+':'+os.environ['PAYPAL_CLIENT_SECRET']).encode()).decode()
    req=urllib.request.Request(paypal_base()+'/v1/oauth2/token',data=b'grant_type=client_credentials',headers={'Authorization':'Basic '+basic,'Content-Type':'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(req,timeout=20) as response:return json.load(response)['access_token']
def create_checkout(order,origin):
    if not paypal_ready():raise ValueError('PayPal is not connected. No charge was made.')
    token=paypal_token()
    if order['provider_ref']:r=_json_request('/v2/checkout/orders/'+order['provider_ref'],'GET',token=token)
    else:
        body={'intent':'CAPTURE','purchase_units':[{'reference_id':str(order['id']),'custom_id':str(order['application_id']),'description':'5 additional AI preparation reviews' if order.get('product')=='ai_reviews' else 'Complete public-charge preparation for one application','amount':{'currency_code':'USD','value':'5.00'},'payee':{'merchant_id':os.environ['PAYPAL_MERCHANT_ID']}}],'payment_source':{'paypal':{'experience_context':{'return_url':origin+'/?checkout=return','cancel_url':origin+'/?checkout=cancel','shipping_preference':'NO_SHIPPING','user_action':'PAY_NOW'}}}}
        r=_json_request('/v2/checkout/orders',body=body,token=token,headers={'PayPal-Request-Id':'visaready-order-'+str(order['id'])});auth_store.attach_provider(order['id'],r['id'])
    approval=next((l['href'] for l in r.get('links',[]) if l['rel'] in ('payer-action','approve')),None)
    if not approval or not approval.startswith(('https://www.paypal.com/','https://www.sandbox.paypal.com/')):raise ValueError('PayPal approval link is unavailable.')
    return approval

def verify_completed(order,response,event_id):
    # Capture response queried directly from PayPal; all expected dimensions checked server-side.
    if response.get('id')!=order['provider_ref'] or response.get('status')!='COMPLETED':raise ValueError('Payment is not completed.')
    units=response.get('purchase_units',[])
    if len(units)!=1:raise ValueError('Unexpected payment units.')
    unit=units[0]
    if unit.get('reference_id')!=str(order['id']) or unit.get('custom_id')!=str(order['application_id']) or unit.get('payee',{}).get('merchant_id')!=os.environ['PAYPAL_MERCHANT_ID']:raise ValueError('Payment recipient or application does not match.')
    captures=unit.get('payments',{}).get('captures',[])
    if len(captures)!=1:raise ValueError('Unexpected capture count.')
    capture=captures[0]
    if capture.get('status')!='COMPLETED' or capture.get('amount')!={'currency_code':'USD','value':'5.00'}:raise ValueError('Payment amount or currency does not match.')
    return auth_store.transition_order(order['id'],'paid',reference=capture['id'],reason='PayPal capture verified',event_id=event_id)
def capture_order(order):
    if not paypal_ready():raise ValueError('PayPal is not configured.')
    if order['status']=='paid':return True
    if not order['provider_ref']:raise ValueError('Create checkout first.')
    token=paypal_token();response=_json_request('/v2/checkout/orders/'+order['provider_ref']+'/capture',body={},token=token,headers={'PayPal-Request-Id':'visaready-capture-'+str(order['id'])})
    return verify_completed(order,response,'capture:'+order['provider_ref'])
def webhook(headers,event):
    if not paypal_ready():raise PermissionError('PayPal webhook is not configured.')
    required=['PAYPAL-AUTH-ALGO','PAYPAL-CERT-URL','PAYPAL-TRANSMISSION-ID','PAYPAL-TRANSMISSION-SIG','PAYPAL-TRANSMISSION-TIME']
    values={k:headers.get(k) for k in required}
    if not all(values.values()):raise PermissionError('Missing PayPal signature headers.')
    token=paypal_token();body={'auth_algo':values[required[0]],'cert_url':values[required[1]],'transmission_id':values[required[2]],'transmission_sig':values[required[3]],'transmission_time':values[required[4]],'webhook_id':os.environ['PAYPAL_WEBHOOK_ID'],'webhook_event':event}
    if _json_request('/v1/notifications/verify-webhook-signature',body=body,token=token).get('verification_status')!='SUCCESS':raise PermissionError('Invalid PayPal webhook signature.')
    event_id=event.get('id');kind=event.get('event_type');resource=event.get('resource',{})
    if not event_id:raise ValueError('Missing event ID.')
    if kind=='PAYMENT.CAPTURE.COMPLETED':
        ref=resource.get('supplementary_data',{}).get('related_ids',{}).get('order_id')
        with auth_store._db() as c:row=c.execute('SELECT * FROM orders WHERE provider_ref=?',(ref,)).fetchone()
        if not row:raise ValueError('Unrecognized payment order.')
        response=_json_request('/v2/checkout/orders/'+ref,'GET',token=token);verify_completed(dict(row),response,event_id)
    elif kind in ('PAYMENT.CAPTURE.REFUNDED','CUSTOMER.DISPUTE.CREATED','PAYMENT.CAPTURE.DENIED','PAYMENT.CAPTURE.REVERSED'):
        capture_id=resource.get('supplementary_data',{}).get('related_ids',{}).get('capture_id')
        if kind=='CUSTOMER.DISPUTE.CREATED':capture_id=next((x.get('seller_transaction_id') for x in resource.get('disputed_transactions',[])),None)
        if kind in ('PAYMENT.CAPTURE.DENIED','PAYMENT.CAPTURE.REVERSED'):capture_id=resource.get('id')
        if not capture_id:
            from urllib.parse import urlsplit
            for link in resource.get('links',[]):
                match=re.search(r'/v2/payments/captures/([A-Za-z0-9]+)$',urlsplit(link.get('href','')).path)
                if link.get('rel')=='up' and match:capture_id=match.group(1)
        with auth_store._db() as c:row=c.execute('SELECT * FROM orders WHERE capture_ref=?',(capture_id,)).fetchone() if capture_id else None
        if not row:
            ref=resource.get('supplementary_data',{}).get('related_ids',{}).get('order_id')
            if not ref and capture_id and re.fullmatch(r'[A-Za-z0-9]+',capture_id):
                capture=_json_request('/v2/payments/captures/'+capture_id,'GET',token=token);ref=capture.get('supplementary_data',{}).get('related_ids',{}).get('order_id')
            with auth_store._db() as c:row=c.execute('SELECT * FROM orders WHERE provider_ref=?',(ref,)).fetchone() if ref else None
        if not row:raise ValueError('Payment event needs manual reconciliation; no access was changed.')
        status={'PAYMENT.CAPTURE.REFUNDED':'refunded','CUSTOMER.DISPUTE.CREATED':'disputed','PAYMENT.CAPTURE.DENIED':'failed','PAYMENT.CAPTURE.REVERSED':'disputed'}[kind]
        auth_store.transition_order(row['id'],status,reason='Verified PayPal event',event_id=event_id)
    return {'received':True}
