"""Durable queue. A single worker claims jobs atomically and validates authorization at execution."""
import json,threading,time,shutil,subprocess,tempfile,sys
from pathlib import Path
import open_engines
import database as db,providers,media,addons,engines,youtube_integration as yt
from database import Problem
COSTS={'open_engine':0,'lyrics':1,'prompt':1,'storyboard':2,'speech':3,'music':10,'synth':0,'compose':0,'youtube_upload':0,'edit':0,'mix':0,'video':2,'stems':5,'export':0,'images':5,'ai_motion_video':20,'master':0,'arrange':0,'analyze':0}

def validate_sources(c,u,kind,payload):
    ids=[]
    if payload.get('asset_id'):ids.append(payload['asset_id'])
    if payload.get('audio_id'):ids.append(payload['audio_id'])
    for item in payload.get('clips',[])+payload.get('scenes',[]):
        if item.get('asset_id'):ids.append(item['asset_id'])
    for aid in ids:db.asset(c,u,aid)

def queue(c,u,d):
    p=db.project(c,u,d.get('project_id'),True)
    if p['trashed']:raise Problem('Restore the project first')
    kind=d.get('kind');payload=d.get('payload',{})
    if kind not in COSTS or not isinstance(payload,dict) or len(json.dumps(payload))>100000:raise Problem('Invalid job')
    caps=providers.capabilities();cap={'youtube_upload':'youtube','music':'music','stems':'stems','video':'video_render','edit':'audio_edit','mix':'audio_edit','export':'audio_edit','master':'audio_edit','arrange':'audio_edit','analyze':'audio_edit'}.get(kind,kind)
    if not caps.get(cap):raise Problem('This engine is not configured. See Account → Engine status.',503)
    if kind in ('lyrics','prompt','storyboard'):
        payload={'prompt':db.text(payload,'prompt',6000 if kind!='storyboard' else 12000)}
    if kind in ('images','ai_motion_video'):
        payload={'prompt':db.text(payload,'prompt',2000),'aspect':payload.get('aspect','16:9')}
        if payload['aspect'] not in ('16:9','9:16'):raise Problem('AI scene aspect must be 16:9 or 9:16')
    if kind=='speech':
        payload={'text':db.text(payload,'text',4000),'voice':payload.get('voice','coral')}
        if payload['voice'] not in ('alloy','ash','coral','echo','fable','nova','onyx','sage','shimmer'):raise Problem('Unsupported voice')
    if kind=='youtube_upload':
        payload=yt.validate_upload(c,u,payload)
        if db.asset(c,u,payload['asset_id'])['project_id']!=p['id']:raise Problem('Asset belongs to a different project',403)
    if kind=='compose':
        payload=engines.validate(payload)
        if payload['engine'] not in engines.enabled():raise Problem('Selected local engine is not enabled',503)
    if kind=='open_engine':
        payload=open_engines.validate(payload)
        if not any(m['id']==payload['engine'] and m['ready'] for m in caps['open_models']):raise Problem('Selected self-hosted engine is unavailable',503)
    if kind=='music':
        if not payload.get('instrumental',True):raise Problem('This engine supports instrumental audio only. Singing is not configured.',422)
        model_id=payload.get('engine','musicgen-small')
        if not any(m['id']==model_id and m['ready'] for m in caps['models']) or model_id not in ('musicgen-small','musicgen-medium'):raise Problem('Selected music model is not enabled',503)
        payload={'engine':model_id,'prompt':db.text(payload,'prompt',1000),'duration':db.number(payload.get('duration',10),2,25),'temperature':db.number(payload.get('temperature',1),.1,2),'guidance':db.number(payload.get('guidance',3),1,8)}
    validate_sources(c,u,kind,payload)
    # Daily cap and quota checked in the same transaction as debit and enqueue.
    c.execute('BEGIN IMMEDIATE') if not c.in_transaction else None
    count=c.execute('SELECT count(*) FROM jobs WHERE tenant_id=? AND created>?',(u['tenant_id'],db.now()-86400)).fetchone()[0]
    if count>=200:raise Problem('Tenant daily job limit reached',429)
    if c.execute("SELECT count(*) FROM jobs WHERE tenant_id=? AND state IN ('queued','running')",(u['tenant_id'],)).fetchone()[0]>=10:raise Problem('Tenant queue is full',429)
    cost=COSTS[kind]
    if not c.execute("UPDATE tenants SET credits=credits-? WHERE id=? AND credits>=? AND status='active'",(cost,u['tenant_id'],cost)).rowcount:raise Problem('Insufficient tenant credits',402)
    jid=c.execute('INSERT INTO jobs(tenant_id,user_id,project_id,kind,payload,cost,created,updated) VALUES(?,?,?,?,?,?,?,?)',(u['tenant_id'],u['id'],p['id'],kind,json.dumps(payload),cost,db.now(),db.now())).lastrowid
    if kind=='youtube_upload':yt.reserve_upload(c,u,payload,jid)
    c.execute('INSERT INTO ledger(tenant_id,job_id,delta,reason,created) VALUES(?,?,?,?,?)',(u['tenant_id'],jid,-cost,'reserve',db.now()))
    db.audit(c,u,'queue.'+kind,jid);return jid

