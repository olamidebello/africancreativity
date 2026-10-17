"""Tenant-scoped YouTube OAuth, metadata imports and explicit video publishing."""
import os,json,re,secrets,base64,hashlib,threading,urllib.request,urllib.error,urllib.parse
from pathlib import Path
import database as db,media
from database import Problem
SCOPES='https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly'
_LOCKS={};_GUARD=threading.Lock()
def lock(uid):
    with _GUARD:return _LOCKS.setdefault(uid,threading.RLock())
def configured():
    return all(os.environ.get(k) for k in ('YOUTUBE_CLIENT_ID','YOUTUBE_CLIENT_SECRET','YOUTUBE_REDIRECT_URI')) and os.environ.get('YOUTUBE_REDIRECT_URI','').startswith('https://')
def require_config():
    if not configured():raise Problem('YouTube OAuth is not configured. Ask the platform administrator to install Google client credentials.',503)
def token_path(uid):
    directory=db.DATA/'youtube-tokens';directory.mkdir(mode=0o700,exist_ok=True)
    return directory/(str(int(uid))+'.json')
def read_token(uid):
    try:return json.loads(token_path(uid).read_text())
    except (FileNotFoundError,ValueError):raise Problem('Connect your YouTube account first',409)
def save_token(uid,data):
    path=token_path(uid);tmp=path.with_suffix('.'+secrets.token_hex(8))
    fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        with os.fdopen(fd,'w') as f:json.dump(data,f)
        os.replace(tmp,path)
    finally:tmp.unlink(missing_ok=True)
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):return None
def request(url,data=None,headers=None,method=None,form=False):
    raw=urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode() if isinstance(data,dict) else data
    h=dict(headers or {})
    if isinstance(data,dict):h.setdefault('Content-Type','application/x-www-form-urlencoded' if form else 'application/json')
    req=urllib.request.Request(url,data=raw,headers=h,method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=120) as r:
            body=r.read(2*1024*1024+1)
            if len(body)>2*1024*1024:raise Problem('YouTube response too large',502)
            return r.status,dict(r.headers),body
    except urllib.error.HTTPError as e:
        if e.code==308:return 308,dict(e.headers),b''
        raise Problem('YouTube request failed (HTTP '+str(e.code)+'). Check connection, API quota and channel permissions.',502)
    except (urllib.error.URLError,TimeoutError,OSError):raise Problem('YouTube connection failed. Review upload history before retrying.',502)
def json_request(url,data=None,headers=None,form=False):
    _,_,raw=request(url,data,headers,form=form)
    try:return json.loads(raw)
    except (ValueError,UnicodeDecodeError):raise Problem('YouTube returned an invalid response',502)
def token(uid):
    require_config()
    with lock(uid):
        t=read_token(uid)
        if t.get('expires_at',0)>db.now()+60:return t['access_token']
        if not t.get('refresh_token'):raise Problem('Reconnect YouTube to renew access',409)
        new=json_request('https://oauth2.googleapis.com/token',{'client_id':os.environ['YOUTUBE_CLIENT_ID'],'client_secret':os.environ['YOUTUBE_CLIENT_SECRET'],'grant_type':'refresh_token','refresh_token':t['refresh_token']},form=True)
        if not new.get('access_token'):raise Problem('Reconnect your YouTube account',409)
        t.update(new);t['expires_at']=db.now()+float(new.get('expires_in',3600));save_token(uid,t);return t['access_token']
def api(uid,resource,params):
    return json_request('https://www.googleapis.com/youtube/v3/'+resource+'?'+urllib.parse.urlencode(params),headers={'Authorization':'Bearer '+token(uid)})
def account(c,u):
    db.tenant_user(u)
    a=c.execute('SELECT * FROM youtube_accounts WHERE user_id=? AND tenant_id=?',(u['id'],u['tenant_id'])).fetchone()
    if not a:raise Problem('Connect your YouTube account first',409)
    return a
def start(c,u,accepted):
    require_config();db.tenant_user(u)
    if accepted is not True:raise Problem('Accept the YouTube terms and privacy notice first')
    state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    c.execute('DELETE FROM youtube_oauth WHERE user_id=? OR expires<?',(u['id'],db.now()))
    c.execute('INSERT INTO youtube_oauth(state,user_id,tenant_id,csrf,verifier,expires) VALUES(?,?,?,?,?,?)',(db.digest(state),u['id'],u['tenant_id'],u['csrf'],verifier,db.now()+600))
    return 'https://accounts.google.com/o/oauth2/v2/auth?'+urllib.parse.urlencode(dict(client_id=os.environ['YOUTUBE_CLIENT_ID'],redirect_uri=os.environ['YOUTUBE_REDIRECT_URI'],response_type='code',scope=SCOPES,state=state,access_type='offline',prompt='consent',code_challenge=challenge,code_challenge_method='S256'))
