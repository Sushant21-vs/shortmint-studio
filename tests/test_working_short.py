"""Full API regression: owner, invite, member credits, and real FFmpeg export."""
import subprocess
import time
import pytest
from fastapi.testclient import TestClient
import app
import accounts

HEADER = {'X-ShortMint-Request': '1'}


@pytest.fixture()
def clients(tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'STORAGE', tmp_path/'jobs')
    app.STORAGE.mkdir(parents=True)
    monkeypatch.setattr(accounts, 'DB_FILE', tmp_path/'shortmint.sqlite3')
    accounts.init_db()
    accounts.create_owner('theowner', 'testownerpassword123')
    with TestClient(app.app) as owner, TestClient(app.app) as friend:
        login = owner.post('/api/auth/login', headers=HEADER,
                json={'username':'theowner','password':'testownerpassword123'})
        assert login.status_code == 200
        invite = owner.post('/api/admin/invites',headers=HEADER).json()['code']
        registered = friend.post('/api/auth/register',headers=HEADER,
                 json={'username':'friend123','password':'friendpassword123','invite_code':invite})
        assert registered.status_code == 200
        login2 = friend.post('/api/auth/login', headers=HEADER,
                 json={'username':'friend123','password':'friendpassword123'})
        assert login2.status_code == 200
        yield owner, friend, tmp_path


def sample_video(tmp_path):
    dest=tmp_path/'sample.mp4'
    subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error',
         '-f','lavfi','-i','testsrc2=size=480x270:rate=24:duration=7',
         '-f','lavfi','-i','sine=frequency=400:duration=7',
         '-c:v','libx264','-preset','ultrafast','-c:a','aac','-shortest',str(dest)],
         check=True, timeout=30)
    return dest


def upload(client, src):
    with src.open('rb') as f:
        resp=client.post('/api/upload',headers=HEADER,files={'file':('video.mp4',f,'video/mp4')})
    assert resp.status_code==200,resp.text
    return resp.json()['id']


def wait(client, task_id):
    for _ in range(200):
        status=client.get('/api/status/'+task_id).json()
        if status['state'] in ('completed','cancelled','failed'):
            return status
        time.sleep(.2)
    pytest.fail('FFmpeg export did not complete in 40 seconds')


def test_member_privacy_credits_and_real_captioned_mp4(clients):
    owner, friend, tmp=clients
    video=sample_video(tmp)
    sid=upload(friend,video)
    assert owner.get('/api/project/'+sid).status_code==404
    assert friend.get('/api/admin/overview').status_code==403
    settings={'session_id':sid,'mode':'manual','clip_length':5,'count':1,'start':1,
        'crop_mode':'center','resolution':'540','title':'Big news',
        'watermark':'@MyChannel','focus_x':35,'normalize_audio':True,
        'caption_srt':'1\n00:00:01,000 --> 00:00:03,000\nThis is my first Short!'}
    resp=friend.post('/api/generate',json=settings,headers=HEADER)
    assert resp.status_code==200,resp.text
    result=wait(friend,resp.json()['task_id'])
    assert result['state']=='completed',result
    assert len(result['results'])==1
    filename=result['results'][0]['file']
    assert result['results'][0]['captions']
    clip=tmp/'jobs'/sid/'exports'/filename
    assert clip.is_file() and clip.stat().st_size>10000
    info=app.probe_video(clip)
    assert info['width']==540 and info['height']==960
    assert info['duration'] >=4.8 and info['has_audio']
    assert friend.get('/api/download/'+sid+'/'+filename).status_code==200
    assert owner.get('/api/download/'+sid+'/'+filename).status_code==404
    assert friend.get('/api/me').json()['user']['credits']==4
    # Invalid SRT should not deduct any credits.
    settings['caption_srt']='not a valid SRT file'
    err=friend.post('/api/generate',json=settings,headers=HEADER)
    assert err.status_code==400,err.text
    assert friend.get('/api/me').json()['user']['credits']==4
    req=friend.post('/api/credits/request',json={'amount':7,'message':'More Shorts'},headers=HEADER)
    assert req.status_code==200
    overview=owner.get('/api/admin/overview').json()
    request=next(x for x in overview['requests'] if x['status']=='pending')
    approval=owner.post(f"/api/admin/requests/{request['id']}/review",headers=HEADER,
            json={'action':'approve','amount':7})
    assert approval.status_code==200,approval.text
    assert friend.get('/api/me').json()['user']['credits']==11


def test_owner_unlimited_and_health(clients):
    owner,friend,tmp=clients
    assert owner.get('/api/me').json()['user']['credits'] is None
    health=owner.get('/api/health').json()
    assert health['ffmpeg'] and health['version']=='3.0'
    assert 'auto_captions' in health