def add_asset(c,u,pid,path,name,kind,mime):
    size=path.stat().st_size
    tenant=c.execute('SELECT * FROM tenants WHERE id=?',(u['tenant_id'],)).fetchone()
    used=c.execute('SELECT coalesce(sum(size),0) FROM assets WHERE tenant_id=?',(u['tenant_id'],)).fetchone()[0]
    if size+used>tenant['storage_mb']*1024*1024:raise Problem('Tenant storage limit reached',413)
    duration=media.probe(path)[1] if kind in ('audio','video') else 0
    return c.execute('INSERT INTO assets(tenant_id,owner_id,project_id,name,path,kind,mime,size,duration,created) VALUES(?,?,?,?,?,?,?,?,?,?)',(u['tenant_id'],u['id'],pid,name,path.name,kind,mime,size,duration,db.now())).lastrowid

def execute(j,u):
    p=json.loads(j['payload']);kind=j['kind'];out=None
    def source(aid,expected=None):
        with db.connect() as c:a=db.asset(c,u,aid)
        if expected and a['kind']!=expected:raise Problem('Wrong media type')
        return media.diskpath(a)
    try:
        if kind=='open_engine':
            spec=open_engines.CATALOG[p['engine']]
            out=media.newfile(spec['ext'])
            src=None
            if p['engine']=='whisper':
                with db.connect() as c:a=db.asset(c,u,p['asset_id'])
                if a['kind'] not in ('audio','video'):raise Problem('Choose an audio or video asset')
                src=media.diskpath(a)
            open_engines.render(p,out,src)
            if p['engine']=='whisper':
                result=json.loads(out.read_text());out.unlink(missing_ok=True)
                return {'engine':'whisper',**result},[]
            return {'engine':p['engine'],'method':'self-hosted AI'},[(out,spec['name'],spec['kind'],spec['mime'])]
        if kind=='youtube_upload':return yt.upload(j,u,p),[]
        if kind in ('lyrics','prompt','storyboard'):return {'text':providers.assist(kind,p['prompt'])},[]
        if kind=='analyze':return {'text':addons.analyze(source(p.get('asset_id'),'audio'))},[]
        if kind=='master':
            out=media.newfile('wav');addons.master(source(p.get('asset_id'),'audio'),p,out);return {},[(out,'Loudness master','audio','audio/wav')]
        if kind=='arrange':
            out=media.newfile('wav');clips=p.get('clips',[])
            addons.arrange([(source(clip.get('asset_id'),'audio'),clip) for clip in clips],out)
            return {},[(out,'Section arrangement','audio','audio/wav')]
        if kind=='images':
            out=media.newfile('png');out.write_bytes(providers.image(p));return {},[(out,'Generated scene image','image','image/png')]
        if kind=='ai_motion_video':
            out=media.newfile('mp4')
            def report(vid):
                with db.connect() as c:c.execute('UPDATE jobs SET result=? WHERE id=?',(json.dumps({'provider_job_id':vid}),j['id']))
            out.write_bytes(providers.motion(p,report));return {},[(out,'Generated motion scene','video','video/mp4')]
        if kind=='video':
            out=media.newfile('mp4');scenes=p.get('scenes',[])
            if not isinstance(scenes,list):raise Problem('Invalid scenes')
            selected=[]
            for s in scenes:
                if s.get('asset_id'):
                    with db.connect() as c:a=db.asset(c,u,s['asset_id'])
                    if a['kind'] not in ('image','video'):raise Problem('Select an image or video scene')
                    selected.append((media.diskpath(a),{**s,'resource_kind':a['kind']}))
                else:selected.append((None,s))
            media.video(source(p['audio_id'],'audio') if p.get('audio_id') else None,selected,p,out)
        elif kind=='compose':
            if p['engine'] not in engines.enabled():raise Problem('Selected local engine is disabled',503)
            out=media.newfile('wav');score=engines.render(p,out)
            return {'score':score,'engine':p['engine'],'method':'procedural; not AI'},[(out,engines.CATALOG[p['engine']],'audio','audio/wav')]
        elif kind=='synth':out=media.newfile('wav');media.synth(p,out)
        elif kind=='music':out=media.newfile('wav');providers.music(p,out)
        elif kind=='speech':out=media.newfile('wav');out.write_bytes(providers.speech(p))
        elif kind=='edit':out=media.newfile('wav');media.edit(source(p.get('asset_id'),'audio'),p,out)
        elif kind=='mix':
            out=media.newfile('wav');clips=p.get('clips',[])
            if not isinstance(clips,list) or not 1<=len(clips)<=12:raise Problem('Add 1–12 clips')
            media.mix([(source(clip.get('asset_id'),'audio'),clip) for clip in clips],out)
        elif kind=='export':
            fmt=p.get('format','wav')
            if fmt not in ('wav','mp3'):raise Problem('Choose WAV or MP3')
            out=media.newfile(fmt);media.ff(['-protocol_whitelist','file,pipe','-i',str(source(p.get('asset_id'),'audio')),'-vn','-t','180',str(out)])
        elif kind=='stems':
            src=source(p.get('asset_id'),'audio')
            with tempfile.TemporaryDirectory() as d:
                media.run([sys.executable,'-m','demucs','--two-stems','vocals','-n','htdemucs','-o',d,str(src)],1800)
                files=[]
                for name in ('vocals','no_vocals'):
                    f=list(Path(d).rglob(name+'.wav'))
                    if len(f)!=1:raise Problem('Stem engine returned no audio',502)
                    dest=media.newfile('wav');shutil.copyfile(f[0],dest);files.append((dest,name,'audio','audio/wav'))
                return {},files
        else:raise Problem('Unknown job')
        return {},[(out,kind+' result','video' if kind=='video' else 'audio','video/mp4' if kind=='video' else 'audio/mpeg' if out.suffix=='.mp3' else 'audio/wav')]
    except BaseException:
        if out:out.unlink(missing_ok=True)
        raise

