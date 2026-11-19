"""Authenticated, quota-limited downloads of publicly accessible videos.

Uses yt-dlp for a small allowlist of social video hosts. No private login,
DRM decryption, cookie forwarding, playlist scraping, or site bypassing.
"""
import json
import mimetypes
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from accounts import (
    download_quota, download_credit_cost, finish_download_quota,
    reserve_download_quota, user_for_request,
)

# Explicit hostnames rather than accepting arbitrary URLs: the backend makes
# outbound requests and must not expose general-purpose internal HTTP access.
SUPPORTED_HOSTS = {
    'youtube.com': 'YouTube', 'www.youtube.com': 'YouTube',
    'm.youtube.com': 'YouTube', 'music.youtube.com': 'YouTube',
    'youtu.be': 'YouTube', 'www.youtu.be': 'YouTube',
    'youtube-nocookie.com': 'YouTube', 'www.youtube-nocookie.com': 'YouTube',
    'tiktok.com': 'TikTok', 'www.tiktok.com': 'TikTok',
    'm.tiktok.com': 'TikTok', 'vm.tiktok.com': 'TikTok',
    'vt.tiktok.com': 'TikTok',
    'instagram.com': 'Instagram', 'www.instagram.com': 'Instagram',
    'm.instagram.com': 'Instagram', 'instagr.am': 'Instagram',
    'www.instagr.am': 'Instagram',
}

MAX_MEDIA_BYTES = 350 * 1024 * 1024
FILE_RETENTION_SECONDS = 6 * 60 * 60
DOWNLOAD_JOBS = {}
DOWNLOAD_LOCK = threading.RLock()
ACTIVE_DOWNLOADS = set()


def source_platform(url):
    try:
        value = url.strip()
        parsed = urlsplit(value)
        host = (parsed.hostname or '').lower()
        if (parsed.scheme != 'https' or not host in SUPPORTED_HOSTS or
                parsed.username is not None or parsed.password is not None or
                parsed.port not in (None, 443) or not parsed.path and not parsed.query):
            raise ValueError('Paste a public HTTPS video link from YouTube, TikTok or Instagram.')
        return SUPPORTED_HOSTS[host]
    except (ValueError, AttributeError):
        raise ValueError('Paste a public HTTPS video link from YouTube, TikTok or Instagram.')


class DownloadRequest(BaseModel):
    url: str = Field(min_length=12, max_length=1200)
    quality: str = Field(default='1080')
    rights_confirmed: bool = False


def quality_format(quality):
    if quality == '2160':
        # Require actual 4K source; never upscale or mislabel an HD download.
        return 'bv*[height>=2160][height<=3840]+ba/b[height>=2160][height<=3840]'
    if quality == '1440':
        return 'bv*[height>=1440][height<=1440]+ba/b[height>=1440][height<=1440]'
    return f'bv*[height<={int(quality)}]+ba/b[height<={int(quality)}]'