def callback(c,qs):
    require_config();state=qs.get('state',[''])[0]
    if not isinstance(state,str) or len(state)>200:raise Problem('Invalid OAuth state',403)
    c.execute('BEGIN IMMEDIATE')
    row=c.execute('SELECT * FROM youtube_oauth WHERE state=? AND expires>?',(db.digest(state),db.now())).fetchone()
    if not row:raise Problem('YouTube connection expired or already used. Start again.',403)
    c.execute('DELETE FROM youtube_oauth WHERE state=?',(row['state'],));c.commit()
    u=c.execute("SELECT u.* FROM users u JOIN tenants t ON t.id=u.tenant_id JOIN sessions s ON s.user_id=u.id WHERE u.id=? AND u.tenant_id=? AND u.active=1 AND u.role!='super_admin' AND t.status='active' AND s.csrf=? AND s.expires>?",(row['user_id'],row['tenant_id'],row['csrf'],db.now())).fetchone()
    if not u:raise Problem('Sign in and reconnect YouTube',403)
    if qs.get('error'):raise Problem('YouTube authorization was declined. Start again when ready.')
    code=qs.get('code',[''])[0]
    if not code or len(code)>4096:raise Problem('Missing authorization code')
    t=json_request('https://oauth2.googleapis.com/token',dict(client_id=os.environ['YOUTUBE_CLIENT_ID'],client_secret=os.environ['YOUTUBE_CLIENT_SECRET'],redirect_uri=os.environ['YOUTUBE_REDIRECT_URI'],code=code,code_verifier=row['verifier'],grant_type='authorization_code'),form=True)
    if not t.get('access_token') or not t.get('refresh_token'):raise Problem('Offline YouTube access was not granted. Reconnect and approve access.',409)
    if not set(SCOPES.split())<=set(t.get('scope','').split()):raise Problem('Approve both YouTube upload and read permissions',409)
    info=json_request('https://www.googleapis.com/youtube/v3/channels?part=snippet,contentDetails&mine=true',headers={'Authorization':'Bearer '+t['access_token']})
    channels=info.get('items',[])
    if not channels:raise Problem('Create a YouTube channel for this Google account first',409)
    ch=channels[0];t['expires_at']=db.now()+float(t.get('expires_in',3600))
    with lock(u['id']):save_token(u['id'],t)
    c.execute('INSERT INTO youtube_accounts(user_id,tenant_id,channel_id,title,playlist,updated) VALUES(?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET tenant_id=excluded.tenant_id,channel_id=excluded.channel_id,title=excluded.title,playlist=excluded.playlist,updated=excluded.updated',(u['id'],u['tenant_id'],ch['id'],ch['snippet']['title'],ch['contentDetails']['relatedPlaylists']['uploads'],db.now()))
    db.audit(c,u,'youtube.connect','self')
def disconnect(c,u):
    db.tenant_user(u);revoked=False
    with lock(u['id']):
        try:
            t=read_token(u['id'])
            request('https://oauth2.googleapis.com/revoke',{'token':t.get('refresh_token') or t['access_token']},form=True)
            revoked=True
        except Problem:pass
        token_path(u['id']).unlink(missing_ok=True)
        c.execute('DELETE FROM youtube_accounts WHERE user_id=? AND tenant_id=?',(u['id'],u['tenant_id']))
        c.execute('DELETE FROM youtube_oauth WHERE user_id=?',(u['id'],))
        c.execute('DELETE FROM youtube_imports WHERE user_id=? AND tenant_id=?',(u['id'],u['tenant_id']))
        c.execute("DELETE FROM youtube_exports WHERE user_id=? AND tenant_id=? AND state!='uploading'",(u['id'],u['tenant_id']))
    db.audit(c,u,'youtube.disconnect','self')
    return {'ok':True,'revoked':revoked}
