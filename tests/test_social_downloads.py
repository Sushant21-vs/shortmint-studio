"""Offline integration tests for authenticated link downloading and daily quotas."""
import json
import subprocess
import time
from types import SimpleNamespace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import accounts
import app
import downloads

HEADERS={'X-ShortMint-Request':'1'}

@pytest.fixture()
def pair(tmp_path,monkeypatch):
    monkeypatch.setattr(accounts,'DB_FILE',tmp_path/'data.db')
    accounts.init_db()
    accounts.create_owner('v5owner','a_long_secure_owner_password')
    monkeypatch.setattr(app,'STORAGE',tmp_path/'jobs')
    app.STORAGE.mkdir(parents=True,exist_ok=True)
    # Routes have already captured app.STORAGE at import time: the downloader
    # knows its own path. Patch its worker and read from that same app storage.
    # For test downloads use a fresh app router built into app.app for reuse.
    with TestClient(app.app) as owner,TestClient(app.app) as friend:
        assert owner.post('/api/auth/login',json={'username':'v5owner','password':'a_long_secure_owner_password'},headers=HEADERS).status_code==200
        code=owner.post('/api/admin/invites',headers=HEADERS).json()['code']
        assert friend.post('/api/auth/register',json={'username':'v5friend','password':'a_long_secure_friend_password','invite_code':code},headers=HEADERS).status_code==200
        assert friend.post('/api/auth/login',json={'username':'v5friend','password':'a_long_secure_friend_password'},headers=HEADERS).status_code==200
        yield owner,friend


def test_url_validation_and_source_import_expansion(pair,monkeypatch):
    owner,friend=pair
    assert downloads.source_platform('https://vm.tiktok.com/abcdef/')=='TikTok'
    assert downloads.source_platform('https://www.instagram.com/reel/AB123/')=='Instagram'
    assert downloads.source_platform('https://youtu.be/abc')=='YouTube'
    for blocked in ['http://www.instagram.com/reel/abc/',
                    'https://instagram.com.evil.test/reel/x',
                    'https://localhost/private','https://127.0.0.1/secret',
                    'https://user:pass@www.tiktok.com/v/3']:
        with pytest.raises(ValueError): downloads.source_platform(blocked)
    r=friend.post('/api/import-url',json={'url':'https://localhost/private'},headers=HEADERS)
    assert r.status_code==400
    assert friend.post('/api/downloads/start',json={'url':'https://www.tiktok.com/@someone/video/77','quality':'720','rights_confirmed':False},headers=HEADERS).status_code==400


def test_daily_quota_and_reset(pair,monkeypatch):
    owner,friend=pair
    m=friend.get('/api/me').json()['user']
    u=m['id']; fakeuser={'id':u,'role':'member'}
    assert friend.get('/api/downloads/quota').json()['remaining']==5
    assert owner.get('/api/downloads/quota').json()['unlimited'] is True
    for i in range(2):
        job=f'job{i}'
        assert accounts.reserve_download_quota(fakeuser,job,'2160')==3
        if i==0:
            assert friend.get('/api/downloads/quota').json()['remaining']==2
            assert friend.get('/api/me').json()['user']['credits']==5  # normal Shorts credits unaffected
            with pytest.raises(Exception): accounts.reserve_download_quota(fakeuser,'over','2160')
            accounts.finish_download_quota(job,False)
            assert friend.get('/api/downloads/quota').json()['remaining']==5
        else:
            accounts.finish_download_quota(job,True)
    assert friend.get('/api/downloads/quota').json()['remaining']==2
    assert owner.post('/api/admin/settings',json={'daily_download_credits':3},headers=HEADERS).status_code==200
    assert friend.get('/api/downloads/quota').json()['remaining']==0
    assert friend.post('/api/admin/settings',json={'daily_download_credits':100},headers=HEADERS).status_code==403
    assert owner.post('/api/admin/settings',json={'daily_download_credits':-1},headers=HEADERS).status_code==400
    monkeypatch.setattr(accounts,'utc_day',lambda:'2099-01-01')
    assert friend.get('/api/downloads/quota').json()['remaining']==3


def test_actual_download_flow_mocked_website(pair,monkeypatch,tmp_path):
    owner,friend=pair
    real_run=subprocess.run
    # Video extraction is simulated offline. FFprobe checks a real small MP4.
    video=tmp_path/'tiny.mp4'
    p=real_run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','testsrc2=s=128x224:r=12',
                '-t','1','-c:v','mpeg4','-y',str(video)],capture_output=True,text=True)
    assert p.returncode==0,p.stderr

    def fake_run(cmd,**kw):
        if 'yt_dlp' in cmd:
            dest=Path(cmd[cmd.index('-o')+1].replace('%(ext)s','mp4'))
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(video.read_bytes())
            return SimpleNamespace(returncode=0,stderr='',stdout='success')
        return real_run(cmd,**kw)
    monkeypatch.setattr(downloads.subprocess,'run',fake_run)

    result=friend.post('/api/downloads/start',headers=HEADERS,json={
        'url':'https://www.tiktok.com/@creator/video/1234','quality':'1080','rights_confirmed':True})
    assert result.status_code==200,result.text
    jobid=result.json()['job_id']
    for _ in range(120):
        state=friend.get('/api/downloads/status/'+jobid).json()
        if state['state'] in ('completed','failed'):break
        time.sleep(.03)
    assert state['state']=='completed',state
    assert friend.get('/api/downloads/quota').json()['remaining']==4
    response=friend.get('/api/downloads/file/'+jobid)
    assert response.status_code==200 and len(response.content)>100
    assert owner.get('/api/downloads/file/'+jobid).status_code==404
    assert len(friend.get('/api/downloads/recent').json()['items'])>=1
    assert friend.get('/api/me').json()['user']['credits']==5
    # Demand 4K from an HD source -> fail and refund all 3 daily credits.
    r=friend.post('/api/downloads/start',headers=HEADERS,json={
        'url':'https://www.instagram.com/reel/ABC123/','quality':'2160','rights_confirmed':True})
    assert r.status_code==200,r.text
    job2=r.json()['job_id']
    for _ in range(120):
        state2=friend.get('/api/downloads/status/'+job2).json()
        if state2['state'] in ('completed','failed'):break
        time.sleep(.03)
    assert state2['state']=='failed',state2
    assert '4K' in state2['message'] or '2160p' in state2['message']
    assert friend.get('/api/downloads/quota').json()['remaining']==4
    assert friend.get('/api/downloads/file/'+job2).status_code==404


def test_daily_4k_three_credits_owner_unlimited(pair):
    owner,friend=pair
    member={'id':friend.get('/api/me').json()['user']['id'],'role':'member'}
    assert accounts.download_credit_cost('2160')==3
    assert accounts.download_credit_cost('1440')==2
    assert accounts.download_credit_cost('1080')==1
    assert accounts.download_credit_cost('720')==1
    accounts.reserve_download_quota(member,'a','2160')
    accounts.finish_download_quota('a',True)
    accounts.reserve_download_quota(member,'b','1440')
    accounts.finish_download_quota('b',True)
    with pytest.raises(Exception): accounts.reserve_download_quota(member,'c','720')
    admin={'id':owner.get('/api/me').json()['user']['id'],'role':'owner'}
    for i in range(10):
        accounts.reserve_download_quota(admin,f'owner-{i}','2160')
        accounts.finish_download_quota(f'owner-{i}',True)
    assert owner.get('/api/downloads/quota').json()['remaining'] is None
