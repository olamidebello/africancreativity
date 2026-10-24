"""Tenant-scoped commerce. Hosted checkout only; secrets never leave the server."""
import json, os, secrets, re
from decimal import Decimal
from urllib.request import Request, urlopen
from urllib.parse import urlencode, quote, urlparse
import database as db
from database import Problem
GATEWAYS = {'stripe': 'STRIPE_SECRET_KEY', 'paystack': 'PAYSTACK_SECRET_KEY', 'flutterwave': 'FLUTTERWAVE_SECRET_KEY'}
SCHEMA = '''
CREATE TABLE IF NOT EXISTS commerce_products(id INTEGER PRIMARY KEY,title TEXT NOT NULL,credits INTEGER NOT NULL,amount INTEGER NOT NULL,currency TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS commerce_orders(id TEXT PRIMARY KEY,tenant_id INTEGER NOT NULL REFERENCES tenants(id),user_id INTEGER NOT NULL REFERENCES users(id),gateway TEXT NOT NULL,product_id INTEGER NOT NULL,credits INTEGER NOT NULL,amount INTEGER NOT NULL,currency TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'pending',provider_ref TEXT UNIQUE,checkout_url TEXT,created REAL NOT NULL,paid REAL);
CREATE TABLE IF NOT EXISTS market_listings(id INTEGER PRIMARY KEY,tenant_id INTEGER NOT NULL REFERENCES tenants(id),seller_id INTEGER NOT NULL REFERENCES users(id),title TEXT NOT NULL,description TEXT NOT NULL,category TEXT NOT NULL,content TEXT NOT NULL,price INTEGER NOT NULL,state TEXT NOT NULL DEFAULT 'pending',created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS market_purchases(id INTEGER PRIMARY KEY,listing_id INTEGER NOT NULL REFERENCES market_listings(id),tenant_id INTEGER NOT NULL REFERENCES tenants(id),user_id INTEGER NOT NULL REFERENCES users(id),price INTEGER NOT NULL,seller_credits INTEGER NOT NULL,created REAL NOT NULL,UNIQUE(listing_id,tenant_id));
'''
def init(c): c.executescript(SCHEMA)
def whole(value,lo,hi):
    number=db.number(value,lo,hi)
    if isinstance(value,bool) or not number.is_integer():raise Problem('Use a whole number')
    return int(number)
def configured():
    base = os.environ.get('COMMERCE_PUBLIC_URL', '').rstrip('/')
    return [{'id': k, 'ready': bool(os.environ.get(v) and base.startswith('https://')), 'status': 'ready' if os.environ.get(v) and base.startswith('https://') else 'not configured'} for k,v in GATEWAYS.items()]
def remote(gateway, path, payload=None):
    roots={'stripe':'https://api.stripe.com/v1','paystack':'https://api.paystack.co','flutterwave':'https://api.flutterwave.com/v3'}
    secret=os.environ.get(GATEWAYS[gateway], '')
    if not secret: raise Problem('Gateway is not configured',409)
    headers={'Authorization':'Bearer '+secret,'Content-Type':'application/json'}
    data=None
    if payload is not None:
        if gateway=='stripe':data=urlencode(payload).encode();headers['Content-Type']='application/x-www-form-urlencoded'
        else:data=json.dumps(payload).encode()
    try:
        with urlopen(Request(roots[gateway]+path,data=data,headers=headers),timeout=20) as response:return json.load(response)
    except Exception:raise Problem('Payment provider unavailable; retry verification before creating another payment',502)
def checkout(c,u,d):
    db.require_role(u,'tenant_admin')
    gateway=d.get('gateway')
    if gateway not in GATEWAYS or not next(x for x in configured() if x['id']==gateway)['ready']:raise Problem('Select a configured gateway',409)
    p=c.execute('SELECT * FROM commerce_products WHERE id=? AND active=1',(d.get('product_id'),)).fetchone()
    if not p:raise Problem('Credit package not available',404)
    profile=c.execute('SELECT email FROM account_profiles WHERE user_id=?',(u['id'],)).fetchone()
    if not profile:raise Problem('An account email is required for checkout',409)
    reference=secrets.token_hex(20);base=os.environ['COMMERCE_PUBLIC_URL'].rstrip('/');back=base+'/?order='+reference+'#billing'
    c.execute('INSERT INTO commerce_orders(id,tenant_id,user_id,gateway,product_id,credits,amount,currency,created) VALUES(?,?,?,?,?,?,?,?,?)',(reference,u['tenant_id'],u['id'],gateway,p['id'],p['credits'],p['amount'],p['currency'],db.now()))
    c.commit() # Persist immutable order before contacting provider; no DB lock over network.
    if gateway=='stripe':
        response=remote(gateway,'/checkout/sessions',{'mode':'payment','client_reference_id':reference,'customer_email':profile['email'],'success_url':back,'cancel_url':back,'line_items[0][price_data][currency]':p['currency'].lower(),'line_items[0][price_data][unit_amount]':p['amount'],'line_items[0][price_data][product_data][name]':p['title'],'line_items[0][quantity]':1})
        provider_ref=response.get('id');url=response.get('url')
    elif gateway=='paystack':
        response=remote(gateway,'/transaction/initialize',{'email':profile['email'],'amount':p['amount'],'currency':p['currency'],'reference':reference,'callback_url':back})
        provider_ref=reference;url=response.get('data',{}).get('authorization_url')
    else:
        response=remote(gateway,'/payments',{'tx_ref':reference,'amount':str(Decimal(p['amount'])/100),'currency':p['currency'],'redirect_url':back,'customer':{'email':profile['email']},'customizations':{'title':p['title']}})
        provider_ref=reference;url=response.get('data',{}).get('link')
    allowed={'stripe':('checkout.stripe.com',),'paystack':('checkout.paystack.com',),'flutterwave':('checkout.flutterwave.com',)}
    parsed=urlparse(url or '')
    if not provider_ref or parsed.scheme!='https' or parsed.hostname not in allowed[gateway]:raise Problem('Provider did not return a valid checkout URL',502)
    c.execute('UPDATE commerce_orders SET provider_ref=?,checkout_url=? WHERE id=?',(provider_ref,url,reference));return {'id':reference,'url':url}
