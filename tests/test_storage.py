import unittest,tempfile,json,base64
from pathlib import Path
from unittest.mock import patch
import auth_store as s

def envelope(tag='x'):
 return json.dumps({'format':'arrival-encrypted-v1','salt':base64.b64encode(b's'*16).decode(),'iv':base64.b64encode(b'i'*12).decode(),'cipher':base64.b64encode((tag*30).encode()).decode()})
class StorageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=s.DB_PATH;s.DB_PATH=Path(self.tmp.name)/'db.sqlite3';s.init();self.uid=s.create_user('owner@example.test','OwnerExample123!')['id'];self.a=s.applications(self.uid)[0]['id']
 def tearDown(self):s.DB_PATH=self.old;self.tmp.cleanup()
 def test_purchase_is_scoped_to_one_application(self):
  b=s.create_application(self.uid,'Second application');s.approve_order(s.create_order(self.uid,application_id=self.a));self.assertTrue(s.has_complete(self.uid,self.a));self.assertFalse(s.has_complete(self.uid,b))
 def test_conflict_does_not_replace_saved_data(self):
  s.save_dossier(self.uid,envelope('a'),application_id=self.a,expected_version=0)
  with self.assertRaises(s.ConflictError):s.save_dossier(self.uid,envelope('b'),application_id=self.a,expected_version=0)
  self.assertEqual(s.get_dossier(self.uid,self.a)['encrypted_blob'],envelope('a'))
 def test_revision_history_retains_twenty(self):
  for v in range(23):s.save_dossier(self.uid,envelope(str(v)),application_id=self.a,expected_version=v)
  revisions=s.versions(self.uid,self.a);self.assertEqual(len(revisions),20);self.assertEqual(revisions[0]['version'],23);self.assertEqual(revisions[-1]['version'],4)
 def test_logout_revokes_token(self):
  token=s.login('owner@example.test','OwnerExample123!')[0];s.logout(token);self.assertIsNone(s.user_for_token(token))
 def test_pause_does_not_revive_old_token(self):
  token=s.login('owner@example.test','OwnerExample123!')[0];s.set_user_disabled(self.uid,True);s.set_user_disabled(self.uid,False);self.assertIsNone(s.user_for_token(token))
 def test_foreign_application_forbidden(self):
  other=s.create_user('other@example.test','OtherExample123!')['id']
  with self.assertRaises(PermissionError):s.get_dossier(other,self.a)
 def test_refund_revokes_and_replay_is_idempotent(self):
  order=s.create_order(self.uid);s.transition_order(order,'paid',event_id='event-1');self.assertFalse(s.transition_order(order,'paid',event_id='event-1'));s.transition_order(order,'refunded',event_id='event-2');self.assertFalse(s.has_complete(self.uid,self.a))
  with self.assertRaises(ValueError):s.transition_order(order,'paid',event_id='event-3')
 def test_close_erases_answers_retains_anonymized_order(self):
  order=s.create_order(self.uid);s.approve_order(order);s.save_dossier(self.uid,envelope(),application_id=self.a,expected_version=0);s.delete_user(self.uid)
  self.assertEqual(s.applications(self.uid),[]);self.assertIsNone(s.get_keys(self.uid));self.assertEqual(s.get_order(order)['amount_cents'],500)
  with s._db() as c:self.assertTrue(c.execute('SELECT email FROM users WHERE id=?',(self.uid,)).fetchone()['email'].endswith('@removed.invalid'))
 def test_reset_requires_recovery_wrap_preserves_dossier(self):
  s.initialize_keys(self.uid,envelope('p'),envelope('r'));s.save_dossier(self.uid,envelope('d'),application_id=self.a,expected_version=0);t=s.create_action_token('owner@example.test','reset')['token']
  with self.assertRaises(ValueError):s.reset_password(t,'NewOwnerPassword123!')
  s.reset_password(t,'NewOwnerPassword123!',envelope('n'),1);self.assertTrue(s.login('owner@example.test','NewOwnerPassword123!'));self.assertEqual(s.get_dossier(self.uid,self.a)['encrypted_blob'],envelope('d'))
  with self.assertRaises(ValueError):s.reset_password(t,'AnotherPassword123!',envelope('x'),2)
 def test_rate_limit(self):
  for _ in range(3):s.rate_limit('sample',limit=3)
  with self.assertRaises(PermissionError):s.rate_limit('sample',limit=3)
 def test_mfa_replay_rejected(self):
  secret=s.mfa_setup(self.uid);s.mfa_enable(self.uid,s.totp(secret))
  self.assertIsNone(s.login('owner@example.test','OwnerExample123!'))
  import time
  future=time.time()+31
  with patch('auth_store.time.time',return_value=future):
   otp=s.totp(secret);self.assertTrue(s.login('owner@example.test','OwnerExample123!',otp));self.assertIsNone(s.login('owner@example.test','OwnerExample123!',otp))
 def test_invalid_envelope_rejected(self):
  with self.assertRaises(ValueError):s.save_dossier(self.uid,'plaintext',application_id=self.a,expected_version=0)
if __name__=='__main__':unittest.main()

class AuditIntegrityTests(unittest.TestCase):
 def test_audit_tampering_is_detected(self):
  with tempfile.TemporaryDirectory() as tmp:
   old=s.DB_PATH;s.DB_PATH=Path(tmp)/'db.sqlite3'
   try:
    s.init();s.audit(None,'test.first');s.audit(None,'test.second');self.assertTrue(s.audit_integrity()['valid'])
    with s._db() as c:c.execute('UPDATE audit_events SET action="tampered" WHERE id=1')
    self.assertFalse(s.audit_integrity()['valid'])
   finally:s.DB_PATH=old

class MFABackupTests(unittest.TestCase):
 def test_backup_codes_are_single_use(self):
  with tempfile.TemporaryDirectory() as tmp:
   old=s.DB_PATH;s.DB_PATH=Path(tmp)/'db.sqlite3'
   try:
    s.init();uid=s.create_user('mfa@example.test','MfaTestPassword123!')['id'];secret=s.mfa_setup(uid);codes=s.mfa_enable(uid,s.totp(secret));self.assertEqual(len(codes),10)
    self.assertTrue(s.login('mfa@example.test','MfaTestPassword123!',codes[0]));self.assertIsNone(s.login('mfa@example.test','MfaTestPassword123!',codes[0]))
   finally:s.DB_PATH=old
