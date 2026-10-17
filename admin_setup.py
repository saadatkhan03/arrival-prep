"""Owner-only local administrator creation/recovery. Never exposes a public MFA bypass."""
import getpass,os,secrets
import auth_store
email=(os.getenv('VISA_ADMIN_EMAIL') or input('Administrator email: ')).strip().lower()
password=os.getenv('VISA_ADMIN_PASSWORD') or getpass.getpass('New administrator password (12–128 characters): ')
auth_store.valid_password(password)
with auth_store._db() as c:
 row=c.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()
 if row:
  c.execute('UPDATE users SET password_hash=?,role="admin",disabled=0,verified=1 WHERE id=?',(auth_store._hash(password),row['id']));c.execute('DELETE FROM sessions WHERE user_id=?',(row['id'],));auth_store.audit(row['id'],'admin.owner_password_reset','user',row['id'],c=c)
  if os.getenv('VISA_RESET_MFA')=='yes':c.execute('DELETE FROM mfa_backup_codes WHERE user_id=?',(row['id'],));c.execute('UPDATE users SET mfa_secret=NULL,mfa_pending=NULL,mfa_last_step=0 WHERE id=?',(row['id'],));auth_store.audit(row['id'],'admin.owner_mfa_reset','user',row['id'],c=c)
 else:
  c.execute('INSERT INTO users(email,password_hash,role,created_at,verified) VALUES(?,?,"admin",strftime("%s","now"),1)',(email,auth_store._hash(password)))
print('Administrator ready. Existing sessions revoked. Set up MFA from the admin console.')
