"""Private SQLite preview storage. Customer answers are opaque client-encrypted envelopes."""
import hashlib,hmac,os,secrets,sqlite3,time,json,re,base64,struct
from pathlib import Path
from contextlib import contextmanager
ROOT=Path(__file__).parent
DB_PATH=Path(os.getenv('VISA_DB_PATH',str(ROOT/'private'/'visaready.sqlite3')))
PBKDF2_ROUNDS=600000
class ConflictError(ValueError):pass
@contextmanager
def _db():
    DB_PATH.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    c=sqlite3.connect(DB_PATH,timeout=15);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON')
    try:
        yield c;c.commit()
    except BaseException:c.rollback();raise
    finally:c.close()
    try:DB_PATH.chmod(0o600)
    except OSError:pass

def _add(c,table,name,definition):
    if name not in [r['name'] for r in c.execute('PRAGMA table_info('+table+')')]:c.execute('ALTER TABLE '+table+' ADD COLUMN '+name+' '+definition)

def init():
    with _db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,password_hash TEXT,role TEXT NOT NULL DEFAULT 'applicant',created_at INTEGER NOT NULL,disabled INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,expires_at INTEGER NOT NULL,created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS dossiers(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,encrypted_blob BLOB,status TEXT NOT NULL DEFAULT 'draft',updated_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,provider TEXT NOT NULL,provider_ref TEXT UNIQUE,amount_cents INTEGER NOT NULL,currency TEXT NOT NULL DEFAULT 'USD',status TEXT NOT NULL DEFAULT 'pending',created_at INTEGER NOT NULL,paid_at INTEGER);
        CREATE TABLE IF NOT EXISTS audit_events(id INTEGER PRIMARY KEY,actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,action TEXT NOT NULL,subject_type TEXT,subject_id TEXT,ip_region TEXT,created_at INTEGER NOT NULL,details TEXT NOT NULL DEFAULT '{}');
        CREATE TABLE IF NOT EXISTS product_metrics(id INTEGER PRIMARY KEY,event TEXT NOT NULL,value INTEGER NOT NULL DEFAULT 1,created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS applications(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,title TEXT NOT NULL,created_at INTEGER NOT NULL,closed INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS application_dossiers(application_id INTEGER PRIMARY KEY REFERENCES applications(id) ON DELETE CASCADE,encrypted_blob TEXT NOT NULL,version INTEGER NOT NULL,updated_at INTEGER NOT NULL,section_count INTEGER NOT NULL DEFAULT 0,evidence_count INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS dossier_versions(id INTEGER PRIMARY KEY,application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,version INTEGER NOT NULL,encrypted_blob TEXT NOT NULL,created_at INTEGER NOT NULL,UNIQUE(application_id,version));
        CREATE TABLE IF NOT EXISTS entitlements(application_id INTEGER PRIMARY KEY REFERENCES applications(id) ON DELETE CASCADE,kind TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,order_id INTEGER REFERENCES orders(id),created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS mfa_backup_codes(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,code_hash TEXT NOT NULL,PRIMARY KEY(user_id,code_hash));
        CREATE TABLE IF NOT EXISTS account_keys(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,password_wrap TEXT NOT NULL,recovery_wrap TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS action_tokens(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,kind TEXT NOT NULL,expires_at INTEGER NOT NULL,used_at INTEGER);
        CREATE TABLE IF NOT EXISTS consents(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,notice_version TEXT NOT NULL,accepted_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,category TEXT NOT NULL,message TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS provider_events(event_id TEXT PRIMARY KEY,order_id INTEGER NOT NULL REFERENCES orders(id),event_type TEXT NOT NULL,created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts(subject_hash TEXT NOT NULL,created_at INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_attempts ON login_attempts(subject_hash,created_at);
        ''')
        for name,definition in [('verified','INTEGER NOT NULL DEFAULT 1'),('mfa_secret','TEXT'),('mfa_pending','TEXT'),('mfa_last_step','INTEGER NOT NULL DEFAULT 0')]:_add(c,'users',name,definition)
        _add(c,'users','country',"TEXT NOT NULL DEFAULT ''")
        _add(c,'orders','application_id','INTEGER REFERENCES applications(id) ON DELETE SET NULL')
        _add(c,'orders','capture_ref','TEXT')
        _add(c,'orders','access_kind',"TEXT NOT NULL DEFAULT 'pending'")
        c.execute("UPDATE orders SET access_kind='legacy' WHERE status='paid' AND access_kind='pending'")
        _add(c,'audit_events','details',"TEXT NOT NULL DEFAULT '{}'")
        _add(c,'audit_events','previous_hash',"TEXT NOT NULL DEFAULT ''")
        _add(c,'audit_events','row_hash',"TEXT NOT NULL DEFAULT ''")
        _add(c,'sessions','last_seen','INTEGER NOT NULL DEFAULT 0')
        # One-time migration: retain the existing encrypted answers and scope legacy paid access to one application.
        for u in c.execute("SELECT id FROM users WHERE role='applicant' AND disabled=0").fetchall():
            if not c.execute('SELECT 1 FROM applications WHERE user_id=?',(u['id'],)).fetchone():
                app=c.execute('INSERT INTO applications(user_id,title,created_at) VALUES(?,?,?)',(u['id'],'My first application',int(time.time()))).lastrowid
                old=c.execute('SELECT * FROM dossiers WHERE user_id=? ORDER BY updated_at DESC LIMIT 1',(u['id'],)).fetchone()
                if old and old['encrypted_blob']:c.execute('INSERT INTO application_dossiers(application_id,encrypted_blob,version,updated_at) VALUES(?,?,1,?)',(app,old['encrypted_blob'],old['updated_at']))
                c.execute('UPDATE orders SET application_id=? WHERE user_id=? AND application_id IS NULL',(app,u['id']))
                paid=c.execute("SELECT id FROM orders WHERE application_id=? AND status='paid' LIMIT 1",(app,)).fetchone()
                if paid:c.execute('INSERT OR IGNORE INTO entitlements VALUES(?,?,1,?,?)',(app,'legacy',paid['id'],int(time.time())))
        _add(c,'orders','product',"TEXT NOT NULL DEFAULT 'application'")
        c.execute('CREATE TABLE IF NOT EXISTS ai_reviews(id TEXT PRIMARY KEY,application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,status TEXT NOT NULL,snapshot_hash TEXT NOT NULL,result_blob TEXT,created_at INTEGER NOT NULL)')
        _add(c,'ai_reviews','credit_order_id','INTEGER REFERENCES orders(id)')

def _hash(password,salt=None):
    salt=salt or secrets.token_bytes(16);digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,PBKDF2_ROUNDS)
    return f'pbkdf2_sha256${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}'
def _check(password,stored):
    try:
        alg,rounds,salt,digest=stored.split('$');new=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),int(rounds)).hex()
        return alg=='pbkdf2_sha256' and hmac.compare_digest(new,digest)
    except (ValueError,TypeError,AttributeError):return False

def valid_password(password):
    if not isinstance(password,str) or not 12<=len(password)<=128:raise ValueError('Use a unique password of 12 to 128 characters.')
def create_user(email,password,role='applicant',verified=False,country=''):
    email=str(email).strip().lower();valid_password(password)
    country=str(country).strip()
    if len(country)>64:raise ValueError('Country / region must be at most 64 characters.')
    if len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise ValueError('Enter a valid email address.')
    with _db() as c:
        try:uid=c.execute('INSERT INTO users(email,password_hash,role,created_at,verified,country) VALUES(?,?,?,?,?,?)',(email,_hash(password),role,int(time.time()),int(verified),country)).lastrowid
        except sqlite3.IntegrityError:raise ValueError('Unable to register. Try signing in or recovering your account.')
        if role=='applicant':c.execute('INSERT INTO applications(user_id,title,created_at) VALUES(?,?,?)',(uid,'My first application',int(time.time())))
        return dict(c.execute('SELECT id,email,role,verified FROM users WHERE id=?',(uid,)).fetchone())
def ensure_admin():
    email=os.getenv('VISA_ADMIN_EMAIL','').strip().lower();password=os.getenv('VISA_ADMIN_PASSWORD','')
    if email and password:
        with _db() as c:row=c.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()
        if not row:create_user(email,password,'admin',True)

def rate_limit(subject,limit=10,window=900):
    key=hmac.new(_secret_key(),subject.encode(),hashlib.sha256).hexdigest();now=int(time.time())
    with _db() as c:
        c.execute('DELETE FROM login_attempts WHERE created_at<?',(now-86400,))
        if c.execute('SELECT COUNT(*) n FROM login_attempts WHERE subject_hash=? AND created_at>?',(key,now-window)).fetchone()['n']>=limit:raise PermissionError('Too many attempts. Please try again later.')
        c.execute('INSERT INTO login_attempts VALUES(?,?)',(key,now))
def _secret_key():
    from cryptography.fernet import Fernet
    configured=os.getenv('VISA_SECRET_KEY')
    if configured:return configured.encode()
    if os.getenv('VISA_ENV')=='production':raise ValueError('Configure VISA_SECRET_KEY in production.')
    path=DB_PATH.parent/'server-secret.key'
    try:return path.read_bytes()
    except FileNotFoundError:
        key=Fernet.generate_key()
        try:
            fd=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f:f.write(key)
        except FileExistsError:return path.read_bytes()
        return key

def _seal(text):
    from cryptography.fernet import Fernet
    return Fernet(_secret_key()).encrypt(text.encode()).decode()
def _unseal(text):
    from cryptography.fernet import Fernet
    return Fernet(_secret_key()).decrypt(text.encode()).decode()
def totp(secret,step=None):
    step=int(time.time())//30 if step is None else step
    raw=hmac.new(base64.b32decode(secret),struct.pack('>Q',step),hashlib.sha1).digest();offset=raw[-1]&15
    return str((struct.unpack('>I',raw[offset:offset+4])[0]&0x7fffffff)%1000000).zfill(6)
def check_otp(user,code,consume=True):
    if not user['mfa_secret']:return False
    if re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{8}',str(code)):
        digest=hashlib.sha256(str(code).encode()).hexdigest()
        with _db() as c:
            if consume:return c.execute('DELETE FROM mfa_backup_codes WHERE user_id=? AND code_hash=?',(user['id'],digest)).rowcount==1
            return c.execute('SELECT 1 FROM mfa_backup_codes WHERE user_id=? AND code_hash=?',(user['id'],digest)).fetchone() is not None
    if not re.fullmatch(r'\d{6}',str(code)):return False
    secret=_unseal(user['mfa_secret']);current=int(time.time())//30
    for step in (current,current-1,current+1):
        if step>user['mfa_last_step'] and hmac.compare_digest(totp(secret,step),str(code)):
            if consume:
                with _db() as c:
                    updated=c.execute('UPDATE users SET mfa_last_step=? WHERE id=? AND mfa_last_step<?',(step,user['id'],step)).rowcount
                    if not updated:return False
            return True
    return False

def login(email,password,otp=''):
    if not isinstance(password,str) or len(password)>128:return None
    with _db() as c:row=c.execute('SELECT * FROM users WHERE email=? AND disabled=0',(str(email).strip().lower(),)).fetchone()
    # Uniform expensive check for unknown accounts.
    if not row:_hash(password);return None
    if not _check(password,row['password_hash']):return None
    if row['mfa_secret'] and not check_otp(row,otp):return None
    raw=secrets.token_urlsafe(48);now=int(time.time())
    with _db() as c:
        c.execute('DELETE FROM sessions WHERE expires_at<=?',(now,))
        c.execute('INSERT INTO sessions(token_hash,user_id,expires_at,created_at,last_seen) VALUES(?,?,?,?,?)',(hashlib.sha256(raw.encode()).hexdigest(),row['id'],now+28800,now,now))
    return raw,dict(id=row['id'],email=row['email'],role=row['role'],verified=bool(row['verified']),mfa_enabled=bool(row['mfa_secret']))
def user_for_token(token):
    if not token:return None
    digest=hashlib.sha256(token.encode()).hexdigest();now=int(time.time())
    with _db() as c:
        row=c.execute('SELECT u.id,u.email,u.role,u.verified,u.mfa_secret,s.created_at FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND s.last_seen>? AND u.disabled=0',(digest,now,now-1800)).fetchone()
        if row:c.execute('UPDATE sessions SET last_seen=? WHERE token_hash=?',(now,digest))
    return dict(id=row['id'],email=row['email'],role=row['role'],verified=bool(row['verified']),mfa_enabled=bool(row['mfa_secret']),session_created=row['created_at']) if row else None

def logout(token):
    with _db() as c:c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256((token or '').encode()).hexdigest(),))
def reauthenticate(user_id,password,otp=''):
    with _db() as c:row=c.execute('SELECT * FROM users WHERE id=? AND disabled=0',(user_id,)).fetchone()
    if not row or not _check(password,row['password_hash']) or (row['mfa_secret'] and not check_otp(row,otp)):raise PermissionError('Confirm your current password and, when enabled, a fresh authenticator code.')
def mfa_setup(user_id):
    secret=base64.b32encode(secrets.token_bytes(20)).decode()
    with _db() as c:
        if c.execute('SELECT mfa_secret FROM users WHERE id=?',(user_id,)).fetchone()['mfa_secret']:raise ValueError('MFA is already enabled.')
        c.execute('UPDATE users SET mfa_pending=? WHERE id=?',(_seal(secret),user_id))
    return secret

def mfa_enable(user_id,code):
    with _db() as c:row=c.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
    if not row['mfa_pending'] or not hmac.compare_digest(totp(_unseal(row['mfa_pending'])),str(code)):raise ValueError('That authenticator code is not valid.')
    codes=[secrets.token_hex(4)+'-'+secrets.token_hex(4) for _ in range(10)]
    with _db() as c:
        c.execute('DELETE FROM mfa_backup_codes WHERE user_id=?',(user_id,))
        c.executemany('INSERT INTO mfa_backup_codes VALUES(?,?)',[(user_id,hashlib.sha256(code.encode()).hexdigest()) for code in codes])
        c.execute('UPDATE users SET mfa_secret=mfa_pending,mfa_pending=NULL,mfa_last_step=? WHERE id=?',(int(time.time())//30,user_id))
        c.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
        audit(user_id,'account.mfa_enabled','user',user_id,c=c)
    return codes

def _audit_hash(args,previous):
    message=json.dumps(list(args)+[previous],separators=(',',':'),ensure_ascii=True).encode()
    return hmac.new(_secret_key(),message,hashlib.sha256).hexdigest()
def audit(actor,action,subject_type='',subject_id='',ip_region='',details=None,c=None):
    args=(actor,action,subject_type,str(subject_id),ip_region,int(time.time()),json.dumps(details or {}))
    if c is not None:
        row=c.execute('SELECT row_hash FROM audit_events ORDER BY id DESC LIMIT 1').fetchone();previous=row['row_hash'] if row else ''
        c.execute('INSERT INTO audit_events(actor_user_id,action,subject_type,subject_id,ip_region,created_at,details,previous_hash,row_hash) VALUES(?,?,?,?,?,?,?,?,?)',args+(previous,_audit_hash(args,previous)))
    else:
        with _db() as connection:
            connection.execute('BEGIN IMMEDIATE');audit(actor,action,subject_type,subject_id,ip_region,details,connection)
def audit_integrity():
    with _db() as c:rows=c.execute('SELECT * FROM audit_events ORDER BY id').fetchall()
    previous='';legacy=0
    for row in rows:
        if not row['row_hash']:legacy+=1;previous='';continue
        args=(row['actor_user_id'],row['action'],row['subject_type'],row['subject_id'],row['ip_region'],row['created_at'],row['details'])
        if row['previous_hash']!=previous or not hmac.compare_digest(row['row_hash'],_audit_hash(args,previous)):return {'valid':False,'legacy_events':legacy,'message':'Audit history failed its integrity check. Contact the owner.'}
        previous=row['row_hash']
    return {'valid':True,'legacy_events':legacy,'message':'Signed audit entries verified. Historical unsigned entries are identified separately.'}

def applications(user_id):
    with _db() as c:
        rows=c.execute('SELECT a.*,COALESCE(e.active,0) complete,e.kind,COALESCE(d.version,0) version,d.updated_at FROM applications a LEFT JOIN entitlements e ON e.application_id=a.id LEFT JOIN application_dossiers d ON d.application_id=a.id WHERE a.user_id=? AND a.closed=0 ORDER BY a.id',(user_id,)).fetchall()
        return [dict(r) for r in rows]
def create_application(user_id,title):
    title=str(title).strip()
    if not title or len(title)>80:raise ValueError('Use an application label of 1–80 characters, without case numbers.')
    with _db() as c:
        if c.execute('SELECT COUNT(*) n FROM applications WHERE user_id=? AND closed=0',(user_id,)).fetchone()['n']>=20:raise ValueError('Maximum 20 active applications.')
        return c.execute('INSERT INTO applications(user_id,title,created_at) VALUES(?,?,?)',(user_id,title,int(time.time()))).lastrowid

def own_application(user_id,application_id=None):
    with _db() as c:
        if application_id is None:row=c.execute('SELECT * FROM applications WHERE user_id=? AND closed=0 ORDER BY id LIMIT 1',(user_id,)).fetchone()
        else:row=c.execute('SELECT * FROM applications WHERE user_id=? AND id=? AND closed=0',(user_id,int(application_id))).fetchone()
        if not row:raise PermissionError('Application not found for this account.')
        return dict(row)
def has_complete(user_id,application_id=None):
    app=own_application(user_id,application_id)
    with _db() as c:
        row=c.execute('SELECT active FROM entitlements WHERE application_id=?',(app['id'],)).fetchone()
        return bool(row and row['active'])
def valid_envelope(blob):
    if not isinstance(blob,str) or not 0<len(blob)<=220000:raise ValueError('Encrypted data must be at most 220 KB.')
    try:
        e=json.loads(blob)
        if e.get('format')!='arrival-encrypted-v1' or len(base64.b64decode(e['salt'],validate=True))!=16 or len(base64.b64decode(e['iv'],validate=True))!=12 or len(base64.b64decode(e['cipher'],validate=True))<16:raise ValueError()
    except (ValueError,KeyError,TypeError):raise ValueError('Invalid encrypted envelope.')

def get_keys(user_id):
    with _db() as c:
        row=c.execute('SELECT password_wrap,recovery_wrap,revision FROM account_keys WHERE user_id=?',(user_id,)).fetchone();return dict(row) if row else None

def initialize_keys(user_id,password_wrap,recovery_wrap):
    valid_envelope(password_wrap);valid_envelope(recovery_wrap)
    with _db() as c:
        if c.execute('SELECT 1 FROM account_keys WHERE user_id=?',(user_id,)).fetchone():raise ConflictError('Encryption keys already exist. Reload and unlock your account.')
        c.execute('INSERT INTO account_keys(user_id,password_wrap,recovery_wrap) VALUES(?,?,?)',(user_id,password_wrap,recovery_wrap))

def save_dossier(user_id,encrypted_blob,section_count=0,evidence_count=0,application_id=None,expected_version=None):
    valid_envelope(encrypted_blob);app=own_application(user_id,application_id);now=int(time.time())
    with _db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT * FROM application_dossiers WHERE application_id=?',(app['id'],)).fetchone();version=row['version'] if row else 0
        if expected_version is not None and int(expected_version)!=version:raise ConflictError('This application changed in another tab. Download your local backup, then reload or restore a saved revision.')
        version+=1
        c.execute('INSERT INTO dossier_versions(application_id,version,encrypted_blob,created_at) VALUES(?,?,?,?)',(app['id'],version,encrypted_blob,now))
        c.execute('INSERT INTO application_dossiers VALUES(?,?,?,?,?,?) ON CONFLICT(application_id) DO UPDATE SET encrypted_blob=excluded.encrypted_blob,version=excluded.version,updated_at=excluded.updated_at,section_count=excluded.section_count,evidence_count=excluded.evidence_count',(app['id'],encrypted_blob,version,now,max(0,min(int(section_count),20)),max(0,min(int(evidence_count),100))))
        c.execute('DELETE FROM dossier_versions WHERE application_id=? AND version<?',(app['id'],max(1,version-19)))
        audit(user_id,'dossier.saved','application',app['id'],details={'version':version},c=c)
    return dict(saved_at=now,version=version)
def get_dossier(user_id,application_id=None,version=None):
    app=own_application(user_id,application_id)
    with _db() as c:
        if version is None:row=c.execute('SELECT encrypted_blob,version,updated_at FROM application_dossiers WHERE application_id=?',(app['id'],)).fetchone()
        else:row=c.execute('SELECT encrypted_blob,version,created_at updated_at FROM dossier_versions WHERE application_id=? AND version=?',(app['id'],int(version))).fetchone()
        return dict(row) if row else {'encrypted_blob':None,'version':0,'updated_at':None}
def versions(user_id,application_id):
    app=own_application(user_id,application_id)
    with _db() as c:return [dict(r) for r in c.execute('SELECT version,created_at FROM dossier_versions WHERE application_id=? ORDER BY version DESC',(app['id'],))]

def create_order(user_id,provider='paypal',application_id=None,product='application'):
    app=own_application(user_id,application_id)
    if product not in ('application','ai_reviews'):raise ValueError('Unknown purchase type.')
    if product=='application' and has_complete(user_id,app['id']):raise ValueError('This application already has Complete access. Corrections and downloads are included.')
    if product=='ai_reviews' and not has_complete(user_id,app['id']):raise PermissionError('Complete access is required before adding AI reviews.')
    with _db() as c:
        row=c.execute("SELECT id FROM orders WHERE application_id=? AND provider=? AND product=? AND status='pending'",(app['id'],provider,product)).fetchone()
        if row:return row['id']
        return c.execute('INSERT INTO orders(user_id,provider,amount_cents,status,created_at,application_id,product) VALUES(?,?,500,?,?,?,?)',(user_id,provider,'pending',int(time.time()),app['id'],product)).lastrowid

def get_order(order_id):
    with _db() as c:
        row=c.execute('SELECT * FROM orders WHERE id=?',(int(order_id),)).fetchone()
        if not row:raise ValueError('Order not found.')
        return dict(row)
def attach_provider(order_id,reference):
    with _db() as c:c.execute('UPDATE orders SET provider_ref=? WHERE id=? AND provider_ref IS NULL',(reference,order_id))
def transition_order(order_id,status,actor=None,reason='',reference='',kind='verified',event_id=None):
    if status not in ('paid','refunded','disputed','revoked','failed'):raise ValueError('Unsupported order status.')
    now=int(time.time())
    with _db() as c:
        c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT * FROM orders WHERE id=?',(int(order_id),)).fetchone()
        if not row:raise ValueError('Order not found.')
        if event_id:
            if c.execute('SELECT 1 FROM provider_events WHERE event_id=?',(event_id,)).fetchone():return False
            c.execute('INSERT INTO provider_events VALUES(?,?,?,?)',(event_id,order_id,status,now))
        if status=='paid' and row['status'] in ('refunded','disputed','revoked'):raise ValueError('A closed payment cannot be approved again. Create a new reviewed order.')
        c.execute('UPDATE orders SET access_kind=CASE WHEN ?="paid" THEN ? ELSE access_kind END WHERE id=?',(status,kind,order_id))
        c.execute('UPDATE orders SET status=?,paid_at=CASE WHEN ?="paid" THEN COALESCE(paid_at,?) ELSE paid_at END,capture_ref=COALESCE(NULLIF(?,""),capture_ref) WHERE id=?',(status,status,now,reference,order_id))
        if row['application_id'] and row['product']=='application':
            if status=='paid':c.execute('INSERT INTO entitlements VALUES(?,?,1,?,?) ON CONFLICT(application_id) DO UPDATE SET active=1,kind=excluded.kind,order_id=excluded.order_id',(row['application_id'],kind,order_id,now))
            else:c.execute('UPDATE entitlements SET active=0 WHERE application_id=? AND order_id=?',(row['application_id'],order_id))
        audit(actor,'payment.'+status,'order',order_id,details={'reason':reason,'reference':reference,'kind':kind},c=c)
    return True

def approve_order(order_id):return transition_order(order_id,'paid',reason='Local test approval',kind='test')
def mark_order(provider_ref,status):
    with _db() as c:row=c.execute('SELECT id FROM orders WHERE provider_ref=?',(provider_ref,)).fetchone()
    return transition_order(row['id'],status,reason='Verified provider event') if row else False

def set_user_disabled(user_id,disabled,actor=None,reason=''):
    with _db() as c:
        row=c.execute('SELECT role FROM users WHERE id=?',(user_id,)).fetchone()
        if not row:raise ValueError('User not found.')
        if row['role']=='admin':raise ValueError('Administrator accounts cannot be changed here.')
        c.execute('UPDATE users SET disabled=? WHERE id=?',(int(disabled),user_id));c.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
        audit(actor,'account.paused' if disabled else 'account.enabled','user',user_id,details={'reason':reason},c=c)
def delete_user(user_id,actor=None,reason=''):
    with _db() as c:
        row=c.execute('SELECT role FROM users WHERE id=?',(user_id,)).fetchone()
        if not row:raise ValueError('User not found.')
        if row['role']=='admin':raise ValueError('Administrator accounts cannot be closed here.')
        # Retain minimal reconciliation history; remove identity and encrypted applicant information.
        c.execute('DELETE FROM mfa_backup_codes WHERE user_id=?',(user_id,));c.execute('DELETE FROM sessions WHERE user_id=?',(user_id,));c.execute('DELETE FROM account_keys WHERE user_id=?',(user_id,));c.execute('DELETE FROM dossiers WHERE user_id=?',(user_id,));c.execute('DELETE FROM applications WHERE user_id=?',(user_id,));c.execute('DELETE FROM tickets WHERE user_id=?',(user_id,));c.execute('DELETE FROM consents WHERE user_id=?',(user_id,));c.execute('DELETE FROM action_tokens WHERE user_id=?',(user_id,))
        c.execute("UPDATE users SET email=?,country='',password_hash=NULL,disabled=1,mfa_secret=NULL,mfa_pending=NULL WHERE id=?",(f'closed-{user_id}@removed.invalid',user_id))
        audit(actor,'account.closed','user',user_id,details={'reason':reason},c=c)

def create_action_token(email,kind):
    with _db() as c:
        u=c.execute('SELECT id,email FROM users WHERE email=? AND disabled=0',(str(email).strip().lower(),)).fetchone()
        if not u:return None
        raw=secrets.token_urlsafe(32);c.execute('UPDATE action_tokens SET used_at=? WHERE user_id=? AND kind=? AND used_at IS NULL',(int(time.time()),u['id'],kind))
        c.execute('INSERT INTO action_tokens VALUES(?,?,?,?,NULL)',(hashlib.sha256(raw.encode()).hexdigest(),u['id'],kind,int(time.time())+(1800 if kind=='reset' else 86400)))
        return dict(token=raw,email=u['email'])
def token_user(token,kind):
    with _db() as c:
        r=c.execute('SELECT user_id FROM action_tokens WHERE token_hash=? AND kind=? AND used_at IS NULL AND expires_at>?',(hashlib.sha256(str(token).encode()).hexdigest(),kind,int(time.time()))).fetchone()
        if not r:raise ValueError('This link has expired or was already used. Request a new link.')
        return r['user_id']
def verify_email(token):
    uid=token_user(token,'verify')
    with _db() as c:
        c.execute('UPDATE users SET verified=1 WHERE id=?',(uid,));c.execute('UPDATE action_tokens SET used_at=? WHERE token_hash=?',(int(time.time()),hashlib.sha256(token.encode()).hexdigest()))
        audit(uid,'email.verified','user',uid,c=c)
def reset_password(token,password,password_wrap=None,key_revision=None):
    valid_password(password);uid=token_user(token,'reset');keys=get_keys(uid)
    if keys:
        if not password_wrap or key_revision!=keys['revision']:raise ValueError('Use your recovery code to unlock the encryption key before changing the password. Your saved data will not be erased.')
        valid_envelope(password_wrap)
    with _db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT used_at,expires_at FROM action_tokens WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not row or row['used_at'] is not None or row['expires_at']<=int(time.time()):raise ValueError('Reset link expired or used.')
        c.execute('UPDATE users SET password_hash=? WHERE id=?',(_hash(password),uid))
        if keys:
            n=c.execute('UPDATE account_keys SET password_wrap=?,revision=revision+1 WHERE user_id=? AND revision=?',(password_wrap,uid,key_revision)).rowcount
            if not n:raise ConflictError('The encryption key changed. Request another reset link.')
        c.execute('UPDATE action_tokens SET used_at=? WHERE user_id=? AND kind="reset" AND used_at IS NULL',(int(time.time()),uid));c.execute('DELETE FROM sessions WHERE user_id=?',(uid,));audit(uid,'password.reset','user',uid,c=c)

def accept_notice(user_id,version):
    with _db() as c:c.execute('INSERT INTO consents(user_id,notice_version,accepted_at) VALUES(?,?,?)',(user_id,version,int(time.time())))
def create_ticket(user_id,category,message):
    if category not in ('Using the app','Saving or account','PDF','Payment','Suggestion'):raise ValueError('Choose a help category.')
    if not isinstance(message,str) or not 5<=len(message.strip())<=2000:raise ValueError('Describe the problem using 5–2,000 characters. Exclude financial and immigration details.')
    with _db() as c:return c.execute('INSERT INTO tickets(user_id,category,message,created_at) VALUES(?,?,?,?)',(user_id,category,message.strip(),int(time.time()))).lastrowid

def admin_summary():
    with _db() as c:
        return dict(regions=[dict(r) for r in c.execute("SELECT country,COUNT(*) count FROM users WHERE disabled=0 AND role='applicant' AND country<>'' GROUP BY country ORDER BY count DESC")],audit_integrity=audit_integrity(),directory=[dict(r) for r in c.execute('SELECT id,email,role,disabled,verified,created_at FROM users ORDER BY id DESC LIMIT 200')],orders=[dict(r) for r in c.execute('SELECT o.*,u.email FROM orders o JOIN users u ON u.id=o.user_id ORDER BY o.id DESC LIMIT 200')],recent_events=[dict(r) for r in c.execute('SELECT action,subject_type,subject_id,created_at,details FROM audit_events ORDER BY id DESC LIMIT 100')],tickets=[dict(r) for r in c.execute('SELECT t.id,t.category,t.message,t.status,t.created_at,u.email FROM tickets t JOIN users u ON t.user_id=u.id ORDER BY t.id DESC LIMIT 100')],analytics=dict(applicants=c.execute("SELECT COUNT(*) n FROM users WHERE role='applicant' AND disabled=0").fetchone()['n'],applications=c.execute('SELECT COUNT(*) n FROM applications WHERE closed=0').fetchone()['n'],verified_payments=c.execute("SELECT COUNT(*) n FROM orders WHERE status='paid' AND access_kind IN ('verified','manual-reconciled')").fetchone()['n'],test_grants=c.execute("SELECT COUNT(*) n FROM entitlements WHERE kind='test' AND active=1").fetchone()['n'],complimentary_grants=c.execute("SELECT COUNT(*) n FROM entitlements WHERE kind='complimentary' AND active=1").fetchone()['n'],revisions=c.execute('SELECT COUNT(*) n FROM dossier_versions').fetchone()['n'],successful_ai_reviews=c.execute("SELECT COUNT(*) n FROM ai_reviews WHERE status='complete'").fetchone()['n'],average_sections_started=c.execute('SELECT ROUND(COALESCE(AVG(section_count),0),1) n FROM application_dossiers').fetchone()['n']))

def _review_capacity(c,application_id):
    base=5 if c.execute('SELECT 1 FROM entitlements WHERE application_id=? AND active=1',(application_id,)).fetchone() else 0
    now=int(time.time())
    usage={r['credit_order_id']:r['n'] for r in c.execute("SELECT credit_order_id,COUNT(*) n FROM ai_reviews WHERE application_id=? AND (status='complete' OR (status='reserved' AND created_at>?)) GROUP BY credit_order_id",(application_id,now-120))}
    orders=[r['id'] for r in c.execute("SELECT id FROM orders WHERE application_id=? AND product='ai_reviews' AND status='paid' ORDER BY id",(application_id,))]
    slots=[(None,max(0,base-usage.get(None,0)))]+[(oid,max(0,5-usage.get(oid,0))) for oid in orders]
    return {'included':base,'extra':5*len(orders),'used':sum(usage.values()),'remaining':sum(n for _,n in slots)},slots

def review_balance(user_id,application_id):
    app=own_application(user_id,application_id)
    with _db() as c:return _review_capacity(c,app['id'])[0]

def reserve_review(user_id,application_id,request_id,snapshot_hash):
    own_application(user_id,application_id)
    if not re.fullmatch(r'[A-Za-z0-9_-]{16,80}',str(request_id)):raise ValueError('Invalid review request reference.')
    now=int(time.time())
    with _db() as c:
        c.execute('BEGIN IMMEDIATE')
        prior=c.execute('SELECT * FROM ai_reviews WHERE id=?',(request_id,)).fetchone()
        if prior:
            if prior['application_id']!=application_id or not hmac.compare_digest(prior['snapshot_hash'],snapshot_hash):raise ConflictError('This request reference belongs to a different review.')
            if prior['status']=='complete':return {'cached':_unseal(prior['result_blob'])}
            if prior['status']=='reserved' and prior['created_at']>now-120:raise ConflictError('This review is still running. Wait before trying again.')
        balance,slots=_review_capacity(c,application_id)
        if not balance['remaining']:raise PermissionError('All available AI reviews have been used. Five more reviews cost $5. The ordinary preparation checklist remains available.')
        source=next(oid for oid,n in slots if n)
        c.execute('INSERT INTO ai_reviews(id,application_id,status,snapshot_hash,result_blob,created_at,credit_order_id) VALUES(?,?,?,?,NULL,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,result_blob=NULL,created_at=excluded.created_at,credit_order_id=excluded.credit_order_id',(request_id,application_id,'reserved',snapshot_hash,now,source))
    return {'cached':None}

def finish_review(application_id,request_id,result=None):
    with _db() as c:
        c.execute("UPDATE ai_reviews SET status=?,result_blob=? WHERE id=? AND application_id=? AND status='reserved'",('complete' if result is not None else 'failed',_seal(json.dumps(result,ensure_ascii=False)) if result is not None else None,request_id,application_id))
        audit(None,'ai.review.completed' if result is not None else 'ai.review.failed','application',application_id,c=c)

def previous_reviews(user_id,application_id):
    own_application(user_id,application_id)
    with _db() as c:rows=c.execute("SELECT id,created_at,result_blob FROM ai_reviews WHERE application_id=? AND status='complete' ORDER BY created_at DESC LIMIT 20",(application_id,)).fetchall()
    return [{'id':r['id'],'created_at':r['created_at'],'result':json.loads(_unseal(r['result_blob']))} for r in rows]

init();ensure_admin()
