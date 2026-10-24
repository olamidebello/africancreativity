import unittest, os
from unittest.mock import patch
import test_platform as platform
from test_platform import Client
import database as db
import commerce

class CommerceTest(unittest.TestCase):
    setUpClass=classmethod(platform.PlatformTest.setUpClass.__func__)
    tearDownClass=classmethod(platform.PlatformTest.tearDownClass.__func__)
    def setUp(self):
        platform.PlatformTest.setUp(self)
        with db.connect() as c:
            for table in ['market_purchases','market_listings','commerce_orders','commerce_products']:c.execute('DELETE FROM '+table)
            c.execute('UPDATE tenants SET credits=100')
            for name in ['alice','bob']:
                uid=c.execute('SELECT id FROM users WHERE username=?',(name,)).fetchone()[0]
                c.execute('INSERT OR IGNORE INTO account_profiles(user_id,email,created,updated) VALUES(?,?,?,?)',(uid,name+'@example.com',db.now(),db.now()))
    def listing(self):
        s,d=self.a.call('marketplace','POST',{'title':'Original prompt','description':'A musical idea','category':'prompt','content':'Secret original content','price':20,'rights_confirmed':True})
        self.assertEqual(s,201,d);return d['id']
    def test_moderation_purchase_isolation_and_idempotency(self):
        lid=self.listing()
        self.assertEqual(self.b.call('marketplace')[1]['listings'],[])
        self.assertEqual(self.b.call(f'marketplace/{lid}/purchase','POST',{})[0],404)
        self.assertEqual(self.a.call(f'marketplace/{lid}/moderate','POST',{'state':'approved'})[0],403)
        self.assertEqual(self.admin.call('marketplace')[1]['listings'][0]['content'],'Secret original content')
        self.assertEqual(self.admin.call(f'marketplace/{lid}/moderate','POST',{'state':'approved'})[0],200)
        catalog=self.b.call('marketplace')[1]
        self.assertNotIn('content',catalog['listings'][0])
        self.assertEqual(self.a.call(f'marketplace/{lid}/purchase','POST',{})[0],400)
        self.assertEqual(self.b.call(f'marketplace/{lid}/purchase','POST',{})[0],201)
        self.assertEqual(self.b.call(f'marketplace/{lid}/purchase','POST',{})[0],200)
        self.assertEqual(self.b.call('me')[1]['tenant']['credits'],80)
        self.assertEqual(self.a.call('me')[1]['tenant']['credits'],118)
        self.assertEqual(self.b.call('marketplace')[1]['purchases'][0]['content'],'Secret original content')
        self.assertEqual(self.a.call('marketplace')[1]['purchases'],[])
        self.assertEqual(self.b.call(f'marketplace/{lid}','PATCH',{})[0],404)
        self.assertEqual(self.a.call(f'marketplace/{lid}','PATCH',{})[0],200)
        self.assertEqual(self.b.call('marketplace')[1]['listings'],[])
        self.assertEqual(len(self.b.call('marketplace')[1]['purchases']),1)
    def test_roles_csrf_rights_and_insufficient_credits(self):
        lid=self.listing();self.admin.call(f'marketplace/{lid}/moderate','POST',{'state':'approved'})
        creator=Client(self.port).login('editor')
        self.assertEqual(creator.call(f'marketplace/{lid}/purchase','POST',{})[0],403)
        self.assertEqual(self.a.call('marketplace','POST',{'rights_confirmed':False})[0],400)
        with db.connect() as c:c.execute('UPDATE tenants SET credits=0 WHERE id=2')
        self.assertEqual(self.b.call(f'marketplace/{lid}/purchase','POST',{})[0],409)
        self.assertEqual(self.a.call('me')[1]['tenant']['credits'],100)
        self.b.csrf='bad';self.assertEqual(self.b.call(f'marketplace/{lid}/purchase','POST',{})[0],403)
        self.assertEqual(Client(self.port).call('commerce')[0],401)
    def package(self):
        s,d=self.admin.call('commerce/products','POST',{'title':'100 credits','credits':100,'amount':1000,'currency':'USD'})
        self.assertEqual(s,201,d);return d['id']
    def test_verified_payment_exactly_once_and_tenant_scope(self):
        pid=self.package()
        self.assertEqual(self.a.call('commerce/products','POST',{})[0],403)
        env={'STRIPE_SECRET_KEY':'test-only','COMMERCE_PUBLIC_URL':'https://africancreativity.io'}
        with patch.dict(os.environ,env),patch.object(commerce,'remote',return_value={'id':'cs_test','url':'https://checkout.stripe.com/c/test'}) as remote:
            status,order=self.a.call('commerce/checkout','POST',{'product_id':pid,'gateway':'stripe','amount':1,'credits':99999})
            self.assertEqual(status,201,order)
            self.assertEqual(remote.call_args.args[2]['line_items[0][price_data][unit_amount]'],1000)
        reference=order['id']
        self.assertEqual(self.b.call(f'commerce/orders/{reference}/verify','POST',{})[0],404)
        result={'payment_status':'paid','client_reference_id':reference,'amount_total':999,'currency':'usd'}
        with patch.object(commerce,'remote',return_value=result):self.assertEqual(self.a.call(f'commerce/orders/{reference}/verify','POST',{})[0],409)
        self.assertEqual(self.a.call('me')[1]['tenant']['credits'],100)
        result['amount_total']=1000
        with patch.object(commerce,'remote',return_value=result):
            for _ in range(2):self.assertEqual(self.a.call(f'commerce/orders/{reference}/verify','POST',{})[0],200)
        self.assertEqual(self.a.call('me')[1]['tenant']['credits'],200)
        self.assertEqual(self.b.call('commerce')[1]['orders'],[])
        with db.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM ledger WHERE reason=?',('payment:'+reference,)).fetchone()[0],1)
    def test_paystack_and_flutterwave_verification(self):
        for gateway in ['paystack','flutterwave']:
            reference=('a' if gateway=='paystack' else 'b')*40
            with db.connect() as c:
                uid=c.execute("SELECT id FROM users WHERE username='alice'").fetchone()[0]
                c.execute('INSERT INTO commerce_orders(id,tenant_id,user_id,gateway,product_id,credits,amount,currency,provider_ref,created) VALUES(?,1,?,?,1,25,1000,?,?,?)',(reference,uid,gateway,'NGN',reference,db.now()))
            data={'status':'success' if gateway=='paystack' else 'successful','reference':reference,'tx_ref':reference,'amount':1000 if gateway=='paystack' else '10.00','currency':'NGN'}
            with patch.object(commerce,'remote',return_value={'data':data}):
                self.assertEqual(self.a.call(f'commerce/orders/{reference}/verify','POST',{})[0],200)
        self.assertEqual(self.a.call('me')[1]['tenant']['credits'],150)
