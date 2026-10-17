import json, os, tempfile, unittest, wave
from pathlib import Path
from unittest.mock import patch
import database as db
import jobs, open_engines
from database import Problem

class OpenEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.old_data,self.old_db=db.DATA,db.DB
        db.DATA=self.root;db.DB=self.root/'test.db';db.init()
        self.manifest=self.root/'manifest.json'
        self.env=patch.dict(os.environ,{'OPEN_ENGINES_CONFIG':str(self.manifest)});self.env.start()
        self.manifest.write_text(json.dumps({e:{'verified':True,'python':__import__('sys').executable,'cache':str(self.root/'cache')} for e in open_engines.CATALOG}))
        with db.connect() as c:
            for tid in (1,2):
                c.execute('INSERT INTO tenants(id,name,slug,created) VALUES(?,?,?,0)',(tid,'Tenant '+str(tid),'tenant-'+str(tid)))
                c.execute("INSERT INTO users(id,tenant_id,username,name,password,role,created) VALUES(?,?,?,?,?,'creator',0)",(tid,tid,'user'+str(tid),'User','unused'))
            self.user=c.execute('SELECT * FROM users WHERE id=1').fetchone()
            self.pid=db.create_project(c,self.user,{'title':'My creation'})
            other=c.execute('SELECT * FROM users WHERE id=2').fetchone()
            self.other_pid=db.create_project(c,other,{'title':'Private'})
            self.other_asset=c.execute("INSERT INTO assets(tenant_id,owner_id,project_id,name,path,kind,mime,size,duration,created) VALUES(2,2,?,'private','private.wav','audio','audio/wav',12,1,0)",(self.other_pid,)).lastrowid
    def tearDown(self):
        self.env.stop();db.DATA=self.old_data;db.DB=self.old_db;self.tmp.cleanup()
    def queue(self,payload,pid=None):
        with db.connect() as c:return jobs.queue(c,self.user,{'project_id':pid or self.pid,'kind':'open_engine','payload':payload})
    def test_cross_tenant_project_denied(self):
        with self.assertRaises(Problem):self.queue({'engine':'kokoro','prompt':'Hello'},self.other_pid)
    def test_transcription_cannot_read_another_tenant(self):
        with self.assertRaises(Problem):self.queue({'engine':'whisper','asset_id':self.other_asset})
        with db.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM jobs').fetchone()[0],0)
    def test_disabled_engine_cannot_queue(self):
        self.manifest.write_text('{}')
        with self.assertRaises(Problem):self.queue({'engine':'kokoro','prompt':'Hello'})
    def test_selected_engine_must_be_verified(self):
        self.manifest.write_text(json.dumps({'kokoro':{'verified':True,'python':__import__('sys').executable}}))
        with self.assertRaises(Problem):self.queue({'engine':'ace-step','prompt':'A melody'})
    def test_ready_engine_retained_when_latest_repair_is_blocked(self):
        status=Path(open_engines.__file__).parent/'open-engine-status.json'
        with patch.object(open_engines.Path,'read_text',autospec=True) as read:
            read.side_effect=lambda path: json.dumps({'kokoro':{'state':'blocked','message':'GPU unavailable'}}) if path.name=='open-engine-status.json' else self.manifest.read_bytes().decode()
            model=next(m for m in open_engines.catalog() if m['id']=='kokoro')
            self.assertTrue(model['ready']);self.assertEqual(model['state'],'ready');self.assertIn('Latest repair attempt',model['message'])
    def test_unready_engine_shows_specific_installation_failure(self):
        self.manifest.write_text('{}')
        with patch.object(open_engines.Path,'read_text',autospec=True) as read:
            read.side_effect=lambda path: json.dumps({'wan':{'state':'failed','message':'Installation failed at: Verify dependency consistency'}}) if path.name=='open-engine-status.json' else '{}'
            model=next(m for m in open_engines.catalog() if m['id']=='wan')
            self.assertFalse(model['ready']);self.assertEqual(model['state'],'failed');self.assertIn('dependency',model['message'])
    def test_invalid_bounds_and_voice_rejected(self):
        for payload in [{'engine':'ace-step','prompt':'Music','duration':999},{'engine':'kokoro','prompt':'Hi','voice':'../../secret'},{'engine':'wan','prompt':'Hi','seed':float('nan')},{'engine':'flux-schnell','prompt':''}]:
            with self.assertRaises(Problem):open_engines.validate(payload)
    def test_existing_queue_limit_still_applies(self):
        for _ in range(10):self.queue({'engine':'kokoro','prompt':'Hello'})
        with self.assertRaises(Problem) as error:self.queue({'engine':'kokoro','prompt':'Hello'})
        self.assertEqual(error.exception.status,429)
    def test_generated_asset_saved_and_tenant_scoped(self):
        jid=self.queue({'engine':'kokoro','prompt':'Hello'})
        def fake_render(p,out,source=None):
            with wave.open(str(out),'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\x01\x01'*24000)
            return open_engines.CATALOG[p['engine']]
        with patch.object(open_engines,'render',side_effect=fake_render):self.assertTrue(jobs.process_one())
        with db.connect() as c:
            j=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone();self.assertEqual(j['state'],'completed')
            asset=c.execute('SELECT * FROM assets WHERE tenant_id=1').fetchone();self.assertEqual(asset['tenant_id'],1);self.assertEqual(asset['project_id'],self.pid)
            other=c.execute('SELECT * FROM users WHERE id=2').fetchone()
            with self.assertRaises(Problem):db.asset(c,other,asset['id'])
    def test_failure_refund_is_exactly_once(self):
        jid=self.queue({'engine':'kokoro','prompt':'Hello'})
        with patch.object(open_engines,'render',side_effect=Problem('GPU unavailable')):jobs.process_one()
        with db.connect() as c:
            j=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone();db.refund(c,j,'again')
            self.assertEqual(j['state'],'failed')
            self.assertEqual(c.execute("SELECT count(*) FROM ledger WHERE job_id=? AND reason='refund'",(jid,)).fetchone()[0],1)
    def test_provider_credentials_not_inherited_by_model_runner(self):
        out=self.root/'out.wav';captured={}
        class FakeProcess:
            returncode=0
            def communicate(self,data,timeout):out.write_bytes(b'0'*100)
        def popen(*args,**kwargs):captured.update(kwargs);return FakeProcess()
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-do-not-forward'}),patch.object(open_engines.subprocess,'Popen',side_effect=popen):
            open_engines.render({'engine':'kokoro','prompt':'Hello'},out)
        self.assertNotIn('OPENAI_API_KEY',captured['env'])
        self.assertTrue(captured['start_new_session'])
    def test_subtitle_result_is_saved_without_public_asset(self):
        # An allowed audio source is resolved from the database, never a browser path.
        with db.connect() as c:
            aid=c.execute("INSERT INTO assets(tenant_id,owner_id,project_id,name,path,kind,mime,size,duration,created) VALUES(1,1,?,'source','source.wav','audio','audio/wav',12,1,0)",(self.pid,)).lastrowid
        (self.root/'media'/'source.wav').write_bytes(b'audio')
        jid=self.queue({'engine':'whisper','asset_id':aid})
        def fake(p,out,source=None):
            self.assertEqual(source.name,'source.wav');out.write_text(json.dumps({'text':'Hello','srt':'1\n00:00:00,000 --> 00:00:01,000\nHello','language':'en'}))
        with patch.object(open_engines,'render',side_effect=fake):jobs.process_one()
        with db.connect() as c:
            j=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone();self.assertEqual(j['state'],'completed');self.assertIn('srt',json.loads(j['result']))
            self.assertEqual(c.execute('SELECT count(*) FROM assets WHERE tenant_id=1').fetchone()[0],1)
if __name__=='__main__':unittest.main()