def verify(c,u,reference):
    db.require_role(u,'tenant_admin')
    order=c.execute('SELECT * FROM commerce_orders WHERE id=? AND tenant_id=?',(reference,u['tenant_id'])).fetchone()
    if not order:raise Problem('Order not found',404)
    if order['state']=='paid':return {'state':'paid','credits':order['credits']}
    if not order['provider_ref']:raise Problem('Checkout was not completed; contact support with the order reference',409)
    gateway=order['gateway']
    if gateway=='stripe':
        result=remote(gateway,'/checkout/sessions/'+quote(order['provider_ref'],safe=''))
        paid=result.get('payment_status')=='paid' and result.get('client_reference_id')==reference
        amount=result.get('amount_total');currency=result.get('currency','').upper()
    else:
        endpoint='/transaction/verify/'+reference if gateway=='paystack' else '/transactions/verify_by_reference?tx_ref='+reference
        result=remote(gateway,endpoint).get('data',{})
        paid=result.get('status')==('success' if gateway=='paystack' else 'successful') and result.get('reference' if gateway=='paystack' else 'tx_ref')==reference
        amount=result.get('amount') if gateway=='paystack' else Decimal(str(result.get('amount',0)))*100
        currency=result.get('currency')
    if not paid: return {'state':'pending','credits':0}
    if amount!=order['amount'] or currency!=order['currency']:raise Problem('Provider amount or currency does not match the order',409)
    c.execute('BEGIN IMMEDIATE')
    if c.execute("UPDATE commerce_orders SET state='paid',paid=? WHERE id=? AND state='pending'",(db.now(),reference)).rowcount:
        c.execute('UPDATE tenants SET credits=credits+?,version=version+1 WHERE id=?',(order['credits'],u['tenant_id']))
        c.execute('INSERT INTO ledger(tenant_id,delta,reason,created) VALUES(?,?,?,?)',(u['tenant_id'],order['credits'],'payment:'+reference,db.now()));db.audit(c,u,'payment.verified',reference)
    return {'state':'paid','credits':order['credits']}