def video_metadata(path):
    proc = subprocess.run([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height:format=duration',
        '-of', 'json', str(path)
    ], capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise ValueError('The downloaded video could not be verified.')
    obj = json.loads(proc.stdout)
    info = (obj.get('streams') or [{}])[0]
    width, height = int(info.get('width') or 0), int(info.get('height') or 0)
    if width < 1 or height < 1:
        raise ValueError('No video stream was found.')
    return {'width':width,'height':height,'duration':float(obj.get('format',{}).get('duration') or 0)}


def safe_job_id(job_id):
    if not re.fullmatch(r'[a-f0-9]{32}', job_id):
        raise HTTPException(404,'Download not found.')


def import_format():
    return 'bv*[height<=1080]+ba/b[height<=1080]/best'


def _download_worker(job_id, folder, url, quality):
    job = DOWNLOAD_JOBS[job_id]
    ok = False
    try:
        job['state'] = 'downloading'
        job['message'] = 'Retrieving video from the source platform…'
        selector = quality_format(quality)
        # yt-dlp manages the platform-specific URL/stream selection. No cookies,
        # private authentication, arbitrary extractor names or browser profiles.
        cmd = [
            sys.executable, '-m', 'yt_dlp', '--ignore-config',
            '--no-playlist', '--playlist-items', '1', '--max-downloads', '1',
            '--no-progress', '--no-warnings', '--no-write-info-json',
            '--no-write-thumbnail', '--no-write-subs',
            '--socket-timeout', '15', '--retries', '2', '--fragment-retries', '2',
            '--max-filesize', '350M', '-f', selector,
            '--merge-output-format', 'mp4',
            '-o', str(folder / 'video.%(ext)s'), '--', url,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            logs = (proc.stderr or proc.stdout or '').splitlines()
            reason = (logs[-1] if logs else 'The source platform rejected this video.')[-270:]
            raise ValueError(f'Could not download this public video: {reason}')
        files = [p for p in folder.glob('video.*')
                 if p.suffix.lower() in {'.mp4','.webm','.mkv','.mov'} and p.is_file()]
        if len(files) != 1:
            raise ValueError('No playable video was returned. Try a different public link.')
        file = files[0]
        if file.stat().st_size > MAX_MEDIA_BYTES:
            raise ValueError('This file exceeds the free server limit of 350 MB.')
        info = video_metadata(file)
        if quality in ('1440','2160') and info['height'] < int(quality):
            raise ValueError(f'{quality}p is not available from this source. Choose a lower quality.')
        if quality == '2160' and info['width'] < 1000:
            raise ValueError('The platform did not provide a verifiable 4K video.')
        info.update({'file':file.name,'quality':quality,'job_id':job_id,
                     'platform':job['platform'],'created_at':int(time.time())})
        (folder / 'meta.json').write_text(json.dumps(info),encoding='utf-8')
        ok = True
    except subprocess.TimeoutExpired:
        job.update({'state':'failed','message':'The source took too long. Try a smaller video or direct file upload.'})
    except Exception as exc:
        job.update({'state':'failed','message':str(exc)[:450]})
    finally:
        if not ok:
            shutil.rmtree(folder, ignore_errors=True)
        finish_download_quota(job_id,ok)
        if ok:
            job.update({'state':'completed','message':'Video ready to download.','result':info})
        with DOWNLOAD_LOCK:
            ACTIVE_DOWNLOADS.discard(job_id)


def prune_download_files(root):
    """Clean temporary downloads older than six hours to limit free disk use."""
    now=time.time()
    for path in root.iterdir():
        if not path.is_dir() or not re.fullmatch(r'[a-f0-9]{32}',path.name):
            continue
        if path.name in ACTIVE_DOWNLOADS:
            continue
        try:
            if now-path.stat().st_mtime > FILE_RETENTION_SECONDS:
                shutil.rmtree(path,ignore_errors=True)
        except OSError:
            continue


def install_download_routes(app, storage):
    download_root = storage / '_downloads'
    download_root.mkdir(parents=True, exist_ok=True)

    @app.get('/api/downloads/quota')
    def get_quota(user=Depends(user_for_request)):
        return download_quota(user)

    @app.post('/api/downloads/start')
    def start_download(body:DownloadRequest,user=Depends(user_for_request)):
        if not body.rights_confirmed:
            raise HTTPException(400,'Confirm you own this video or have permission to download it.')
        try:
            platform = source_platform(body.url)
        except ValueError as exc:
            raise HTTPException(400,str(exc))
        cost=download_credit_cost(body.quality)
        job_id=uuid.uuid4().hex
        folder = download_root / job_id
        with DOWNLOAD_LOCK:
            prune_download_files(download_root)
            if len(ACTIVE_DOWNLOADS) >= 1:
                raise HTTPException(429,'The free download server is busy. Try again after the current download finishes.')
            # Check permissions and quota transactionally before creating files.
            reserve_download_quota(user,job_id,body.quality)
            try:
                folder.mkdir(parents=True)
                DOWNLOAD_JOBS[job_id]={
                    'job_id':job_id,'user_id':user['id'],'platform':platform,
                    'state':'queued','message':'Preparing download…','cost':cost,
                    'result':None,
                }
                ACTIVE_DOWNLOADS.add(job_id)
                threading.Thread(target=_download_worker,args=(job_id,folder,body.url,body.quality),daemon=True).start()
            except Exception:
                ACTIVE_DOWNLOADS.discard(job_id)
                DOWNLOAD_JOBS.pop(job_id,None)
                shutil.rmtree(folder,ignore_errors=True)
                finish_download_quota(job_id,False)
                raise
        return {'job_id':job_id,'cost':cost,'platform':platform}

    @app.get('/api/downloads/status/{job_id}')
    def get_status(job_id:str,user=Depends(user_for_request)):
        safe_job_id(job_id)
        job=DOWNLOAD_JOBS.get(job_id)
        if not job or job['user_id'] != user['id']:
            raise HTTPException(404,'Download not found.')
        return {k:v for k,v in job.items() if k != 'user_id'}

    @app.get('/api/downloads/file/{job_id}')
    def get_file(job_id:str,user=Depends(user_for_request)):
        safe_job_id(job_id)
        # Successful files stay private, even across process restarts.
        meta_path=download_root / job_id / 'meta.json'
        if not meta_path.exists():
            raise HTTPException(404,'Download expired or is not ready.')
        from accounts import db
        with db() as con:
            row=con.execute("SELECT user_id,status FROM daily_downloads WHERE job_id=?",(job_id,)).fetchone()
        if not row or row['user_id'] != user['id'] or row['status'] != 'used':
            raise HTTPException(404,'Download not found.')
        info=json.loads(meta_path.read_text(encoding='utf-8'))
        file=download_root / job_id / info['file']
        if not file.exists() or not file.is_file():
            raise HTTPException(404,'Download file no longer available.')
        return FileResponse(file,media_type=mimetypes.guess_type(file.name)[0] or 'application/octet-stream',
                            filename=f'ShortMint_{info["platform"]}_{job_id[:8]}{file.suffix}')

    @app.get('/api/downloads/recent')
    def recent(user=Depends(user_for_request)):
        with DOWNLOAD_LOCK:
            prune_download_files(download_root)
        from accounts import db
        with db() as con:
            rows=con.execute("""SELECT job_id FROM daily_downloads WHERE user_id=? AND status='used'
                              ORDER BY created_at DESC LIMIT 15""",(user['id'],)).fetchall()
        items=[]
        for row in rows:
            path=download_root / row['job_id'] / 'meta.json'
            if path.is_file():
                try:
                    meta=json.loads(path.read_text(encoding='utf-8'))
                    if (path.parent / meta['file']).is_file():
                        items.append(meta)
                except (OSError,KeyError,ValueError):
                    pass
        return {'items':items}
