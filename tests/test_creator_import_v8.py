"""Offline social video import integration checks (no network or third-party bypass)."""
import subprocess
from pathlib import Path
from types import SimpleNamespace
from fastapi.testclient import TestClient
import pytest
import accounts
import app

HEADERS={'X-ShortMint-Request':'1'}

@pytest.fixture()
def owner(tmp_path,monkeypatch):
    monkeypatch.setattr(accounts,'DB_FILE',tmp_path/'accounts.sqlite')
    accounts.init_db()
    accounts.create_owner('v8owner','long_passphrase_for_testing_8')
    monkeypatch.setattr(app,'STORAGE',tmp_path/'jobs')
    app.STORAGE.mkdir()
    with TestClient(app.app) as client:
        r=client.post('/api/auth/login',headers=HEADERS,json={'username':'v8owner','password':'long_passphrase_for_testing_8'})
        assert r.status_code==200
        yield client, tmp_path

@pytest.mark.parametrize('source,url',[
   ('youtube','https://www.youtube.com/shorts/abc123'),
   ('tiktok','https://www.tiktok.com/@user/video/1234567890'),
   ('instagram','https://www.instagram.com/reel/abc123/'),
])
def test_mocked_social_import_reaches_editor(owner,monkeypatch,source,url):
    client,root=owner
    clip=root/'source.mp4'
    p=subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=144x256:r=12',
        '-t','2','-c:v','mpeg4','-y',str(clip)],capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    real_run=app.run
    def fake_run(cmd,timeout=120,**kwargs):
        if 'yt_dlp' in cmd:
            out=Path(cmd[cmd.index('-o')+1].replace('%(ext)s','mp4'))
            out.write_bytes(clip.read_bytes())
            return SimpleNamespace(returncode=0,stderr='',stdout='')
        return real_run(cmd,timeout=timeout,**kwargs)
    monkeypatch.setattr(app,'run',fake_run)
    result=client.post('/api/import-url',headers=HEADERS,json={'url':url,'platform':source,'rights_confirmed':True})
    assert result.status_code==200,result.text
    data=result.json()
    assert {'youtube':'YouTube','tiktok':'TikTok','instagram':'Instagram'}[source] in data['filename']
    assert data['duration']>1
    assert client.get('/api/project/'+data['id']).status_code==200
    assert client.get('/api/media/'+data['id']+'/source').status_code==200


def test_wrong_source_permission_and_private_url(owner):
    client,_=owner
    src='https://www.tiktok.com/@creator/video/123'
    assert client.post('/api/import-url',headers=HEADERS,json={'url':src,'platform':'instagram','rights_confirmed':True}).status_code==400
    r=client.post('/api/import-url',headers=HEADERS,json={'url':src,'platform':'tiktok','rights_confirmed':False})
    assert r.status_code==400 and 'permission' in r.json()['detail']
    assert client.post('/api/import-url',headers=HEADERS,json={'url':'https://127.0.0.1/private','platform':'youtube','rights_confirmed':True}).status_code==400
