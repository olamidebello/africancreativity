import unittest,tempfile,threading,json,urllib.request,urllib.error,http.cookiejar,base64,wave,io,os,time
from pathlib import Path
from unittest.mock import patch
import sys,sqlite3
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import database as db,server,jobs,media,providers
from http.server import ThreadingHTTPServer

class Client:
    def __init__(self,port):self.base='http://127.0.0.1:'+str(port);self.csrf='';self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(self,path,method='GET',data=None):
        headers={'Content-Type':'application/json','X-Requested-With':'AfricanCreativity','X-CSRF-Token':self.csrf}
        req=urllib.request.Request(self.base+'/api/'+path,data=json.dumps(data).encode() if data is not None else None,headers=headers,method=method)
        try:r=self.opener.open(req)
        except urllib.error.HTTPError as e:r=e
        raw=r.read()
        return r.status,json.loads(raw) if r.headers.get_content_type()=='application/json' else raw
    def login(self,name):
        status,d=self.call('login','POST',dict(username=name,password='test-password-123'))
        assert status==200,(status,d)
        self.csrf=d['csrf'];return self

class PlatformTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();db.DATA=Path(cls.tmp.name);db.DB=db.DATA/'test.db';db.init()
        with db.connect() as c:
            for name in ['alpha','beta']:c.execute('INSERT INTO tenants(name,slug,created) VALUES(?,?,?)',(name,name,db.now()))
            for tenant,name,role in [(None,'platform','super_admin'),(1,'alice','tenant_admin'),(1,'editor','creator'),(1,'viewer','creator'),(2,'bob','tenant_admin')]:c.execute('INSERT INTO users(tenant_id,username,name,password,role,created) VALUES(?,?,?,?,?,?)',(tenant,name,name,db.hash_password('test-password-123'),role,db.now()))
        cls.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.port=cls.http.server_address[1];threading.Thread(target=cls.http.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.tmp.cleanup()
    def setUp(self):
        with db.connect() as c:c.execute("DELETE FROM login_limits WHERE ip LIKE 'register:%'")
        self.a=Client(self.port).login('alice');self.b=Client(self.port).login('bob');self.admin=Client(self.port).login('platform')
    def project(self,client=None,kind='song',body=None):
        status,d=(client or self.a).call('projects','POST',dict(title='Test idea',kind=kind,body=body or {}));self.assertEqual(status,201,d);return d['id']
    def upload(self,pid):
        buf=io.BytesIO()
        with wave.open(buf,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b'\0\0'*8000)
        s,d=self.a.call('upload','POST',dict(project_id=pid,name='test.wav',data=base64.b64encode(buf.getvalue()).decode(),rights_confirmed=True));self.assertEqual(s,201,d);return d['id']
    def patch(self,pid,**changes):
        p=self.a.call('projects/'+str(pid))[1]['project'];return self.a.call('projects/'+str(pid),'PATCH',dict(version=p['version'],**changes))
    def test_platform_management_metadata_and_permissions(self):
        for endpoint,key in [('overview','tenants'),('users','users'),('invitations','invitations'),('jobs','jobs'),('ledger','ledger'),('audit','events')]:
            status,d=self.admin.call('admin/'+endpoint);self.assertEqual(status,200,d);self.assertIn(key,d)
            self.assertEqual(self.a.call('admin/'+endpoint)[0],403)
            self.assertEqual(Client(self.port).call('admin/'+endpoint)[0],401)
        users=self.admin.call('admin/users')[1]['users']
        self.assertFalse(any('password' in x or 'email' in x for x in users))
        self.assertFalse(any('payload' in x or 'result' in x for x in self.admin.call('admin/jobs')[1]['jobs']))
        self.assertFalse(any('token' in x for x in self.admin.call('admin/invitations')[1]['invitations']))

    def test_platform_member_controls_protect_identity_and_last_admin(self):
        users=self.admin.call('admin/users')[1]['users'];alice=next(x for x in users if x['username']=='alice');platform=next(x for x in users if x['username']=='platform');editor=next(x for x in users if x['username']=='editor')
        self.assertEqual(self.admin.call('admin/users/'+str(platform['id']),'PATCH',{'active':0})[0],403)
        self.assertEqual(self.admin.call('admin/users/'+str(alice['id']),'PATCH',{'role':'creator'})[0],409)
        self.assertEqual(self.a.call('admin/users/'+str(editor['id']),'PATCH',{'role':'tenant_admin'})[0],403)
        bad=Client(self.port).login('platform');bad.csrf='bad'
        self.assertEqual(bad.call('admin/users/'+str(editor['id']),'PATCH',{'active':0})[0],403)
        self.assertEqual(self.admin.call('admin/users/'+str(editor['id']),'PATCH',{'active':0})[0],200)
        self.assertEqual(Client(self.port).login('alice').call('me')[0],200)
        disabled=Client(self.port)
        self.assertEqual(disabled.call('login','POST',dict(username='editor',password='test-password-123'))[0],401)
        self.assertEqual(self.admin.call('admin/users/'+str(editor['id']),'PATCH',{'active':1})[0],200)
        self.assertEqual(Client(self.port).login('editor').call('me')[0],200)

    def test_platform_can_reissue_and_revoke_invitation(self):
        status,d=self.admin.call('admin/tenants/2/invitations','POST',{'role':'tenant_admin'});self.assertEqual(status,201,d)
        records=self.admin.call('admin/invitations')[1]['invitations'];iid=max(x['id'] for x in records if x['tenant_id']==2)
        self.assertEqual(self.admin.call('admin/invitations/'+str(iid),'DELETE')[0],200)
        with db.connect() as c:
            invite=c.execute('SELECT * FROM invitations WHERE id=?',(iid,)).fetchone();self.assertEqual(invite['used'],1);self.assertEqual(invite['token'],db.digest(d['token']))
        self.assertEqual(self.admin.call('admin/tenants/999999/invitations','POST',{})[0],404)

    def test_platform_cancel_refunds_queued_job_exactly_once(self):
        pid=self.project()
        with db.connect() as c:
            before=c.execute('SELECT credits FROM tenants WHERE id=1').fetchone()[0]
            c.execute('UPDATE tenants SET credits=credits-3 WHERE id=1')
            uid=c.execute("SELECT id FROM users WHERE username='alice'").fetchone()[0]
            jid=c.execute("INSERT INTO jobs(tenant_id,user_id,project_id,kind,payload,cost,created,updated) VALUES(1,?,?,'speech','{}',3,?,?)",(uid,pid,db.now(),db.now())).lastrowid
        self.assertEqual(self.a.call('admin/jobs/'+str(jid)+'/cancel','POST',{})[0],403)
        self.assertEqual(self.admin.call('admin/jobs/'+str(jid)+'/cancel','POST',{})[0],200)
        self.assertEqual(self.admin.call('admin/jobs/'+str(jid)+'/cancel','POST',{})[0],409)
        with db.connect() as c:
            self.assertEqual(c.execute('SELECT credits FROM tenants WHERE id=1').fetchone()[0],before)
            self.assertEqual(c.execute("SELECT count(*) FROM ledger WHERE job_id=? AND reason='refund'",(jid,)).fetchone()[0],1)
        events=self.admin.call('admin/audit')[1]['events'];self.assertTrue(any(x['action']=='platform.cancel.job' and x['resource']==str(jid) for x in events))

    def test_tenant_isolation_and_platform_no_chart_access(self):
        p=self.project();self.assertEqual(self.b.call('projects/'+str(p))[0],404);self.assertEqual(self.admin.call('projects')[0],403)
        self.assertNotIn(p,[x['id'] for x in self.b.call('projects')[1]['projects']])
    def test_csrf_and_get_mutation_denial(self):
        c=Client(self.port).login('alice');c.csrf='bad';self.assertEqual(c.call('projects','POST',dict(title='bad'))[0],403);self.assertEqual(c.call('logout')[0],404)
    def test_committed_state_is_visible_before_success_response(self):
        # Delay the context-manager commit so a response-before-commit race is deterministic.
        class DelayedExit(sqlite3.Connection):
            def __exit__(self,*args):
                time.sleep(.08)
                return super().__exit__(*args)
        def delayed_connect():
            c=sqlite3.connect(db.DB,timeout=20,factory=DelayedExit)
            c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c
        with patch.object(db,'connect',side_effect=delayed_connect):
            pid=self.project()
            self.assertEqual(self.a.call('projects/'+str(pid))[0],200)
            aid=self.upload(pid)
            self.assertEqual(self.a.call('media/'+str(aid))[0],200)
            status,result=self.patch(pid,title='Committed title')
            self.assertEqual(status,200,result)
            self.assertEqual(self.a.call('projects/'+str(pid),'PATCH',dict(version=1,title='Stale edit'))[0],409)

    def test_stale_version(self):
        p=self.project();self.patch(p,title='Changed');self.assertEqual(self.a.call('projects/'+str(p),'PATCH',dict(title='Stale',version=1))[0],409)
    def test_upload_permission_and_media_range(self):
        p=self.project();aid=self.upload(p);self.assertEqual(self.b.call('media/'+str(aid))[0],404)
        req=urllib.request.Request(self.a.base+'/api/media/'+str(aid),headers={'Range':'bytes=0-15'});r=self.a.opener.open(req);self.assertEqual(r.status,206);self.assertEqual(len(r.read()),16)
    def test_workspace_viewer_cannot_edit(self):
        wid=self.a.call('workspaces','POST',dict(name='Shared'))[1]['id'];users=self.a.call('users')[1]['users'];viewer=next(u for u in users if u['username']=='viewer')
        self.a.call(f'workspaces/{wid}/members','POST',dict(user_id=viewer['id'],permission='viewer'));pid=self.a.call('projects','POST',dict(title='Shared song',workspace_id=wid))[1]['id'];v=Client(self.port).login('viewer');self.assertEqual(v.call(f'projects/{pid}')[0],200);self.assertEqual(v.call(f'projects/{pid}','PATCH',dict(version=1,title='No'))[0],403)
    def test_cross_tenant_workspace_and_assets_rejected(self):
        wid=self.b.call('workspaces','POST',dict(name='Foreign'))[1]['id'];self.assertEqual(self.a.call('projects','POST',dict(title='No',workspace_id=wid))[0],404)
        p=self.project();aid=self.upload(p);self.assertEqual(self.b.call('projects','POST',dict(title='No',body={'clips':[{'asset_id':aid}]}))[0],404)
    def test_invitation_single_use(self):
        token=self.a.call('invitations','POST',dict(role='creator'))[1]['token'];c=Client(self.port);data=dict(token=token,name='Invited',username='invited'+str(db.now()),password='new-password-123');self.assertEqual(c.call('accept-invitation','POST',data)[0],201);self.assertEqual(c.call('accept-invitation','POST',data)[0],400)
    def test_platform_provision_and_suspend(self):
        s,d=self.admin.call('admin/tenants','POST',dict(name='New label',slug='label-'+str(int(db.now()*1000000)),credits=50));self.assertEqual(s,201);tid=d['id'];invite=d['invitation'];c=Client(self.port);name='newadmin'+str(tid);self.assertEqual(c.call('accept-invitation','POST',dict(token=invite,username=name,name='New admin',password='test-password-123'))[0],201);c.login(name)
        self.assertEqual(self.admin.call('admin/tenants/'+str(tid),'PATCH',dict(version=1,status='suspended'))[0],200);self.assertEqual(c.call('me')[0],401)
    def test_queue_synth_creates_real_wav(self):
        pid=self.project();s,d=self.a.call('jobs','POST',dict(project_id=pid,kind='synth',payload={'notes':[{'pitch':60,'start':0,'duration':.5}]}));self.assertEqual(s,202,d)
        while jobs.process_one():pass
        j=next(x for x in self.a.call('jobs')[1]['jobs'] if x['id']==d['id']);self.assertEqual(j['state'],'completed',j);aid=j['result']['asset_ids'][0];self.assertTrue(self.a.call('media/'+str(aid))[1].startswith(b'RIFF'))
    def test_failed_job_refunds_exactly_once(self):
        pid=self.project();before=self.a.call('account')[1]['tenant']['credits']
        with patch.object(providers,'capabilities',return_value={**providers.capabilities(),'speech':True}),patch.object(providers,'speech',side_effect=db.Problem('Provider unavailable',502)):
            jid=self.a.call('jobs','POST',dict(project_id=pid,kind='speech',payload={'text':'Hello'}))[1]['id'];self.assertEqual(self.a.call('account')[1]['tenant']['credits'],before-3)
            jobs.process_one();jobs.process_one()
        self.assertEqual(self.a.call('account')[1]['tenant']['credits'],before)
        ledger=self.a.call('account')[1]['ledger'];self.assertEqual(len([e for e in ledger if e['job_id']==jid and e['reason']=='refund']),1)
    def test_insufficient_credits_no_enqueue(self):
        pid=self.project(self.b)
        with db.connect() as c:c.execute('UPDATE tenants SET credits=0 WHERE id=2')
        with patch.object(providers,'capabilities',return_value={**providers.capabilities(),'speech':True}):self.assertEqual(self.b.call('jobs','POST',dict(project_id=pid,kind='speech',payload={'text':'Hi'}))[0],402)
        with db.connect() as c:c.execute('UPDATE tenants SET credits=100 WHERE id=2')
    def test_unconfigured_music_cannot_claim_success(self):
        pid=self.project()
        with patch.dict(os.environ,{'MUSICGEN_ENABLED':'0'}):self.assertEqual(self.a.call('jobs','POST',dict(project_id=pid,kind='music',payload={'prompt':'Drums'}))[0],503)
    def test_publication_revoke_and_unlisted(self):
        pid=self.project();aid=self.upload(pid);guest=Client(self.port);self.assertEqual(guest.call('public-media/'+str(aid))[0],404)
        self.patch(pid,visibility='unlisted');p=self.a.call('projects/'+str(pid))[1]['project'];key=p['share_token'];self.assertEqual(guest.call('public/'+key)[0],200);self.assertEqual(guest.call(f'public-media/{aid}?key={key}')[0],200);self.assertEqual(guest.call('public/'+str(pid))[0],404)
        self.patch(pid,visibility='private');self.assertEqual(guest.call('public/'+key)[0],404)
    def test_remix_requires_explicit_permission(self):
        pid=self.project();self.upload(pid);self.patch(pid,visibility='public');self.assertEqual(self.b.call('remix','POST',dict(project_id=pid))[0],403);self.patch(pid,allow_remix=1);s,d=self.b.call('remix','POST',dict(project_id=pid));self.assertEqual(s,201,d);self.assertEqual(self.b.call('projects/'+str(d['id']))[1]['project']['tenant_id'],2)
    def test_audio_edit_and_mix(self):
        pid=self.project();aid=self.upload(pid)
        for kind,payload in [('edit',{'asset_id':aid,'end':.8,'pitch':2,'fade_out':.1,'effects':[{'type':'compressor','amount':.5}]}),('mix',{'clips':[{'asset_id':aid,'duration':.5,'offset':.1,'volume':.5,'pan':-.5}]})]:
            s,d=self.a.call('jobs','POST',dict(project_id=pid,kind=kind,payload=payload));self.assertEqual(s,202);jobs.process_one();j=next(x for x in self.a.call('jobs')[1]['jobs'] if x['id']==d['id']);self.assertEqual(j['state'],'completed',j)
    def test_video_real_mp4_and_caption(self):
        pid=self.project(kind='video');s,d=self.a.call('jobs','POST',dict(project_id=pid,kind='video',payload={'aspect':'9:16','scenes':[{'duration':2,'subtitle':'Creative test: 100% original'}]}));self.assertEqual(s,202,d);jobs.process_one();j=next(x for x in self.a.call('jobs')[1]['jobs'] if x['id']==d['id']);self.assertEqual(j['state'],'completed',j);raw=self.a.call('media/'+str(j['result']['asset_ids'][0]))[1];self.assertIn(b'ftyp',raw[:32])
    def test_public_collection_exposes_only_separately_published_members(self):
        song=self.project();collection=self.project(kind='playlist',body={'project_ids':[song]});self.patch(collection,visibility='public');guest=Client(self.port)
        self.assertEqual(guest.call('public/'+str(collection))[1]['tracks'],[])
        self.patch(song,visibility='public');tracks=guest.call('public/'+str(collection))[1]['tracks'];self.assertEqual([x['id'] for x in tracks],[song])
        self.patch(song,visibility='private');self.assertEqual(guest.call('public/'+str(collection))[1]['tracks'],[])
    def test_trash_removes_public_access(self):
        pid=self.project();aid=self.upload(pid);self.patch(pid,visibility='public',trashed=1);self.assertEqual(Client(self.port).call('public/'+str(pid))[0],404);self.assertEqual(self.a.call('projects/'+str(pid),'DELETE')[0],200);self.assertEqual(self.a.call('media/'+str(aid))[0],404)
    def test_audio_addon_master_arrange_and_measurements(self):
        pid=self.project();aid=self.upload(pid)
        for kind,payload in [('master',{'asset_id':aid,'loudness':-16}),('arrange',{'clips':[{'asset_id':aid,'trim':0,'duration':.3},{'asset_id':aid,'trim':.4,'duration':.2}]}),('analyze',{'asset_id':aid})]:
            status,d=self.a.call('jobs','POST',dict(project_id=pid,kind=kind,payload=payload));self.assertEqual(status,202,d);jobs.process_one()
            result=next(j for j in self.a.call('jobs')[1]['jobs'] if j['id']==d['id']);self.assertEqual(result['state'],'completed',result)
            if kind=='analyze':self.assertEqual(result['result']['text']['duration_seconds'],1);self.assertIsNone(result['result']['text']['estimated_bpm'])
            else:self.assertTrue(result['result']['asset_ids'])
    def test_cancel_queued_job_refunds_and_cannot_cancel_twice(self):
        pid=self.project();before=self.a.call('account')[1]['tenant']['credits']
        with patch.object(providers,'capabilities',return_value={**providers.capabilities(),'speech':True}):
            jid=self.a.call('jobs','POST',dict(project_id=pid,kind='speech',payload={'text':'Hello'}))[1]['id']
        self.assertEqual(self.a.call(f'jobs/{jid}/cancel','POST',{})[0],200)
        self.assertEqual(self.a.call(f'jobs/{jid}/cancel','POST',{})[0],409)
        self.assertEqual(self.a.call('account')[1]['tenant']['credits'],before)
    def test_cross_tenant_job_source_denied_before_queue(self):
        pid=self.project();aid=self.upload(pid);foreign=self.project(self.b)
        status,_=self.b.call('jobs','POST',dict(project_id=foreign,kind='edit',payload={'asset_id':aid}))
        self.assertEqual(status,404)
    def test_invalid_audio_is_rejected(self):
        pid=self.project();status,_=self.a.call('upload','POST',dict(project_id=pid,name='fake.mp3',data=base64.b64encode(b'#EXTM3U\nfile:///etc/passwd').decode(),rights_confirmed=True))
        self.assertEqual(status,422)
    def test_quota_blocks_upload(self):
        pid=self.project()
        with db.connect() as c:c.execute('UPDATE tenants SET storage_mb=0 WHERE id=1')
        try:
            buf=io.BytesIO()
            with wave.open(buf,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b'\0\0'*80)
            s,_=self.a.call('upload','POST',dict(project_id=pid,name='small.wav',data=base64.b64encode(buf.getvalue()).decode(),rights_confirmed=True));self.assertEqual(s,413)
        finally:
            with db.connect() as c:c.execute('UPDATE tenants SET storage_mb=500 WHERE id=1')

    def registration(self,username='new-artist',password=' signup-password-123 '):
        return dict(username=username,email=username.lower()+'@example.test',name='New Artist',password=password,password_confirmation=password,phone='+1 555 0100',country='Nigeria',workspace_name='Artist Studio')
    def test_public_signup_persists_private_workspace_and_session(self):
        client=Client(self.port)
        s,d=client.call('register','POST',self.registration())
        self.assertEqual(s,201,d);client.csrf=d['csrf']
        s,me=client.call('me');self.assertEqual(s,200)
        self.assertEqual(me['user']['role'],'tenant_admin');self.assertEqual(me['tenant']['credits'],0)
        self.assertEqual(me['tenant']['storage_mb'],100)
        self.assertEqual(len(client.call('workspaces')[1]['workspaces']),1)
        pid=self.project(client);self.assertEqual(self.a.call('projects/'+str(pid))[0],404)
        self.assertEqual(client.call('admin/tenants')[0],403)
        self.assertEqual(client.call('logout','POST',{})[0],200)
        self.assertEqual(client.call('me')[0],401)
        status,result=client.call('login','POST',dict(username='NEW-ARTIST',password=' signup-password-123 '))
        self.assertEqual(status,200,result)
    def test_signup_rejects_mismatch_and_duplicate_without_orphan_tenant(self):
        client=Client(self.port)
        with db.connect() as c:before=c.execute('SELECT count(*) FROM tenants').fetchone()[0]
        data=self.registration('ALICE');s,_=client.call('register','POST',data);self.assertEqual(s,409)
        data=self.registration('unused-artist');data['password_confirmation']='different'
        self.assertEqual(client.call('register','POST',data)[0],400)
        with db.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM tenants').fetchone()[0],before)
    def test_signup_ignores_requested_admin_role_and_initial_credits(self):
        client=Client(self.port);data=self.registration('bounded-artist');data.update(role='super_admin',credits=100000,tenant_id=1)
        s,d=client.call('register','POST',data);self.assertEqual(s,201,d)
        me=client.call('me')[1];self.assertEqual(me['user']['role'],'tenant_admin');self.assertNotEqual(me['tenant']['id'],1);self.assertEqual(me['tenant']['credits'],0)
    def test_signup_requires_application_request_header(self):
        req=urllib.request.Request(Client(self.port).base+'/api/register',data=json.dumps(self.registration()).encode(),headers={'Content-Type':'application/json'},method='POST')
        with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(req)
        self.assertEqual(caught.exception.code,403)
    def test_failed_login_limiter_is_scoped_to_client_and_username(self):
        client=Client(self.port)
        for _ in range(15):self.assertEqual(client.call('login','POST',dict(username='not-a-user',password='wrong-password'))[0],401)
        self.assertEqual(client.call('login','POST',dict(username='not-a-user',password='wrong-password'))[0],429)
        self.assertEqual(client.call('login','POST',dict(username='alice',password='test-password-123'))[0],200)
    def test_password_spaces_from_invitation_survive_login(self):
        _,invite=self.a.call('invitations','POST',dict(role='creator'))
        client=Client(self.port);password=' invitation-password-123 '
        s,d=client.call('accept-invitation','POST',dict(token=invite['token'],name='Space Artist',username='space-artist',password=password))
        self.assertEqual(s,201,d)
        self.assertEqual(client.call('login','POST',dict(username='space-artist',password=password))[0],200)
        self.assertEqual(client.call('login','POST',dict(username='space-artist',password=password.strip()))[0],401)

    def test_explore_page_is_public_without_a_session(self):
        with urllib.request.urlopen(Client(self.port).base+'/explore') as response:
            self.assertEqual(response.status,200)
            self.assertIn(b'id="public-explore"',response.read())
        status,data=Client(self.port).call('explore')
        self.assertEqual(status,200);self.assertIsInstance(data['projects'],list)

    def test_registration_email_login_profile_and_optional_username(self):
        client=Client(self.port);data=self.registration('mail-artist');data.pop('username');data['email']='EMAIL-ARTIST@example.test'
        status,result=client.call('register','POST',data);self.assertEqual(status,201,result);client.csrf=result['csrf']
        profile=client.call('profile')[1];self.assertEqual(profile['email'],'email-artist@example.test');self.assertEqual(profile['phone'],'+1 555 0100')
        self.assertEqual(client.call('me')[1]['tenant']['name'],'Artist Studio')
        self.assertEqual(client.call('logout','POST',{})[0],200)
        status,result=client.call('login','POST',dict(username='EMAIL-ARTIST@example.test',password=data['password']));self.assertEqual(status,200,result);client.csrf=result['csrf']
        self.assertEqual(client.call('profile','PATCH',dict(name='Updated Artist',email='updated-artist@example.test',phone='',country='Ghana'))[0],200)
        self.assertEqual(client.call('profile')[1]['country'],'Ghana')
    def test_registration_invalid_email_and_duplicate_are_rejected(self):
        client=Client(self.port);data=self.registration('invalid-email');data['email']='not-an-email'
        self.assertEqual(client.call('register','POST',data)[0],400)
        data=self.registration('first-email-owner');data['email']='unique-owner@example.test'
        status,result=client.call('register','POST',data);self.assertEqual(status,201,result)
        data=self.registration('second-email-owner');data['email']='UNIQUE-OWNER@example.test'
        status,result=client.call('register','POST',data);self.assertEqual(status,409,result)
        with db.connect() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM account_profiles WHERE email=?',('unique-owner@example.test',)).fetchone()[0],1)
            self.assertIsNone(c.execute('SELECT 1 FROM users WHERE username=?',('second-email-owner',)).fetchone())
    def test_signup_rate_limit_survives_failed_attempts(self):
        client=Client(self.port);data=self.registration('ALICE')
        for _ in range(5):self.assertEqual(client.call('register','POST',data)[0],409)
        self.assertEqual(client.call('register','POST',self.registration('limited-registration'))[0],429)
    def test_public_sample_seed_creates_playable_audio_once(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('sample_seed',Path(__file__).parents[1]/'deploy/seed_public_releases.py');seed=importlib.util.module_from_spec(spec);spec.loader.exec_module(seed)
        ids=seed.seed();self.assertEqual(len(ids),3);self.assertEqual(seed.seed(),ids)
        client=Client(self.port);listing=client.call('explore')[1]['projects'];self.assertEqual(len([p for p in listing if p.get('sample')]),3)
        for pid in ids:
            status,release=client.call('public/'+str(pid));self.assertEqual(status,200)
            asset=release['assets'][0];self.assertGreater(asset['duration'],5)
            status,audio=client.call('public-media/'+str(asset['id']));self.assertEqual(status,200);self.assertEqual(audio[:4],b'RIFF')
            self.assertEqual(self.a.call('projects/'+str(pid))[0],404)

    def test_mobile_download_page_and_apk_are_public(self):
        import hashlib
        client=Client(self.port)
        with urllib.request.urlopen(client.base+'/mobile') as response:
            self.assertEqual(response.status,200);self.assertIn(b'Download Android app',response.read())
        with urllib.request.urlopen(client.base+'/downloads/africa-creativity.apk') as response:
            apk=response.read();self.assertEqual(apk[:2],b'PK');self.assertEqual(response.headers.get_content_type(),'application/vnd.android.package-archive')
        with urllib.request.urlopen(client.base+'/downloads/africa-creativity.apk.sha256') as response:
            self.assertEqual(response.read().decode().split()[0],hashlib.sha256(apk).hexdigest())
        with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(client.base+'/downloads/private.jks')
        self.assertEqual(caught.exception.code,404)

if __name__=='__main__':unittest.main()
