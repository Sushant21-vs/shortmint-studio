"""Offline regression checks for ShortMint v9 source/import fixes."""
import subprocess
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
import downloads


def test_portrait_quality_choice_and_display_rules():
    # Real social vertical videos are e.g. 1080x1920; don't filter by height.
    for q in ('720','1080','1440','2160'):
        assert downloads.quality_format(q) == 'bv*+ba/best'
    assert min(1080,1920) == 1080
    assert min(2160,3840) == 2160


def test_human_readable_error_mapping():
    yt=downloads.extraction_failure_message('YouTube',
          "ERROR: [youtube] abc: Sign in to confirm you're not a bot. Use --cookies-from-browser chrome")
    assert 'blocked automated downloads' in yt.lower()
    assert '--cookies' not in yt
    assert 'Upload file' in yt
    ig=downloads.extraction_failure_message('Instagram',
          'ERROR: Requested format is not available')
    assert '1080p' in ig
    tk=downloads.extraction_failure_message('TikTok','ERROR HTTP Error 403 Forbidden')
    assert '403' in tk


def test_worker_returns_quota_after_bot_block(tmp_path,monkeypatch):
    job_id=uuid.uuid4().hex
    folder=tmp_path/job_id
    folder.mkdir()
    logged=[]
    def fake_run(cmd, **kwargs):
        assert '-S' in cmd
        assert cmd[cmd.index('-S')+1]=='res:1080'
        assert '-f' in cmd and cmd[cmd.index('-f')+1]=='bv*+ba/best'
        return SimpleNamespace(returncode=1,
             stderr="ERROR: Sign in to confirm you're not a bot. Use --cookies")
    monkeypatch.setattr(downloads.subprocess,'run',fake_run)
    monkeypatch.setattr(downloads,'finish_download_quota',lambda job,success:logged.append((job,success)))
    downloads.DOWNLOAD_JOBS[job_id]={'job_id':job_id,'platform':'YouTube','state':'queued','message':''}
    downloads.ACTIVE_DOWNLOADS.add(job_id)
    try:
        downloads._download_worker(job_id,folder,'https://www.youtube.com/watch?v=abc','1080')
        result=downloads.DOWNLOAD_JOBS[job_id]
        assert result['state']=='failed'
        assert 'blocked automated downloads' in result['message']
        assert logged==[(job_id,False)]
        assert not folder.exists()
        assert job_id not in downloads.ACTIVE_DOWNLOADS
    finally:
        downloads.DOWNLOAD_JOBS.pop(job_id,None)
        downloads.ACTIVE_DOWNLOADS.discard(job_id)
