#!/usr/bin/env python3
"""AfricanCreativity HTTP app. Run behind an HTTPS reverse proxy for network access."""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from http.cookies import SimpleCookie
from pathlib import Path
import json,os,secrets,base64,mimetypes,sqlite3,re,io,zipfile,argparse,getpass
import database as db,providers,jobs,media
from database import Problem

class Handler(BaseHTTPRequestHandler):
    server_version='AfricanCreativity'
    def log_message(self,fmt,*args):pass # Never log invitation/share query tokens.
    def send(self,status,data,cookie=None):
        raw=json.dumps(data).encode();self.send_response(status);self.headers_common();self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
        if cookie:self.send_header('Set-Cookie',cookie)
        self.end_headers();self.wfile.write(raw)
    def headers_common(self):
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
    def binary(self,path,mime,download=False):
        size=path.stat().st_size;start,end=0,size-1;status=200
        range_header=self.headers.get('Range')
        if range_header:
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',range_header)
            if not match or not any(match.groups()):raise Problem('Invalid byte range',416)
            first,last=match.groups()
            if first:start=int(first);end=min(int(last),end) if last else end
            else:start=max(0,size-int(last))
            if not 0<=start<=end<size:raise Problem('Range outside file',416)
            status=206
        self.send_response(status);self.headers_common();self.send_header('Content-Type',mime);self.send_header('Accept-Ranges','bytes');self.send_header('Content-Length',str(end-start+1))
        if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        if download:self.send_header('Content-Disposition','attachment; filename="AfricanCreativity-'+path.stem+path.suffix+'"')
        self.end_headers()
        with path.open('rb') as f:
            f.seek(start);left=end-start+1
            while left:
                chunk=f.read(min(left,65536))
                if not chunk:break
                self.wfile.write(chunk);left-=len(chunk)
    def input(self):
        try:length=int(self.headers.get('Content-Length','0'))
        except ValueError:raise Problem('Invalid request')
        if not 0<length<=28*1024*1024:raise Problem('Request exceeds 28 MB',413)
        try:d=json.loads(self.rfile.read(length))
        except (ValueError,UnicodeDecodeError):raise Problem('Invalid JSON')
        if not isinstance(d,dict):raise Problem('Expected JSON object')
        return d
    def do_GET(self):self.handle('GET')
    def do_POST(self):self.handle('POST')
    def do_PATCH(self):self.handle('PATCH')
    def do_DELETE(self):self.handle('DELETE')
    def handle(self,method=None):
        if method is None:return super().handle()
        try:self.route(method)
        except Problem as e:self.send(e.status,{'error':e.message})
        except sqlite3.IntegrityError:self.send(409,{'error':'Duplicate or invalid linked record'})
        except (ValueError,TypeError,KeyError,OverflowError):self.send(400,{'error':'Invalid request fields'})
        except (BrokenPipeError,ConnectionResetError):pass
        except Exception as e:
            print('Request failed:',type(e).__name__,flush=True);self.send(500,{'error':'Internal server error'})
    def user(self,c):
        cookie=SimpleCookie()
        try:cookie.load(self.headers.get('Cookie',''))
        except Exception:raise Problem('Authentication required',401)
        token=cookie.get('session');token=token.value if token else ''
        u=c.execute("SELECT u.*,s.csrf FROM users u JOIN sessions s ON s.user_id=u.id LEFT JOIN tenants t ON t.id=u.tenant_id WHERE s.token=? AND s.expires>? AND u.active=1 AND (u.role='super_admin' OR t.status='active')",(db.digest(token),db.now())).fetchone()
        if not u:raise Problem('Sign in to continue',401)
        return u
    def mutation(self,u):
        if not secrets.compare_digest(self.headers.get('X-CSRF-Token',''),u['csrf']):raise Problem('Session verification failed; reload and sign in',403)
    def route(self,method):
        url=urlparse(self.path);path=url.path;qs=parse_qs(url.query)
        if path=='/health' and method=='GET':return self.send(200,{'status':'ok'})
        if not path.startswith('/api/'):
            files={'/':'index.html','/logo.jpg':'logo.jpg','/app.js':'app.js','/style.css':'style.css','/studio.js':'studio.js','/help':'help.html','/terms':'terms.html','/privacy':'privacy.html'}
            if method!='GET' or path not in files:raise Problem('Not found',404)
            f=db.ROOT/'static'/files[path];return self.binary(f,mimetypes.guess_type(f)[0] or 'text/plain')
        with db.connect() as c:
            if path=='/api/login' and method=='POST':
                if self.headers.get('X-Requested-With')!='AfricanCreativity':raise Problem('Invalid sign-in request',403)
                d=self.input();name=db.text(d,'username',80);password=db.text(d,'password',256);ip=self.client_address[0]
                c.execute('BEGIN IMMEDIATE');lim=c.execute('SELECT * FROM login_limits WHERE ip=?',(ip,)).fetchone()
                if lim and db.now()-lim['started']<300 and lim['attempts']>=15:raise Problem('Too many attempts. Wait five minutes.',429)
                if not lim or db.now()-lim['started']>=300:c.execute('INSERT OR REPLACE INTO login_limits VALUES(?,?,?)',(ip,1,db.now()))
                else:c.execute('UPDATE login_limits SET attempts=attempts+1 WHERE ip=?',(ip,))
                c.commit()
                u=c.execute("SELECT u.* FROM users u LEFT JOIN tenants t ON t.id=u.tenant_id WHERE username=? AND u.active=1 AND (u.role='super_admin' OR t.status='active')",(name,)).fetchone()
                if not u or not db.check_password(password,u['password']):raise Problem('Invalid sign-in details',401)
                token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24)
                c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(db.digest(token),u['id'],db.now()+28800,csrf));c.execute('DELETE FROM login_limits WHERE ip=?',(ip,));db.audit(c,u,'login','session')
                cookie='session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'+('; Secure' if os.environ.get('COOKIE_SECURE')=='1' else '')
                return self.send(200,{'csrf':csrf},cookie)
            if path=='/api/accept-invitation' and method=='POST':
                if self.headers.get('X-Requested-With')!='AfricanCreativity':raise Problem('Invalid request',403)
                d=self.input();password=db.hash_password(db.text(d,'password',256));username=db.text(d,'username',80)
                if not re.fullmatch('[a-zA-Z0-9_.@-]{3,80}',username):raise Problem('Username must be 3–80 letters, digits or _.@-')
                c.execute('BEGIN IMMEDIATE');inv=c.execute("SELECT i.* FROM invitations i JOIN tenants t ON t.id=i.tenant_id WHERE i.token=? AND used=0 AND expires>? AND t.status='active'",(db.digest(db.text(d,'token',200)),db.now())).fetchone()
                if not inv:raise Problem('Invitation expired or unavailable',400)
                c.execute('INSERT INTO users(tenant_id,username,name,password,role,created) VALUES(?,?,?,?,?,?)',(inv['tenant_id'],username,db.text(d,'name',120),password,inv['role'],db.now()));c.execute('UPDATE invitations SET used=1 WHERE id=?',(inv['id'],))
                return self.send(201,{'message':'Account created. Sign in to continue.'})
            if path=='/api/explore' and method=='GET':
                projects=c.execute("SELECT p.id,p.title,p.kind,p.updated,u.name as artist,t.name as label FROM projects p JOIN users u ON u.id=p.owner_id JOIN tenants t ON t.id=p.tenant_id WHERE visibility='public' AND trashed=0 AND t.status='active' AND u.active=1 AND p.kind IN ('song','album','playlist','video') ORDER BY p.updated DESC LIMIT 100").fetchall()
                return self.send(200,{'projects':[dict(x) for x in projects]})
            if path.startswith('/api/public/') and method=='GET':
                key=path.split('/')[-1];p=c.execute("SELECT p.* FROM projects p JOIN tenants t ON t.id=p.tenant_id JOIN users u ON u.id=p.owner_id WHERE (cast(p.id as TEXT)=? AND p.visibility='public' OR p.share_token=? AND p.visibility='unlisted') AND p.trashed=0 AND t.status='active' AND u.active=1",(key,key)).fetchone()
                if not p:raise Problem('Published item not found',404)
                # Only the explicitly published project's own assets are exposed, never arbitrary body links.
                assets=c.execute('SELECT id,name,kind,mime,duration FROM assets WHERE project_id=?',(p['id'],)).fetchall()
                tracks=[]
                if p['kind'] in ('playlist','album'):
                    for pid in db.body(p).get('project_ids',[])[:100]:
                        track=c.execute("SELECT p.id,p.title,p.kind FROM projects p JOIN tenants t ON t.id=p.tenant_id JOIN users u ON u.id=p.owner_id WHERE p.id=? AND p.visibility='public' AND p.trashed=0 AND t.status='active' AND u.active=1",(pid,)).fetchone()
                        if track:tracks.append(dict(track))
                return self.send(200,{'project':{'id':p['id'],'title':p['title'],'kind':p['kind'],'allow_remix':bool(p['allow_remix'])},'assets':[dict(a) for a in assets],'tracks':tracks})
            if path.startswith('/api/public-media/') and method=='GET':
                aid=int(path.split('/')[-1]);key=qs.get('key',[''])[0]
                a=c.execute("SELECT a.* FROM assets a JOIN projects p ON p.id=a.project_id JOIN tenants t ON t.id=p.tenant_id JOIN users u ON u.id=p.owner_id WHERE a.id=? AND p.trashed=0 AND t.status='active' AND u.active=1 AND (p.visibility='public' OR p.visibility='unlisted' AND p.share_token=?)",(aid,key)).fetchone()
                if not a:raise Problem('Published media not found',404)
                return self.binary(media.diskpath(a),a['mime'])
            u=self.user(c)
            if method!='GET':self.mutation(u)
            if path=='/api/me' and method=='GET':
                tenant=c.execute('SELECT * FROM tenants WHERE id=?',(u['tenant_id'],)).fetchone()
                return self.send(200,{'user':{k:u[k] for k in ('id','tenant_id','username','name','role')},'tenant':dict(tenant) if tenant else None,'csrf':u['csrf'],'capabilities':providers.capabilities()})
            if path=='/api/logout' and method=='POST':
                c.execute('DELETE FROM sessions WHERE user_id=? AND csrf=?',(u['id'],u['csrf']));return self.send(200,{'ok':True},'session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            if path=='/api/password' and method=='POST':
                d=self.input()
                if not db.check_password(d.get('current',''),u['password']):raise Problem('Current password is incorrect',403)
                hashed=db.hash_password(d.get('password'));c.execute('UPDATE users SET password=? WHERE id=?',(hashed,u['id']));c.execute('DELETE FROM sessions WHERE user_id=? AND csrf!=?',(u['id'],u['csrf']));return self.send(200,{'ok':True})
            if path.startswith('/api/admin/'):return self.admin(c,u,path,method)
            db.tenant_user(u)
            if path=='/api/users' and method=='GET':
                rows=c.execute('SELECT id,name,username,role,active FROM users WHERE tenant_id=?',(u['tenant_id'],)).fetchall();return self.send(200,{'users':[dict(r) for r in rows]})
            if path=='/api/invitations' and method=='POST':
                db.require_role(u,'tenant_admin');d=self.input();role=d.get('role','creator')
                if role not in ('tenant_admin','creator'):raise Problem('Invalid role')
                token=secrets.token_urlsafe(32);c.execute('INSERT INTO invitations(tenant_id,token,role,expires) VALUES(?,?,?,?)',(u['tenant_id'],db.digest(token),role,db.now()+7*86400));db.audit(c,u,'invite',role);return self.send(201,{'token':token,'expires_in_days':7})
            if path.startswith('/api/users/') and method=='PATCH':
                db.require_role(u,'tenant_admin');d=self.input();uid=int(path.split('/')[-1]);target=c.execute('SELECT * FROM users WHERE id=? AND tenant_id=?',(uid,u['tenant_id'])).fetchone()
                if not target:raise Problem('User not found',404)
                if uid==u['id']:raise Problem('You cannot disable or change your own role here')
                role=d.get('role',target['role']);active=d.get('active',target['active'])
                if role not in ('tenant_admin','creator') or active not in (0,1):raise Problem('Invalid role or active status')
                c.execute('UPDATE users SET active=?,role=? WHERE id=?',(active,role,uid));c.execute('DELETE FROM sessions WHERE user_id=?',(uid,));db.audit(c,u,'update.user',uid);return self.send(200,{'ok':True})
            if path=='/api/workspaces':
                if method=='GET':
                    rows=c.execute('SELECT DISTINCT w.* FROM workspaces w LEFT JOIN members m ON m.workspace_id=w.id WHERE w.tenant_id=? AND (w.owner_id=? OR m.user_id=? OR ?)',(u['tenant_id'],u['id'],u['id'],u['role']=='tenant_admin')).fetchall();return self.send(200,{'workspaces':[dict(w) for w in rows]})
                if method=='POST':
                    d=self.input();wid=c.execute('INSERT INTO workspaces(tenant_id,owner_id,name,created) VALUES(?,?,?,?)',(u['tenant_id'],u['id'],db.text(d,'name',120),db.now())).lastrowid;db.audit(c,u,'create.workspace',wid);return self.send(201,{'id':wid})
            if re.fullmatch(r'/api/workspaces/\d+/members',path):
                wid=int(path.split('/')[3]);w=db.workspace(c,u,wid)
                if method=='GET':return self.send(200,{'members':[dict(m) for m in c.execute('SELECT m.user_id,m.permission,u.name FROM members m JOIN users u ON u.id=m.user_id WHERE workspace_id=?',(wid,))]})
                if method=='POST':
                    if u['role']!='tenant_admin' and w['owner_id']!=u['id']:raise Problem('Only the workspace owner can invite collaborators',403)
                    d=self.input();target=c.execute('SELECT id FROM users WHERE id=? AND tenant_id=? AND active=1',(d.get('user_id'),u['tenant_id'])).fetchone();permission=d.get('permission')
                    if not target or permission not in ('viewer','editor','remove'):raise Problem('Invalid collaborator')
                    c.execute('DELETE FROM members WHERE workspace_id=? AND user_id=?',(wid,target[0]))
                    if permission!='remove':c.execute('INSERT INTO members VALUES(?,?,?)',(wid,target[0],permission))
                    db.audit(c,u,'workspace.member',wid);return self.send(200,{'ok':True})
            if path=='/api/projects':
                if method=='GET':
                    rows=c.execute('SELECT * FROM projects WHERE tenant_id=? ORDER BY updated DESC LIMIT 500',(u['tenant_id'],)).fetchall();out=[]
                    for p in rows:
                        try:db.project(c,u,p['id']);out.append(db.row(p))
                        except Problem:pass
                    return self.send(200,{'projects':out})
                if method=='POST':
                    d=self.input();self.validate_body(c,u,d.get('body',{}));pid=db.create_project(c,u,d);db.audit(c,u,'create.project',pid);return self.send(201,{'id':pid})
            if re.fullmatch(r'/api/projects/\d+',path):
                pid=int(path.split('/')[-1]);p=db.project(c,u,pid,method!='GET')
                if method=='GET':
                    assets=c.execute('SELECT id,name,kind,mime,size,duration FROM assets WHERE project_id=? ORDER BY id DESC',(pid,)).fetchall();return self.send(200,{'project':db.row(p),'assets':[dict(a) for a in assets]})
                if method=='PATCH':
                    d=self.input()
                    if d.get('version')!=p['version']:raise Problem('Project changed. Reload before saving.',409)
                    title=db.text(d,'title',120) if 'title' in d else p['title'];b=d.get('body',db.body(p))
                    self.validate_body(c,u,b)
                    wid=d.get('workspace_id',p['workspace_id']) or None
                    if wid!=p['workspace_id']:
                        if u['role']!='tenant_admin' and p['owner_id']!=u['id']:raise Problem('Only the owner can move this project',403)
                        if wid:db.workspace(c,u,wid,True)
                    vis=d.get('visibility',p['visibility']);remix=d.get('allow_remix',p['allow_remix']);trash=d.get('trashed',p['trashed'])
                    if vis not in ('private','unlisted','public') or remix not in (0,1) or trash not in (0,1):raise Problem('Invalid publication settings')
                    if (vis!=p['visibility'] or remix!=p['allow_remix'] or trash!=p['trashed']) and u['role']!='tenant_admin' and p['owner_id']!=u['id']:raise Problem('Only the owner can publish or trash a project',403)
                    token=(p['share_token'] or secrets.token_urlsafe(24)) if vis=='unlisted' else None
                    c.execute('UPDATE projects SET title=?,body=?,workspace_id=?,visibility=?,share_token=?,allow_remix=?,trashed=?,version=version+1,updated=? WHERE id=? AND version=?',(title,json.dumps(b),wid,vis,token,remix,trash,db.now(),pid,p['version']));db.audit(c,u,'update.project',pid);return self.send(200,{'version':p['version']+1,'share_token':token})
                if method=='DELETE':
                    if not p['trashed']:raise Problem('Move to Trash before permanent deletion')
                    if u['role']!='tenant_admin' and p['owner_id']!=u['id']:raise Problem('Only the owner can delete',403)
                    if c.execute("SELECT 1 FROM jobs WHERE project_id=? AND state IN ('queued','running')",(pid,)).fetchone():raise Problem('Wait for project jobs to finish',409)
                    paths=[media.diskpath(a) for a in c.execute('SELECT * FROM assets WHERE project_id=?',(pid,))]
                    c.execute('DELETE FROM likes WHERE project_id=?',(pid,));c.execute('DELETE FROM assets WHERE project_id=?',(pid,));c.execute("UPDATE projects SET body='{}',title='Deleted project',visibility='private',share_token=NULL,version=version+1 WHERE id=?",(pid,))
                    # Keep a tombstone and ledger/job references for accounting; no media remains.
                    for f in paths:f.unlink(missing_ok=True)
                    db.audit(c,u,'delete.project',pid);return self.send(200,{'ok':True})
            if path=='/api/remix' and method=='POST':
                d=self.input();src=c.execute("SELECT p.* FROM projects p JOIN tenants t ON t.id=p.tenant_id JOIN users u ON u.id=p.owner_id WHERE u.active=1 AND p.id=? AND p.visibility='public' AND p.allow_remix=1 AND p.trashed=0 AND t.status='active'",(d.get('project_id'),)).fetchone()
                if not src:raise Problem('This public project does not allow remixing',403)
                pid=db.create_project(c,u,{'title':src['title']+' · remix','kind':'song','body':{'prompt':db.body(src).get('prompt',''),'lyrics':db.body(src).get('lyrics',''),'remix_source':src['id']}})
                # Explicitly consented copies become tenant-owned; later revocation prevents new remixes.
                copied=[]
                try:
                    for a in c.execute("SELECT * FROM assets WHERE project_id=? AND kind='audio' LIMIT 1",(src['id'],)).fetchall():
                        out=media.newfile(Path(a['path']).suffix[1:]);import shutil;shutil.copyfile(media.diskpath(a),out);copied.append(out);jobs.add_asset(c,u,pid,out,'Remix source','audio',a['mime'])
                except Exception:
                    for f in copied:f.unlink(missing_ok=True)
                    raise
                db.audit(c,u,'remix',pid);return self.send(201,{'id':pid})
            if path=='/api/likes':
                if method=='GET':return self.send(200,{'ids':[r[0] for r in c.execute('SELECT project_id FROM likes WHERE user_id=?',(u['id'],))]})
                if method=='POST':
                    d=self.input();pid=d.get('project_id');public=c.execute("SELECT 1 FROM projects p JOIN tenants t ON t.id=p.tenant_id WHERE p.id=? AND visibility='public' AND trashed=0 AND t.status='active'",(pid,)).fetchone()
                    if not public:db.project(c,u,pid)
                    c.execute('DELETE FROM likes WHERE user_id=? AND project_id=?',(u['id'],pid)) if not d.get('liked') else c.execute('INSERT OR IGNORE INTO likes VALUES(?,?)',(u['id'],pid));return self.send(200,{'ok':True})
            if path=='/api/upload' and method=='POST':
                d=self.input();p=db.project(c,u,d.get('project_id'),True)
                if p['trashed']:raise Problem('Restore the project first')
                if d.get('rights_confirmed') is not True:raise Problem('Confirm that you have permission to use this media')
                name=db.text(d,'name',150)
                try:raw=base64.b64decode(d.get('data',''),validate=True)
                except Exception:raise Problem('Invalid upload')
                if not 1<=len(raw)<=20*1024*1024:raise Problem('Upload must be 1 byte–20 MB',413)
                ext=Path(name).suffix.lower();formats={'.wav':('audio','audio/wav'),'.mp3':('audio','audio/mpeg'),'.ogg':('audio','audio/ogg'),'.m4a':('audio','audio/mp4'),'.webm':('audio','audio/webm'),'.png':('image','image/png'),'.jpg':('image','image/jpeg'),'.jpeg':('image','image/jpeg'),'.mp4':('video','video/mp4')}
                if ext not in formats:raise Problem('Supported uploads: WAV, MP3, OGG, M4A, WebM audio, PNG, JPEG, MP4')
                kind,mime=formats[ext];f=media.newfile(ext[1:]);f.write_bytes(raw)
                try:
                    info,_=media.probe(f);types={s['codec_type'] for s in info['streams']}
                    if kind=='audio' and 'audio' not in types or kind in ('image','video') and 'video' not in types:raise Problem('File contents do not match the selected media type')
                    if kind=='image' and not any(s.get('codec_name') in ('png','mjpeg') for s in info['streams']):raise Problem('Invalid image')
                    if kind=='image' and any(s.get('width',0)*s.get('height',0)>16000000 for s in info['streams']):raise Problem('Image exceeds 16 megapixels')
                    c.execute('BEGIN IMMEDIATE');aid=jobs.add_asset(c,u,p['id'],f,name,kind,mime);db.audit(c,u,'upload',aid)
                except Exception:f.unlink(missing_ok=True);raise
                return self.send(201,{'id':aid})
            if re.fullmatch(r'/api/media/\d+',path) and method=='GET':
                a=db.asset(c,u,int(path.split('/')[-1]));return self.binary(media.diskpath(a),a['mime'],qs.get('download')==['1'])
            if re.fullmatch(r'/api/waveform/\d+',path) and method=='GET':
                a=db.asset(c,u,int(path.split('/')[-1]))
                if a['kind']!='audio':raise Problem('Choose an audio asset')
                return self.send(200,{'peaks':media.waveform(media.diskpath(a))})
            if path=='/api/download-batch' and method=='POST':
                d=self.input();ids=d.get('asset_ids',[])
                if not isinstance(ids,list) or not 1<=len(ids)<=20:raise Problem('Select 1–20 assets')
                assets=[db.asset(c,u,i) for i in ids]
                if sum(a['size'] for a in assets)>100*1024*1024:raise Problem('Archive exceeds 100 MB',413)
                buf=io.BytesIO()
                with zipfile.ZipFile(buf,'w',zipfile.ZIP_STORED) as z:
                    for a in assets:z.write(media.diskpath(a),str(a['id'])+Path(a['path']).suffix)
                raw=buf.getvalue();self.send_response(200);self.headers_common();self.send_header('Content-Type','application/zip');self.send_header('Content-Disposition','attachment; filename="AfricanCreativity.zip"');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
            if path=='/api/jobs':
                if method=='POST':jid=jobs.queue(c,u,self.input());return self.send(202,{'id':jid})
                if method=='GET':
                    rows=c.execute('SELECT id,project_id,kind,state,cost,result,error,created,updated FROM jobs WHERE user_id=? AND tenant_id=? ORDER BY id DESC LIMIT 100',(u['id'],u['tenant_id'])).fetchall()
                    return self.send(200,{'jobs':[{**dict(j),'result':json.loads(j['result']) if j['result'] else None} for j in rows]})
            if re.fullmatch(r'/api/jobs/\d+/cancel',path) and method=='POST':
                jid=int(path.split('/')[3]);c.execute('BEGIN IMMEDIATE');j=c.execute('SELECT * FROM jobs WHERE id=? AND tenant_id=? AND user_id=?',(jid,u['tenant_id'],u['id'])).fetchone()
                if not j:raise Problem('Job not found',404)
                if j['state']!='queued':raise Problem('Only queued jobs can be canceled',409)
                db.refund(c,j,'Canceled by creator');db.audit(c,u,'cancel.job',jid);return self.send(200,{'ok':True})
            if path=='/api/account' and method=='GET':
                t=c.execute('SELECT * FROM tenants WHERE id=?',(u['tenant_id'],)).fetchone();used=c.execute('SELECT coalesce(sum(size),0) FROM assets WHERE tenant_id=?',(u['tenant_id'],)).fetchone()[0]
                ledger=c.execute('SELECT delta,reason,job_id,created FROM ledger WHERE tenant_id=? ORDER BY id DESC LIMIT 100',(u['tenant_id'],)).fetchall()
                return self.send(200,{'tenant':dict(t),'storage_bytes':used,'ledger':[dict(x) for x in ledger]})
            if path=='/api/audit' and method=='GET':
                db.require_role(u,'tenant_admin');return self.send(200,{'events':[dict(x) for x in c.execute('SELECT a.*,u.name FROM audit a LEFT JOIN users u ON u.id=a.actor_id WHERE a.tenant_id=? ORDER BY a.id DESC LIMIT 200',(u['tenant_id'],))]})
            raise Problem('Not found',404)
    def validate_body(self,c,u,b):
        if not isinstance(b,dict) or len(json.dumps(b))>100000:raise Problem('Project data too large')
        if not isinstance(b.get('project_ids',[]),list) or len(b.get('project_ids',[]))>100:raise Problem('A collection can contain at most 100 projects')
        for pid in b.get('project_ids',[]):db.project(c,u,pid)
        for clip in b.get('clips',[]):db.asset(c,u,clip.get('asset_id'))
        for scene in b.get('scenes',[]):
            if scene.get('asset_id'):db.asset(c,u,scene['asset_id'])
        if b.get('audio_id'):db.asset(c,u,b['audio_id'])
    def admin(self,c,u,path,method):
        db.require_role(u,'super_admin')
        if path=='/api/admin/tenants':
            if method=='GET':return self.send(200,{'tenants':[dict(t) for t in c.execute('SELECT t.*,(SELECT count(*) FROM users WHERE tenant_id=t.id) as users,(SELECT coalesce(sum(size),0) FROM assets WHERE tenant_id=t.id) as storage_bytes FROM tenants t ORDER BY id')]})
            if method=='POST':
                d=self.input();name=db.text(d,'name',120);slug=db.text(d,'slug',60)
                if not re.fullmatch('[a-z0-9][a-z0-9-]{1,59}',slug):raise Problem('Tenant code must be 2–60 lowercase letters, digits or hyphens')
                credits=int(db.number(d.get('credits',100),0,1000000));storage=int(db.number(d.get('storage_mb',500),20,100000));plan=d.get('plan','starter')
                if plan not in ('starter','creator','studio'):raise Problem('Invalid plan')
                tid=c.execute('INSERT INTO tenants(name,slug,plan,credits,storage_mb,created) VALUES(?,?,?,?,?,?)',(name,slug,plan,credits,storage,db.now())).lastrowid
                token=secrets.token_urlsafe(32);c.execute("INSERT INTO invitations(tenant_id,token,role,expires) VALUES(?,?,'tenant_admin',?)",(tid,db.digest(token),db.now()+7*86400));db.audit(c,u,'provision.tenant',tid)
                return self.send(201,{'id':tid,'invitation':token,'expires_in_days':7})
        if re.fullmatch(r'/api/admin/tenants/\d+',path) and method=='PATCH':
            d=self.input();tid=int(path.split('/')[-1]);c.execute('BEGIN IMMEDIATE');t=c.execute('SELECT * FROM tenants WHERE id=?',(tid,)).fetchone()
            if not t:raise Problem('Tenant not found',404)
            if t['version']!=d.get('version'):raise Problem('Tenant changed. Reload.',409)
            status=d.get('status',t['status']);plan=d.get('plan',t['plan']);delta=int(db.number(d.get('credit_adjustment',0),-1000000,1000000));storage=int(db.number(d.get('storage_mb',t['storage_mb']),20,100000))
            if status not in ('active','suspended') or plan not in ('starter','creator','studio') or t['credits']+delta<0:raise Problem('Invalid tenant settings')
            c.execute('UPDATE tenants SET status=?,plan=?,credits=credits+?,storage_mb=?,version=version+1 WHERE id=?',(status,plan,delta,storage,tid))
            if delta:c.execute('INSERT INTO ledger(tenant_id,delta,reason,created) VALUES(?,?,?,?)',(tid,delta,'platform adjustment',db.now()))
            if status=='suspended':
                c.execute('DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE tenant_id=?)',(tid,))
                for j in c.execute("SELECT * FROM jobs WHERE tenant_id=? AND state='queued'",(tid,)).fetchall():db.refund(c,j,'Tenant suspended')
            db.audit(c,u,'update.tenant',tid);return self.send(200,{'ok':True})
        if path=='/api/admin/status' and method=='GET':return self.send(200,{'capabilities':providers.capabilities(),'queue':[dict(x) for x in c.execute('SELECT state,count(*) as count FROM jobs GROUP BY state')],'audit':[dict(x) for x in c.execute('SELECT * FROM audit WHERE tenant_id IS NULL ORDER BY id DESC LIMIT 100')]})
        raise Problem('Not found',404)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--host',default='127.0.0.1');ap.add_argument('--port',type=int,default=8096);ap.add_argument('--create-super-admin');args=ap.parse_args();db.init()
    if args.create_super_admin:
        pw=getpass.getpass('New platform password (12+ characters): ')
        if pw!=getpass.getpass('Confirm password: '):raise SystemExit('Passwords do not match')
        with db.connect() as c:c.execute("INSERT INTO users(username,name,password,role,created) VALUES(?,?,?,'super_admin',?)",(args.create_super_admin,args.create_super_admin,db.hash_password(pw),db.now()))
        print('Platform administrator created; sign in and provision a tenant.')
    else:
        jobs.start();ThreadingHTTPServer((args.host,args.port),Handler).serve_forever()