def video_id(value):
    if not isinstance(value,str):raise Problem('Enter a YouTube video URL or ID')
    if re.fullmatch(r'[A-Za-z0-9_-]{11}',value):return value
    parsed=urllib.parse.urlparse(value)
    if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port:raise Problem('Use an HTTPS YouTube video link')
    host=(parsed.hostname or '').lower()
    if host=='youtu.be':vid=parsed.path.strip('/')
    elif host in ('youtube.com','www.youtube.com','m.youtube.com'):
        if parsed.path=='/watch':vid=urllib.parse.parse_qs(parsed.query).get('v',[''])[0]
        elif parsed.path.startswith(('/shorts/','/embed/')):vid=parsed.path.split('/')[2]
        else:vid=''
    else:vid=''
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}',vid):raise Problem('Invalid YouTube video link')
    return vid
def import_video(c,u,value):
    account(c,u);vid=video_id(value)
    items=api(u['id'],'videos',dict(part='snippet',id=vid)).get('items',[])
    if not items:raise Problem('Video is unavailable or not accessible to this account',404)
    snippet=items[0]['snippet']
    c.execute('INSERT INTO youtube_imports(user_id,tenant_id,video_id,title,channel_title,created) VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,video_id) DO UPDATE SET title=excluded.title,channel_title=excluded.channel_title,created=excluded.created',(u['id'],u['tenant_id'],vid,snippet['title'],snippet.get('channelTitle',''),db.now()))
    db.audit(c,u,'youtube.import.reference','saved-reference');return {'video_id':vid,'url':'https://www.youtube.com/watch?v='+vid}
def status(c,u):
    db.tenant_user(u);cleanup(c)
    a=c.execute('SELECT channel_id,title FROM youtube_accounts WHERE user_id=? AND tenant_id=?',(u['id'],u['tenant_id'])).fetchone()
    return {'configured':configured(),'account':dict(a) if a else None,
            'imports':[dict(x) for x in c.execute('SELECT id,video_id,title,channel_title,created FROM youtube_imports WHERE user_id=? AND tenant_id=? ORDER BY id DESC LIMIT 100',(u['id'],u['tenant_id']))],
            'exports':[dict(x) for x in c.execute('SELECT job_id,asset_id,channel_id,video_id,state,privacy,created FROM youtube_exports WHERE user_id=? AND tenant_id=? ORDER BY job_id DESC LIMIT 100',(u['id'],u['tenant_id']))]}
def cleanup(c):
    cutoff=db.now()-30*86400
    c.execute('DELETE FROM youtube_imports WHERE created<?',(cutoff,))
    c.execute("DELETE FROM youtube_exports WHERE created<? AND state!='uploading'",(cutoff,))
    for row in c.execute('SELECT user_id FROM youtube_accounts WHERE updated<?',(cutoff,)).fetchall():
        token_path(row['user_id']).unlink(missing_ok=True)
        c.execute('DELETE FROM youtube_accounts WHERE user_id=?',(row['user_id'],))
        c.execute('DELETE FROM youtube_imports WHERE user_id=?',(row['user_id'],))
    c.execute("UPDATE jobs SET result=NULL,payload='{}' WHERE kind='youtube_upload' AND state IN ('completed','failed') AND updated<?",(cutoff,))
    c.execute('DELETE FROM youtube_oauth WHERE expires<?',(db.now(),))
def validate_upload(c,u,p):
    a=account(c,u);asset=db.asset(c,u,p.get('asset_id'))
    db.project(c,u,asset['project_id'],True)
    if asset['kind']!='video' or asset['mime']!='video/mp4':raise Problem('Render or upload an MP4 video before publishing',422)
    if p.get('rights_confirmed') is not True:raise Problem('Confirm rights and permission to publish this video')
    if p.get('privacy','private') not in ('private','unlisted','public'):raise Problem('Choose a valid YouTube privacy setting')
    if type(p.get('made_for_kids')) is not bool:raise Problem('Choose the intended audience')
    title=db.text(p,'title',100);description=db.text(p,'description',5000,False)
    if '<' in title or '>' in title:raise Problem('YouTube titles cannot contain angle brackets')
    return dict(asset_id=asset['id'],title=title,description=description,privacy=p.get('privacy','private'),made_for_kids=p['made_for_kids'],channel_id=a['channel_id'],rights_confirmed=True)
