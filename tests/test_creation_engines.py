import unittest, tempfile, os, json, wave
from pathlib import Path
from unittest.mock import patch
import database as db, engines, jobs, providers
from deploy.verify_creation_engines import verify
from deploy.promote_admin import promote

class CreationEngineTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old_data,self.old_db=db.DATA,db.DB
        db.DATA=Path(self.tmp.name);db.DB=db.DATA/'creativity.db';db.init()
        with db.connect() as c:
            c.execute("INSERT INTO tenants(name,slug,created) VALUES('Local','local',?)",(db.now(),))
            c.execute("INSERT INTO users(tenant_id,username,name,password,role,created) VALUES(1,'creator','Creator','unused','tenant_admin',?)",(db.now(),))
            c.execute("INSERT INTO account_profiles(user_id,email,created,updated) VALUES(1,'dobcalldemo@gmail.com',?,?)",(db.now(),db.now()))
    def tearDown(self):
        db.DATA,db.DB=self.old_data,self.old_db;self.tmp.cleanup()
    def test_each_engine_renders_non_silent_wav(self):
        result=verify(list(engines.CATALOG))
        self.assertEqual(len(result),3);self.assertTrue(all(x['verified'] for x in result))
    def test_score_repeatability_limits_and_seed(self):
        p=dict(engine='arpeggio',duration=25,tempo=180,root=71,seed=3)
        a=engines.compose(p);self.assertEqual(a,engines.compose(p));self.assertLessEqual(len(a['notes']),256)
        self.assertNotEqual(a,engines.compose({**p,'seed':4}))
        for engine in engines.CATALOG:
            with self.assertRaises(db.Problem):engines.validate(dict(engine=engine,duration=1000000))
        with self.assertRaises(db.Problem):engines.validate(dict(engine='../../bad'))
    def test_catalog_enablement_and_end_to_end_queue(self):
        with patch.dict(os.environ,{'LOCAL_CREATION_ENGINES':'arpeggio,chord-pad,bassline'}):
            self.assertTrue(providers.capabilities()['compose'])
            for engine in engines.CATALOG:
                with db.connect() as c:
                    u=c.execute('SELECT * FROM users WHERE id=1').fetchone()
                    pid=db.create_project(c,u,dict(title=engine,kind='song'))
                    jid=jobs.queue(c,u,dict(project_id=pid,kind='compose',payload=dict(engine=engine,duration=2)))
                self.assertTrue(jobs.process_one())
                with db.connect() as c:
                    j=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
                    self.assertEqual(j['state'],'completed',j['error']);self.assertEqual(j['cost'],0)
                    result=json.loads(j['result']);self.assertEqual(result['engine'],engine);self.assertTrue(result['score']['notes'])
                    asset=c.execute('SELECT * FROM assets WHERE id=?',(result['asset_ids'][0],)).fetchone()
                    with wave.open(str(db.DATA/'media'/asset['path'])) as wav:self.assertGreater(wav.getnframes(),1000)
            with patch.dict(os.environ,{'LOCAL_CREATION_ENGINES':''}):
                with db.connect() as c:
                    u=c.execute('SELECT * FROM users WHERE id=1').fetchone()
                    with self.assertRaises(db.Problem):jobs.queue(c,u,dict(project_id=pid,kind='compose',payload=dict(engine='bassline')))
    def test_promotion_is_exact_idempotent_and_preserves_ownership(self):
        with db.connect() as c:
            u=c.execute('SELECT * FROM users WHERE id=1').fetchone()
            pid=db.create_project(c,u,dict(title='Private original'))
            c.execute("INSERT INTO sessions(token,user_id,csrf,expires) VALUES('token',1,'csrf',?)",(db.now()+3600,))
        with db.connect() as c:result=promote(c,'DOBCallDemo@gmail.com')
        self.assertTrue(result['changed'])
        with db.connect() as c:
            u=c.execute('SELECT * FROM users WHERE id=1').fetchone()
            self.assertEqual(u['role'],'super_admin');self.assertEqual(u['tenant_id'],1)
            self.assertEqual(c.execute('SELECT count(*) FROM sessions WHERE user_id=1').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT owner_id FROM projects WHERE id=?',(pid,)).fetchone()[0],1)
            with self.assertRaises(db.Problem):db.project(c,u,pid)
            self.assertEqual(c.execute("SELECT count(*) FROM audit WHERE action='platform.promote.user'").fetchone()[0],1)
        with db.connect() as c:self.assertFalse(promote(c,'dobcalldemo@gmail.com')['changed'])
        with self.assertRaises(db.Problem):
            with db.connect() as c:promote(c,'nonexistent@gmail.com')
