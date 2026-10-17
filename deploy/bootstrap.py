"""Read a bootstrap password on stdin; preserve existing platform passwords."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import database as db
username=sys.argv[1];secret=sys.stdin.read().strip();db.init()
with db.connect() as c:
    existing=c.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
    if existing:
        if existing['role']!='super_admin':raise SystemExit('Bootstrap name is already a tenant account')
        print('Existing platform account preserved')
    else:
        c.execute("INSERT INTO users(username,name,password,role,created) VALUES(?,?,?,'super_admin',?)",(username,username,db.hash_password(secret),db.now()));print('Platform administrator created')
