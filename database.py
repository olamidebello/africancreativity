"""Single-instance SQLite persistence, scoped access and immutable job credit ledger."""
import os, sqlite3, hashlib, secrets, time, json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
for envfile in [ROOT/'.env.local']:
    if envfile.is_file():
        for line in envfile.read_text().splitlines():
            k,sep,v=line.partition('=')
            if sep and k in ('OPENAI_API_KEY','OPENAI_MODEL','OPENAI_SPEECH_MODEL','COOKIE_SECURE','MUSICGEN_ENABLED','MUSICGEN_LICENSE_ACCEPTED','DEMUCS_ENABLED','VIDEO_AI_ENABLED','OPENAI_IMAGE_MODEL'):
                os.environ.setdefault(k,v.strip())
DATA=Path(os.environ.get('CREATIVITY_DATA',ROOT/'data')).resolve()
DB=DATA/'creativity.db'
class Problem(Exception):
    def __init__(self,message,status=400):self.message,self.status=message,status

def connect():
    c=sqlite3.connect(DB,timeout=20);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c

def init():
    DATA.mkdir(parents=True,exist_ok=True,mode=0o700);(DATA/'media').mkdir(exist_ok=True,mode=0o700)
    with connect() as c:
        c.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY,name TEXT NOT NULL,slug TEXT NOT NULL UNIQUE,status TEXT NOT NULL DEFAULT 'active',plan TEXT NOT NULL DEFAULT 'starter',credits INTEGER NOT NULL DEFAULT 100,storage_mb INTEGER NOT NULL DEFAULT 500,version INTEGER NOT NULL DEFAULT 1,created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,tenant_id INTEGER REFERENCES tenants(id),username TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS account_profiles(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,email TEXT UNIQUE COLLATE NOCASE NOT NULL,phone TEXT NOT NULL DEFAULT '',country TEXT NOT NULL DEFAULT '',created REAL NOT NULL,updated REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER REFERENCES users(id),expires REAL NOT NULL,csrf TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS invitations(id INTEGER PRIMARY KEY,tenant_id INTEGER NOT NULL REFERENCES tenants(id),token TEXT UNIQUE NOT NULL,role TEXT NOT NULL,expires REAL NOT NULL,used INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS workspaces(id INTEGER PRIMARY KEY,tenant_id INTEGER NOT NULL REFERENCES tenants(id),owner_id INTEGER NOT NULL REFERENCES users(id),name TEXT NOT NULL,created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS members(workspace_id INTEGER REFERENCES workspaces(id),user_id INTEGER REFERENCES users(id),permission TEXT NOT NULL,PRIMARY KEY(workspace_id,user_id));
        CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY,tenant_id INTEGER NOT NULL REFERENCES tenants(id),owner_id INTEGER NOT NULL REFERENCES users(id),workspace_id INTEGER REFERENCES workspaces(id),kind TEXT NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL DEFAULT '{}',visibility TEXT NOT NULL DEFAULT 'private',share_token TEXT UNIQUE,allow_remix INTEGER NOT NULL DEFAULT 0,trashed INTEGER NOT NULL DEFAULT 0,version INTEGER NOT NULL DEFAULT 1,created REAL NOT NULL,updated REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS assets(id INTEGER PRIMARY KEY,tenant_id INTEGER NOT NULL REFERENCES tenants(id),owner_id INTEGER NOT NULL REFERENCES users(id),project_id INTEGER NOT NULL REFERENCES projects(id),name TEXT NOT NULL,path TEXT NOT NULL UNIQUE,kind TEXT NOT NULL,mime TEXT NOT NULL,size INTEGER NOT NULL,duration REAL NOT NULL DEFAULT 0,created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY,tenant_id INTEGER NOT NULL REFERENCES tenants(id),user_id INTEGER NOT NULL REFERENCES users(id),project_id INTEGER NOT NULL REFERENCES projects(id),kind TEXT NOT NULL,payload TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'queued',cost INTEGER NOT NULL,result TEXT,error TEXT,created REAL NOT NULL,updated REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY,tenant_id INTEGER REFERENCES tenants(id),job_id INTEGER REFERENCES jobs(id),delta INTEGER NOT NULL,reason TEXT NOT NULL,created REAL NOT NULL,UNIQUE(job_id,reason));
        CREATE TABLE IF NOT EXISTS likes(user_id INTEGER REFERENCES users(id),project_id INTEGER REFERENCES projects(id),PRIMARY KEY(user_id,project_id));
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,tenant_id INTEGER,actor_id INTEGER,action TEXT NOT NULL,resource TEXT NOT NULL,created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS youtube_accounts(user_id INTEGER PRIMARY KEY REFERENCES users(id),tenant_id INTEGER NOT NULL REFERENCES tenants(id),channel_id TEXT NOT NULL,title TEXT NOT NULL,playlist TEXT NOT NULL,updated REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS youtube_oauth(state TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),tenant_id INTEGER NOT NULL,csrf TEXT NOT NULL,verifier TEXT NOT NULL,expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS youtube_imports(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),tenant_id INTEGER NOT NULL REFERENCES tenants(id),video_id TEXT NOT NULL,title TEXT NOT NULL,channel_title TEXT NOT NULL,created REAL NOT NULL,UNIQUE(user_id,video_id));
        CREATE TABLE IF NOT EXISTS youtube_exports(job_id INTEGER PRIMARY KEY REFERENCES jobs(id),user_id INTEGER NOT NULL REFERENCES users(id),tenant_id INTEGER NOT NULL REFERENCES tenants(id),asset_id INTEGER NOT NULL REFERENCES assets(id),channel_id TEXT NOT NULL,video_id TEXT,state TEXT NOT NULL,privacy TEXT NOT NULL,session_url TEXT,created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS login_limits(ip TEXT PRIMARY KEY,attempts INTEGER NOT NULL,started REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_users_tenant_role ON users(tenant_id,role,active);
        CREATE INDEX IF NOT EXISTS idx_assets_tenant_size ON assets(tenant_id,size);
        CREATE INDEX IF NOT EXISTS idx_jobs_tenant_state ON jobs(tenant_id,state);
        CREATE INDEX IF NOT EXISTS idx_invitations_tenant ON invitations(tenant_id,id);
        CREATE INDEX IF NOT EXISTS idx_ledger_tenant ON ledger(tenant_id,id);
        CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit(tenant_id,id);

        ''')
        c.execute("UPDATE youtube_exports SET state='uncertain' WHERE state='uploading'")
        c.execute("UPDATE youtube_exports SET state='failed' WHERE state='queued' AND job_id IN (SELECT id FROM jobs WHERE state NOT IN ('queued','running'))")
        # Interrupted jobs are refunded rather than replaying possibly charged provider requests.
        for j in c.execute("SELECT * FROM jobs WHERE state='running'").fetchall():
            refund(c,j,'Worker restarted; review before submitting again')

def now():return time.time()
def digest(s):return hashlib.sha256(s.encode()).hexdigest()
def email_address(value):
    if not isinstance(value,str):raise Problem('Enter a valid email address')
    value=value.strip().lower()
    if len(value)>254 or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+",value):raise Problem('Enter a valid email address')
    return value

def password_input(d):
    p=d.get('password')
    if not isinstance(p,str) or not 1<=len(p)<=256:raise Problem('Enter a password of at most 256 characters')
    return p # Password spaces are significant; never use text() here.

def hash_password(p):
    if not isinstance(p,str) or not 12<=len(p)<=256:raise Problem('Choose a password of 12–256 characters')
    salt=secrets.token_hex(16)
    return salt+':'+hashlib.scrypt(p.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
def check_password(p,h):
    try:
        s,v=h.split(':');return secrets.compare_digest(v,hashlib.scrypt(p.encode(),salt=s.encode(),n=16384,r=8,p=1).hex())
    except (ValueError,AttributeError):return False

def text(d,key,maxlen=200,required=True):
    v=d.get(key,'')
    if not isinstance(v,str) or len(v)>maxlen or (required and not v.strip()):raise Problem('Invalid '+key)
    return v.strip()
def number(v,lo,hi):
    import math
    try:n=float(v)
    except (ValueError,TypeError):raise Problem('Invalid number')
    if not math.isfinite(n) or not lo<=n<=hi:raise Problem(f'Number must be between {lo} and {hi}')
    return n

def audit(c,u,action,resource):c.execute('INSERT INTO audit(tenant_id,actor_id,action,resource,created) VALUES(?,?,?,?,?)',(u['tenant_id'],u['id'],action,str(resource),now()))
def require_role(u,*roles):
    if u['role'] not in roles:raise Problem('Permission denied',403)
def tenant_user(u):
    if u['tenant_id'] is None or u['role']=='super_admin':raise Problem('Select a tenant account for creative work; platform admins manage provisioning only',403)
def workspace(c,u,wid,write=False):
    w=c.execute('SELECT * FROM workspaces WHERE id=? AND tenant_id=?',(wid,u['tenant_id'])).fetchone()
    if not w:raise Problem('Workspace not found',404)
    m=c.execute('SELECT permission FROM members WHERE workspace_id=? AND user_id=?',(wid,u['id'])).fetchone()
    if u['role']!='tenant_admin' and w['owner_id']!=u['id'] and (not m or (write and m[0]!='editor')):raise Problem('Workspace access denied',403)
    return w

def project(c,u,pid,write=False):
    tenant_user(u)
    p=c.execute('SELECT * FROM projects WHERE id=? AND tenant_id=?',(pid,u['tenant_id'])).fetchone()
    if not p:raise Problem('Project not found',404)
    if u['role']=='tenant_admin' or p['owner_id']==u['id']:return p
    if p['workspace_id']:workspace(c,u,p['workspace_id'],write);return p
    raise Problem('Project access denied',403)

def asset(c,u,aid):
    a=c.execute('SELECT * FROM assets WHERE id=? AND tenant_id=?',(aid,u['tenant_id'])).fetchone()
    if not a:raise Problem('Asset not found',404)
    project(c,u,a['project_id']);return a

def body(p):return json.loads(p['body'])
def row(p):
    d=dict(p)
    if 'body' in d:d['body']=json.loads(d['body'])
    return d

def refund(c,j,error):
    changed=c.execute("UPDATE jobs SET state='failed',error=?,updated=? WHERE id=? AND state IN ('running','queued')",(error,now(),j['id'])).rowcount
    if changed:
        c.execute("UPDATE youtube_exports SET state=CASE WHEN state='uploading' THEN 'uncertain' ELSE 'failed' END WHERE job_id=? AND state IN ('queued','uploading')",(j['id'],))
        c.execute('UPDATE tenants SET credits=credits+? WHERE id=?',(j['cost'],j['tenant_id']))
        c.execute('INSERT OR IGNORE INTO ledger(tenant_id,job_id,delta,reason,created) VALUES(?,?,?,?,?)',(j['tenant_id'],j['id'],j['cost'],'refund',now()))

def create_project(c,u,d):
    tenant_user(u);kind=d.get('kind','song')
    if kind not in ('song','studio','video','playlist','album','persona'):raise Problem('Invalid project type')
    wid=d.get('workspace_id') or None
    if wid:workspace(c,u,wid,True)
    title=text(d,'title',120);b=d.get('body',{})
    if not isinstance(b,dict) or len(json.dumps(b))>100000:raise Problem('Project data too large')
    return c.execute('INSERT INTO projects(tenant_id,owner_id,workspace_id,kind,title,body,created,updated) VALUES(?,?,?,?,?,?,?,?)',(u['tenant_id'],u['id'],wid,kind,title,json.dumps(b),now(),now())).lastrowid
