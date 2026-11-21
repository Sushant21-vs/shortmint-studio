"""V13: Edited montage must actually join noncontiguous moments into ONE MP4."""
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app
import accounts
from montage import plan_montage

HEADER={'X-ShortMint-Request':'1'}


def test_montage_planner_uses_multiple_non_adjacent_moments():
    for length in (12,30,75,240):
        for pace in ('fast','balanced','story'):
            cuts=plan_montage(length,min(45,length),[2,6,10,20,42],[(0,2),(14,15)],pace)
            assert len(cuts)>=2
            for i,cut in enumerate(cuts):
                assert 0<=cut['start']
                assert cut['duration']>0
                assert cut['start']+cut['duration']<=length+.02
                if i: assert cut['start']-(cuts[i-1]['start']+cuts[i-1]['duration'])>.35


def test_montage_real_api_export_and_credits(tmp_path,monkeypatch):
    monkeypatch.setattr(app,'STORAGE',tmp_path/'jobs')
    app.STORAGE.mkdir()
    monkeypatch.setattr(accounts,'DB_FILE',tmp_path/'site.sqlite3')
    accounts.init_db()
    accounts.create_owner('editing_owner','verystrongpassword123')
    original=tmp_path/'source.mp4'
    subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error',
                    '-f','lavfi','-i','testsrc2=size=280x180:rate=20:duration=13',
                    '-f','lavfi','-i','sine=frequency=600:duration=13',
                    '-c:v','libx264','-preset','ultrafast','-c:a','aac','-shortest',str(original)],
                   check=True,timeout=45)
    with TestClient(app.app) as client:
        assert client.post('/api/auth/login',json={'username':'editing_owner','password':'verystrongpassword123'},headers=HEADER).status_code==200
        with original.open('rb') as f:
            response=client.post('/api/upload',files={'file':('source.mp4',f,'video/mp4')},headers=HEADER)
        assert response.status_code==200,response.text
        sid=response.json()['id']
        requested={'session_id':sid,'mode':'montage','clip_length':15,
                   'count':1,'resolution':'540','crop_mode':'center','edit_pace':'fast',
                   'punch_zoom':True,'title':'First test','caption_srt':'1\n00:00:01,000 --> 00:00:03,000\nCut montage works'}
        response=client.post('/api/generate',json=requested,headers=HEADER)
        assert response.status_code==200,response.text
        taskid=response.json()['task_id']
        status=None
        for _ in range(250):
            status=client.get('/api/status/'+taskid).json()
            if status['state'] in ('completed','failed','cancelled'):break
            time.sleep(.15)
        assert status['state']=='completed',status
        assert len(status['results'])==1
        clip=status['results'][0]
        assert 2<=len(clip['edits'])<=12
        assert abs(sum(x['duration'] for x in clip['edits'])-clip['duration'])<.05
        info=app.probe_video(tmp_path/'jobs'/sid/'exports'/clip['file'])
        assert info['width']==540 and info['height']==960 and info['duration']>5
        assert info['has_audio']
        assert clip['captions']
        assert client.get('/api/download/'+sid+'/'+clip['file']).status_code==200
