"""Idempotently publish three original, synthetic instrumentals; no external API calls."""
import json,secrets,sys,wave
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import database as db,media

SAMPLES=[
 ('sunrise-keys','Sunrise Keys · Sample',[60,64,67,72,67,64,62,65,69,74,69,65],105,'sine'),
 ('evening-arpeggio','Evening Arpeggio · Sample',[57,60,64,69,64,60,55,59,62,67,62,59],90,'triangle'),
 ('bright-horizon','Bright Horizon · Sample',[60,62,64,67,69,67,64,62,65,69,72,69],120,'sine'),
]

def seed():
    # init() belongs to application startup, not a live seed operation: it also
    # recovers interrupted jobs. Deployment initializes/migrates while stopped.
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        tenant=c.execute("SELECT * FROM tenants WHERE slug='africa-creativity-samples'").fetchone()
        if tenant:
            tid=tenant['id']
            user=c.execute("SELECT * FROM users WHERE tenant_id=? AND username='sample-instrumentals'",(tid,)).fetchone()
            if not user:raise RuntimeError('Sample namespace exists without its expected owner; review manually')
        else:
            # A random, unpublished password keeps this public sample owner from
            # being a shared default-login account. It has no platform role.
            if c.execute("SELECT 1 FROM users WHERE username='sample-instrumentals'").fetchone():raise RuntimeError('Reserved sample username is already used; review manually')
            tid=c.execute("INSERT INTO tenants(name,slug,credits,storage_mb,created) VALUES('Africa Creativity Samples','africa-creativity-samples',0,20,?)",(db.now(),)).lastrowid
            uid=c.execute("INSERT INTO users(tenant_id,username,name,password,role,created) VALUES(?,?,'Africa Creativity · Original Samples',?,'creator',?)",(tid,'sample-instrumentals',db.hash_password(secrets.token_urlsafe(48)),db.now())).lastrowid
            user=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        published=[]
        for key,title,pitches,tempo,waveform in SAMPLES:
            marker='sample-release:'+key
            project=c.execute('SELECT * FROM projects WHERE tenant_id=? AND owner_id=? AND share_token=?',(tid,user['id'],marker)).fetchone()
            if not project:
                body=json.dumps({'sample_release':True,'sample_key':key,'description':'Original locally synthesized instrumental demonstration. No sung vocals, impersonation, external artist recording or paid generation.'})
                pid=c.execute("INSERT INTO projects(tenant_id,owner_id,kind,title,body,visibility,share_token,allow_remix,created,updated) VALUES(?,?,'song',?,?,'public',?,0,?,?)",(tid,user['id'],title,body,marker,db.now(),db.now())).lastrowid
            else:
                pid=project['id']
                if project['trashed'] or project['visibility']!='public':continue # Respect an operator's removal.
            asset=c.execute('SELECT * FROM assets WHERE project_id=?',(pid,)).fetchone()
            if not asset or not (db.DATA/'media'/asset['path']).is_file():
                path=media.newfile('wav')
                notes=[{'pitch':pitch,'start':i*.5,'duration':.46,'velocity':.55} for i,pitch in enumerate(pitches*2)]
                media.synth({'tempo':tempo,'waveform':waveform,'notes':notes},path)
                with wave.open(str(path)) as w:duration=w.getnframes()/w.getframerate()
                if asset:c.execute('DELETE FROM assets WHERE id=?',(asset['id'],))
                c.execute('INSERT INTO assets(tenant_id,owner_id,project_id,name,path,kind,mime,size,duration,created) VALUES(?,?,?,?,?,?,?,?,?,?)',(tid,user['id'],pid,title+'.wav',path.name,'audio','audio/wav',path.stat().st_size,duration,db.now()))
                db.audit(c,user,'publish.sample',pid)
            published.append(pid)
        return published

if __name__=='__main__':print(json.dumps({'sample_release_ids':seed()}))