def reserve_upload(c,u,p,jid):
    prior=c.execute("SELECT state FROM youtube_exports WHERE user_id=? AND asset_id=? AND channel_id=? AND state IN ('queued','uploading','uploaded','uncertain')",(u['id'],p['asset_id'],p['channel_id'])).fetchone()
    if prior:raise Problem('This video already has a queued, completed or uncertain upload. Check YouTube history before retrying.',409)
    c.execute("INSERT INTO youtube_exports(job_id,user_id,tenant_id,asset_id,channel_id,state,privacy,created) VALUES(?,?,?,?,?,'queued',?,?)",(jid,u['id'],u['tenant_id'],p['asset_id'],p['channel_id'],p['privacy'],db.now()))
def session_url(value):
    u=urllib.parse.urlparse(value)
    if u.scheme!='https' or u.hostname not in ('www.googleapis.com','upload.youtube.com') or u.port or u.username or u.password or u.fragment:raise Problem('YouTube returned an invalid upload endpoint',502)
    return value
def upload(j,u,p):
    with db.connect() as c:
        a=account(c,u)
        if a['channel_id']!=p['channel_id']:raise Problem('Connected channel changed; queue a new upload',409)
        asset=db.asset(c,u,p['asset_id']);db.project(c,u,asset['project_id'],True)
        row=c.execute('SELECT * FROM youtube_exports WHERE job_id=? AND user_id=?',(j['id'],u['id'])).fetchone()
        if not row or row['state']!='queued':raise Problem('Upload already attempted. Inspect history before retrying.',409)
        c.execute("UPDATE youtube_exports SET state='uploading' WHERE job_id=?",(j['id'],))
    attempted=False
    try:
        access=token(u['id']);path=media.diskpath(asset);size=path.stat().st_size
        if not size:raise Problem('Video is empty',422)
        _,headers,_=request('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status',
            {'snippet':{'title':p['title'],'description':p['description'],'categoryId':'10'},'status':{'privacyStatus':p['privacy'],'selfDeclaredMadeForKids':p['made_for_kids']}},
            {'Authorization':'Bearer '+access,'X-Upload-Content-Type':'video/mp4','X-Upload-Content-Length':str(size)})
        location=session_url(next((v for k,v in headers.items() if k.lower()=='location'),''))
        with db.connect() as c:c.execute('UPDATE youtube_exports SET session_url=? WHERE job_id=?',(location,j['id']))
        offset=0;result=None
        with path.open('rb') as f:
            while offset<size:
                # Recheck access and connection immediately before each external write.
                with db.connect() as c:
                    current=c.execute("SELECT * FROM users WHERE id=? AND active=1",(u['id'],)).fetchone()
                    tenant=c.execute("SELECT id FROM tenants WHERE id=? AND status='active'",(u['tenant_id'],)).fetchone()
                    if not current or not tenant or current['role']=='super_admin' or account(c,current)['channel_id']!=p['channel_id']:raise Problem('YouTube upload access revoked',403)
                    db.project(c,current,asset['project_id'],True)
                chunk=f.read(8*1024*1024);end=offset+len(chunk)-1;attempted=True
                code,heads,raw=request(location,chunk,{'Authorization':'Bearer '+access,'Content-Type':'video/mp4','Content-Range':f'bytes {offset}-{end}/{size}'},method='PUT')
                if code in (200,201):
                    if end+1!=size:raise Problem('Unexpected early upload completion',502)
                    result=json.loads(raw);break
                acknowledged=next((v for k,v in heads.items() if k.lower()=='range'),'')
                if code!=308 or acknowledged!=f'bytes=0-{end}':raise Problem('Upload progress could not be confirmed',502)
                offset=end+1
        vid=(result or {}).get('id','')
        if not re.fullmatch('[A-Za-z0-9_-]{11}',vid):raise Problem('Upload completion was not confirmed',502)
        actual_privacy=result.get('status',{}).get('privacyStatus',p['privacy'])
        if actual_privacy not in ('private','unlisted','public'):actual_privacy=p['privacy']
        with db.connect() as c:c.execute("UPDATE youtube_exports SET state='uploaded',video_id=?,privacy=?,session_url=NULL WHERE job_id=?",(vid,actual_privacy,j['id']))
        return {'youtube_video_id':vid,'youtube_url':'https://www.youtube.com/watch?v='+vid,'privacy':actual_privacy}
    except Exception:
        with db.connect() as c:c.execute("UPDATE youtube_exports SET state=? WHERE job_id=?",('uncertain' if attempted else 'failed',j['id']))
        raise Problem('YouTube upload was not confirmed. Inspect YouTube Studio and upload history before retrying.',502)
