"""Root-only administrator promotion, exact registered email, no password changes."""
import argparse,json,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import database as db

def promote(c,email):
    email=db.email_address(email)
    c.execute('BEGIN IMMEDIATE')
    rows=c.execute('SELECT u.* FROM users u JOIN account_profiles p ON p.user_id=u.id WHERE p.email=? COLLATE NOCASE',(email,)).fetchall()
    if len(rows)!=1:raise db.Problem('Exactly one registered account must match the email',404)
    u=rows[0]
    if not u['active']:raise db.Problem('Account is disabled; reactivate it before promotion',409)
    if u['role']=='super_admin':return {'changed':False,'id':u['id'],'email':email,'role':'super_admin'}
    # Preserve tenant ownership links for recovery; platform API rejects creative access.
    c.execute("UPDATE users SET role='super_admin' WHERE id=?",(u['id'],))
    c.execute('DELETE FROM sessions WHERE user_id=?',(u['id'],))
    db.audit(c,{'id':u['id'],'tenant_id':None},'platform.promote.user',u['id'])
    return {'changed':True,'id':u['id'],'email':email,'role':'super_admin','previous_role':u['role'],'retained_tenant_id':u['tenant_id']}

def main():
    if os.geteuid()!=0:raise SystemExit('Run this helper as root on the application server.')
    parser=argparse.ArgumentParser();parser.add_argument('--email',required=True);args=parser.parse_args()
    if not db.DB.is_file():raise SystemExit('Existing application database not found')
    directory=Path('/var/backups/africancreativity');directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    backup=directory/('before-admin-promotion-'+str(time.time_ns())+'.db')
    fd=os.open(str(backup),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
    import sqlite3
    with db.connect() as source,sqlite3.connect(backup) as dest:source.backup(dest)
    try:
        with db.connect() as c:result=promote(c,args.email)
    except db.Problem as error:raise SystemExit(error.message)
    print(json.dumps({**result,'backup':str(backup)}))
if __name__=='__main__':main()