def route(h,c,u,path,method):
    admin=u['role']=='super_admin'
    if not admin:db.tenant_user(u)
    if path=='/api/commerce' and method=='GET':
        scope='' if admin else ' WHERE tenant_id=?';args=() if admin else (u['tenant_id'],)
        return h.send(200,{'gateways':configured(),'products':[dict(x) for x in c.execute('SELECT * FROM commerce_products'+('' if admin else ' WHERE active=1'))],'orders':[dict(x) for x in c.execute('SELECT * FROM commerce_orders'+scope+' ORDER BY created DESC LIMIT 100',args)],'ledger':[dict(x) for x in c.execute('SELECT * FROM ledger'+scope+' ORDER BY id DESC LIMIT 100',args)]})
    if path=='/api/commerce/products' and method=='POST':
        db.require_role(u,'super_admin');d=h.input();currency=d.get('currency')
        if currency not in ('USD','NGN','GBP','EUR','GHS','KES','ZAR'):raise Problem('Unsupported currency')
        pid=c.execute('INSERT INTO commerce_products(title,credits,amount,currency) VALUES(?,?,?,?)',(db.text(d,'title',120),whole(d.get('credits'),1,1000000),whole(d.get('amount'),1,100000000),currency)).lastrowid
        db.audit(c,u,'commerce.product',pid);return h.send(201,{'id':pid})
    if re.fullmatch('/api/commerce/products/[0-9]+',path) and method=='PATCH':
        db.require_role(u,'super_admin');d=h.input();active=whole(d.get('active'),0,1)
        c.execute('UPDATE commerce_products SET active=? WHERE id=?',(active,int(path.split('/')[-1])));db.audit(c,u,'commerce.product.status',path);return h.send(200,{'ok':True})
    if path=='/api/commerce/checkout' and method=='POST':return h.send(201,checkout(c,u,h.input()))
    if re.fullmatch('/api/commerce/orders/[a-f0-9]{40}/verify',path) and method=='POST':return h.send(200,verify(c,u,path.split('/')[-2]))
    if path=='/api/marketplace' and method=='GET':
        condition='1=1' if admin else "(l.state='approved' OR l.tenant_id=?)"
        args=() if admin else (u['tenant_id'],)
        extra=',l.content' if admin else ''
        rows=c.execute('SELECT l.id,l.tenant_id,l.title,l.description,l.category,l.price,l.state,t.name AS seller'+extra+' FROM market_listings l JOIN tenants t ON t.id=l.tenant_id WHERE t.status=\'active\' AND '+condition+' ORDER BY l.id DESC LIMIT 500',args)
        purchases=[] if admin else [dict(x) for x in c.execute('SELECT p.*,l.title,l.content,l.category FROM market_purchases p JOIN market_listings l ON l.id=p.listing_id WHERE p.tenant_id=? ORDER BY p.id DESC',(u['tenant_id'],))]
        sales=[] if admin else [dict(x) for x in c.execute('SELECT p.id,p.price,p.seller_credits,p.created,l.title FROM market_purchases p JOIN market_listings l ON l.id=p.listing_id WHERE l.tenant_id=? ORDER BY p.id DESC LIMIT 100',(u['tenant_id'],))]
        return h.send(200,{'listings':[dict(x) for x in rows],'purchases':purchases,'sales':sales})
    if re.fullmatch('/api/marketplace/[0-9]+',path) and method=='PATCH':
        db.require_role(u,'tenant_admin')
        if not c.execute("UPDATE market_listings SET state='withdrawn' WHERE id=? AND tenant_id=?",(int(path.split('/')[-1]),u['tenant_id'])).rowcount:raise Problem('Listing not found',404)
        db.audit(c,u,'marketplace.withdraw',path);return h.send(200,{'ok':True})
    if path=='/api/marketplace' and method=='POST':
        db.require_role(u,'tenant_admin');d=h.input()
        if d.get('rights_confirmed') is not True:raise Problem('Confirm you own the rights to sell this content')
        if d.get('category') not in ('lyrics','prompt','guide'):raise Problem('Select lyrics, prompt, or guide')
        lid=c.execute('INSERT INTO market_listings(tenant_id,seller_id,title,description,category,content,price,created) VALUES(?,?,?,?,?,?,?,?)',(u['tenant_id'],u['id'],db.text(d,'title',120),db.text(d,'description',2000),d['category'],db.text(d,'content',20000),whole(d.get('price'),1,1000000),db.now())).lastrowid
        db.audit(c,u,'marketplace.submit',lid);return h.send(201,{'id':lid})
    if re.fullmatch('/api/marketplace/[0-9]+/moderate',path) and method=='POST':
        db.require_role(u,'super_admin');d=h.input();state=d.get('state')
        if state not in ('approved','rejected','pending'):raise Problem('Invalid moderation state')
        c.execute('UPDATE market_listings SET state=? WHERE id=?',(state,int(path.split('/')[-2])));db.audit(c,u,'marketplace.'+state,path);return h.send(200,{'ok':True})
    if re.fullmatch('/api/marketplace/[0-9]+/purchase',path) and method=='POST':
        db.require_role(u,'tenant_admin');lid=int(path.split('/')[-2]);c.execute('BEGIN IMMEDIATE')
        item=c.execute("SELECT l.* FROM market_listings l JOIN tenants t ON t.id=l.tenant_id WHERE l.id=? AND l.state='approved' AND t.status='active'",(lid,)).fetchone()
        if not item:raise Problem('Listing not available',404)
        if item['tenant_id']==u['tenant_id']:raise Problem('You cannot buy your own listing')
        existing=c.execute('SELECT id FROM market_purchases WHERE listing_id=? AND tenant_id=?',(lid,u['tenant_id'])).fetchone()
        if existing:return h.send(200,{'id':existing['id'],'already_owned':True})
        price=item['price'];earnings=price*90//100
        if not c.execute('UPDATE tenants SET credits=credits-?,version=version+1 WHERE id=? AND credits>=?',(price,u['tenant_id'],price)).rowcount:raise Problem('Insufficient workspace credits',409)
        c.execute('UPDATE tenants SET credits=credits+?,version=version+1 WHERE id=?',(earnings,item['tenant_id']))
        pid=c.execute('INSERT INTO market_purchases(listing_id,tenant_id,user_id,price,seller_credits,created) VALUES(?,?,?,?,?,?)',(lid,u['tenant_id'],u['id'],price,earnings,db.now())).lastrowid
        for tid,delta in [(u['tenant_id'],-price),(item['tenant_id'],earnings)]:c.execute('INSERT INTO ledger(tenant_id,delta,reason,created) VALUES(?,?,?,?)',(tid,delta,'marketplace:'+str(pid),db.now()))
        db.audit(c,u,'marketplace.purchase',pid);return h.send(201,{'id':pid})
    raise Problem('Not found',404)
