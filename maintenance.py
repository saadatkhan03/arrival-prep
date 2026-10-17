"""Operator-only encrypted database backup/restore. Stop the service before restore."""
import argparse,os,sqlite3,tempfile
from pathlib import Path
from cryptography.fernet import Fernet

def backup(database,destination,key):
    database=Path(database);destination=Path(destination)
    if not database.exists():raise ValueError('Database does not exist.')
    with tempfile.TemporaryDirectory() as d:
        copy=Path(d)/'snapshot.sqlite3'
        with sqlite3.connect(database) as source,sqlite3.connect(copy) as target:source.backup(target)
        encrypted=Fernet(key).encrypt(copy.read_bytes())
    destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(encrypted)

def restore(archive,destination,key):
    destination=Path(destination)
    if destination.exists():raise ValueError('Restore to a new private path. Existing databases are never overwritten.')
    plain=Fernet(key).decrypt(Path(archive).read_bytes());destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with tempfile.TemporaryDirectory() as d:
        test=Path(d)/'verified.sqlite3';test.write_bytes(plain)
        with sqlite3.connect(test) as c:
            if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Backup database failed integrity validation.')
        fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(plain)

def main():
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['backup','restore']);p.add_argument('source');p.add_argument('destination');args=p.parse_args()
    key=os.environ.get('VISA_BACKUP_KEY')
    if not key:raise SystemExit('Set VISA_BACKUP_KEY to a separately stored Fernet key; do not put it in source or the backup filename.')
    (backup if args.operation=='backup' else restore)(args.source,args.destination,key.encode());print('Operation complete. Preserve the separate server-secret key for administrator MFA recovery. Backups contain private account metadata; protect and rotate them.')
if __name__=='__main__':main()