def process_one():
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE');j=c.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY id LIMIT 1").fetchone()
        if not j:return False
        c.execute("UPDATE jobs SET state='running',updated=? WHERE id=?",(db.now(),j['id']))
    files=[]
    try:
        with db.connect() as c:
            u=c.execute('SELECT * FROM users WHERE id=? AND active=1',(j['user_id'],)).fetchone()
            t=c.execute("SELECT * FROM tenants WHERE id=? AND status='active'",(j['tenant_id'],)).fetchone()
            if not u or not t:raise Problem('Account or tenant was suspended',403)
            project=db.project(c,u,j['project_id'],True)
            if project['trashed']:raise Problem('Project is in Trash')
        result,files=execute(j,u)
        with db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            # Authorization must still hold when an expensive provider job finishes.
            u=c.execute('SELECT * FROM users WHERE id=? AND active=1',(j['user_id'],)).fetchone()
            t=c.execute("SELECT id FROM tenants WHERE id=? AND status='active'",(j['tenant_id'],)).fetchone()
            if not u or not t:raise Problem('Access revoked during processing',403)
            project=db.project(c,u,j['project_id'],True)
            if project['trashed']:raise Problem('Project moved to Trash')
            validate_sources(c,u,j['kind'],json.loads(j['payload']))
            previous=c.execute('SELECT result FROM jobs WHERE id=?',(j['id'],)).fetchone()[0]
            if previous:result={**json.loads(previous),**result}
            result['asset_ids']=[add_asset(c,u,j['project_id'],*f) for f in files]
            c.execute("UPDATE jobs SET state='completed',result=?,updated=? WHERE id=?",(json.dumps(result),db.now(),j['id']))
            db.audit(c,u,'complete.'+j['kind'],j['id'])
    except Exception as e:
        print('Job',j['id'],'failed:',type(e).__name__,flush=True)
        for f in files:f[0].unlink(missing_ok=True)
        with db.connect() as c:db.refund(c,j,e.message if isinstance(e,Problem) else 'Processing failed. Check server logs and engine installation.')
    return True

def worker():
    while True:
        if not process_one():time.sleep(.5)
def start():threading.Thread(target=worker,daemon=True,name='creative-worker').start()
