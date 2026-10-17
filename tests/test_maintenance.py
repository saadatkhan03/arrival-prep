import unittest,tempfile,sqlite3
from pathlib import Path
from cryptography.fernet import Fernet
from maintenance import backup,restore
class BackupTests(unittest.TestCase):
 def test_encrypted_backup_roundtrip_and_no_overwrite(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);db=root/'original.sqlite3';archive=root/'backup.encrypted';copy=root/'restored.sqlite3';key=Fernet.generate_key()
   with sqlite3.connect(db) as c:c.execute('CREATE TABLE test(value TEXT)');c.execute('INSERT INTO test VALUES("secret metadata")')
   backup(db,archive,key);self.assertNotIn(b'secret metadata',archive.read_bytes());restore(archive,copy,key)
   with sqlite3.connect(copy) as c:self.assertEqual(c.execute('SELECT value FROM test').fetchone()[0],'secret metadata')
   with self.assertRaises(ValueError):restore(archive,copy,key)
if __name__=='__main__':unittest.main()
