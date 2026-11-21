"""v10 regression tests; no network calls, no YouTube bypasses."""
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
import media_runtime
import downloads
import app


def test_runtime_detection_selects_supported_default_or_explicit_node(monkeypatch):
    monkeypatch.setattr(media_runtime.shutil, 'which', lambda cmd: '/opt/deno' if cmd == 'deno' else None)
    assert media_runtime.javascript_runtime_options() == []
    monkeypatch.setattr(media_runtime.shutil, 'which', lambda cmd: '/usr/local/bin/node' if cmd == 'node' else None)
    assert media_runtime.javascript_runtime_options() == ['--js-runtimes', 'node']
    monkeypatch.setattr(media_runtime.shutil, 'which', lambda cmd: None)
    assert media_runtime.javascript_runtime_options() == []


def test_youtube_error_categories_are_actionable():
    a=downloads.extraction_failure_message('YouTube', "ERROR: Sign in to confirm you're not a bot.")
    assert 'blocked automated downloads' in a.lower()
    assert 'Upload file' in a
    b=downloads.extraction_failure_message('YouTube', 'WARNING: No supported JavaScript runtime could be found.')
    assert 'Dockerfile' in b
    assert 'requirements.txt' in b


def test_import_uses_js_runtime_when_available(monkeypatch, tmp_path):
    # This simulates an extractor error, not a real YouTube request.
    monkeypatch.setattr(app,'STORAGE',tmp_path)
    monkeypatch.setattr(app,'source_platform',lambda url:'YouTube')
    monkeypatch.setattr(app,'javascript_runtime_options',lambda: ['--js-runtimes','node'])
    calls=[]
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=1,stderr='ERROR: HTTP Error 403',stdout='')
    monkeypatch.setattr(app,'run',fake_run)
    with pytest.raises(app.HTTPException) as err:
        app.import_url(app.SocialVideoImport(url='https://www.youtube.com/watch?v=abcdefg',platform='youtube'),{'id':123})
    assert err.value.status_code==400
    assert calls and calls[0][calls[0].index('--js-runtimes')+1] == 'node'
    assert not list(tmp_path.iterdir())


def test_download_uses_js_and_refunds_blocked_request(monkeypatch,tmp_path):
    job_id=uuid.uuid4().hex
    folder=tmp_path/job_id;folder.mkdir()
    monkeypatch.setattr(downloads,'javascript_runtime_options',lambda:['--js-runtimes','node'])
    cmd_list=[];refunds=[]
    def fake_run(cmd,**kwargs):
        cmd_list.append(cmd)
        return SimpleNamespace(returncode=1,stderr="ERROR: Sign in to confirm you're not a bot.",stdout='')
    monkeypatch.setattr(downloads.subprocess,'run',fake_run)
    monkeypatch.setattr(downloads,'finish_download_quota',lambda job_id,ok:refunds.append(ok))
    downloads.DOWNLOAD_JOBS[job_id]={'job_id':job_id,'platform':'YouTube','state':'queued','message':''}
    downloads.ACTIVE_DOWNLOADS.add(job_id)
    try:
        downloads._download_worker(job_id,folder,'https://youtube.com/watch?v=abc','1080')
        assert cmd_list and '--js-runtimes' in cmd_list[0]
        assert refunds==[False]
        assert downloads.DOWNLOAD_JOBS[job_id]['state']=='failed'
        assert not folder.exists()
    finally:
        downloads.DOWNLOAD_JOBS.pop(job_id,None)
        downloads.ACTIVE_DOWNLOADS.discard(job_id)


def test_docker_and_requirements_include_youtube_support():
    root=Path(__file__).resolve().parents[1]
    d=(root/'Dockerfile').read_text()
    r=(root/'requirements.txt').read_text()
    assert 'node:22-bookworm-slim' in d
    assert 'COPY --from=js-runtime /usr/local/bin/node' in d
    assert 'yt-dlp[default]' in r
