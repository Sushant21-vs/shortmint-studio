"""Tests for owner-issued ShortMint credits and manual buy-contact workflow."""
import pytest
from fastapi.testclient import TestClient
import app
import accounts

HEADERS={'X-ShortMint-Request':'1'}

@pytest.fixture()
def accounts_clients(tmp_path,monkeypatch):
    monkeypatch.setattr(app,'STORAGE',tmp_path/'jobs')
    app.STORAGE.mkdir(parents=True)
    monkeypatch.setattr(accounts,'DB_FILE',tmp_path/'shortmint.sqlite3')
    accounts.init_db()
    accounts.create_owner('testowner','a_secure_test_password')
    with TestClient(app.app) as owner,TestClient(app.app) as friend:
        assert owner.post('/api/auth/login',json={'username':'testowner','password':'a_secure_test_password'},headers=HEADERS).status_code==200
        code=owner.post('/api/admin/invites',headers=HEADERS).json()['code']
        assert friend.post('/api/auth/register',json={'username':'testmember','password':'another_secure_password','invite_code':code},headers=HEADERS).status_code==200
        assert friend.post('/api/auth/login',json={'username':'testmember','password':'another_secure_password'},headers=HEADERS).status_code==200
        yield owner,friend

def test_purchase_requires_owner_confirmed_payment(accounts_clients):
    owner,friend=accounts_clients
    assert friend.get('/api/me').json()['user']['credits']==5
    before=friend.get('/api/credits/shop').json()
    assert before['packages']==[10,25,50,100]
    assert before['email']==''
    r=friend.post('/api/credits/purchase-request',headers=HEADERS,
        json={'amount':25,'contact':'testmember@example.com','message':'Please contact me'} )
    assert r.status_code==200,r.text
    rid=r.json()['request_id']
    assert friend.get('/api/me').json()['user']['credits']==5
    assert friend.post('/api/admin/purchases/'+str(rid)+'/review',headers=HEADERS,json={'action':'confirm_paid'}).status_code==403
    assert friend.post('/api/credits/purchase-request',headers=HEADERS,
        json={'amount':10,'contact':'testmember@example.com'}).status_code==409
    overview=owner.get('/api/admin/overview').json()
    assert overview['purchase_requests'][0]['id']==rid
    assert overview['purchase_requests'][0]['contact']=='testmember@example.com'
    approved=owner.post('/api/admin/purchases/'+str(rid)+'/review',headers=HEADERS,json={'action':'confirm_paid'})
    assert approved.status_code==200,approved.text
    assert friend.get('/api/me').json()['user']['credits']==30
    assert owner.post('/api/admin/purchases/'+str(rid)+'/review',headers=HEADERS,json={'action':'confirm_paid'}).status_code==404
    assert friend.get('/api/me').json()['user']['credits']==30
    assert friend.get('/api/credits/shop').json()['purchases'][0]['status']=='fulfilled'
    creditlog=friend.get('/api/credits/activity').json()['history']
    assert any('owner confirmed payment' in h['reason'] and h['amount']==25 for h in creditlog)

def test_owner_contact_settings_and_rejection(accounts_clients):
    owner,friend=accounts_clients
    assert friend.post('/api/admin/settings',headers=HEADERS,json={'contact_email':'x@abc.com'}).status_code==403
    assert owner.post('/api/admin/settings',headers=HEADERS,
        json={'contact_email':'help@example.com','contact_whatsapp':'+977 9812345678'}).status_code==200
    shop=friend.get('/api/credits/shop').json()
    assert shop['email']=='help@example.com'
    assert shop['whatsapp']=='+977 9812345678'
    req=friend.post('/api/credits/purchase-request',headers=HEADERS,
        json={'amount':50,'contact':'+977 98 12345678'}).json()['request_id']
    r=owner.post(f'/api/admin/purchases/{req}/review',headers=HEADERS,json={'action':'reject'})
    assert r.status_code==200
    assert friend.get('/api/me').json()['user']['credits']==5
    assert owner.post(f'/api/admin/purchases/{req}/review',headers=HEADERS,json={'action':'confirm_paid'}).status_code==404
    assert owner.post('/api/admin/settings',headers=HEADERS,json={'contact_whatsapp':'abc'}).status_code==400
    assert owner.post('/api/admin/settings',headers=HEADERS,json={'contact_email':'not_an_email'}).status_code==400
    assert owner.post('/api/admin/settings',headers=HEADERS,json={'starting_credits':0}).status_code==200
    newcode=owner.post('/api/admin/invites',headers=HEADERS).json()['code']
    with TestClient(app.app) as newfriend:
        assert newfriend.post('/api/auth/register',headers=HEADERS,json={
            'username':'newfriend','password':'another_good_password','invite_code':newcode}).status_code==200
        assert newfriend.post('/api/auth/login',headers=HEADERS,json={
            'username':'newfriend','password':'another_good_password'}).status_code==200
        assert newfriend.get('/api/me').json()['user']['credits']==0
    assert owner.get('/api/credits/shop').status_code==200
    assert owner.post('/api/credits/purchase-request',headers=HEADERS,
        json={'amount':10,'contact':'someone@example.com'}).status_code==400


def test_missing_request_header_rejected(accounts_clients):
    _,friend=accounts_clients
    assert friend.post('/api/credits/purchase-request',json={'amount':10,'contact':'test@site.com'}).status_code==403
