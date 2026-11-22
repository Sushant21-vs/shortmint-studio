"""ShortMint Studio: a local-first video-to-shorts editor.

Uses FFmpeg for editing. 'Smart picks' are audio-activity heuristics, not generative AI.
Runs only on 127.0.0.1 by default via launch.py.
"""
import json
import importlib.util
import tempfile
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, HTTPException, UploadFile, Depends, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image, ImageDraw, ImageFont
from captions import parse_srt, clip_srt, transcript_to_srt
from accounts import user_for_request, install_auth_routes, reserve_credits, finish_credit_job
from downloads import source_platform, extraction_failure_message, install_download_routes
from media_runtime import javascript_runtime_options, media_runtime_status
from montage import scene_changes, plan_montage, parse_custom_cuts
from admin_backup import install_backup_routes
from voice_tools import VOICES, voice_options, validate_voice, generate_voice_mp3, whisper_srt

ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get('SHORTMINT_STORAGE_DIR') or str(ROOT / 'storage')).resolve()
STORAGE = DATA_ROOT / 'jobs'
STATIC = ROOT / 'static'
STORAGE.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_BYTES = 1024 * 1024 * 1024  # 1 GiB, locally stored
ALLOWED_EXTS = {'.mp4', '.mov', '.mkv', '.webm', '.avi', '.m4v'}
SESSIONS = {}
TASKS = {}
ACTIVE_SESSIONS = set()
VOICE_GATE = threading.BoundedSemaphore(1)
VOICE_PREVIEW_ACTIVITY = {}  # per-account 10 requests / 15 minutes
CLOUD_CAPTION_ACTIVITY = {}  # per-account 3 transcription jobs / hour
LOCK = threading.RLock()

app = FastAPI(title='ShortMint Studio v3', docs_url=None, redoc_url=None)

@app.middleware('http')
async def guard_api_actions(request: Request, call_next):
    # Extra, non-simple header prevents cross-origin forms from spending credits or uploading files.
    if request.url.path.startswith('/api/') and request.method not in ('GET','HEAD','OPTIONS'):
        if request.headers.get('X-ShortMint-Request') != '1':
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail':'App request header missing.'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    return response


def checked_project(sid, user):
    data = load_manifest(sid)
    owner_id = data.get('owner_user_id')
    if owner_id is None:
        # Legacy local projects belong exclusively to the owner after upgrading.
        if user['role'] != 'owner':
            raise HTTPException(404, 'Project not found')
    elif owner_id != user['id']:
        raise HTTPException(404,'Project not found')
    return data




def run(cmd, timeout=120, **kwargs):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kwargs)
    except subprocess.TimeoutExpired:
        raise ValueError('The video operation timed out. Try a shorter or smaller video.')
    except FileNotFoundError:
        raise ValueError('FFmpeg/FFprobe was not found. Install FFmpeg and restart the app.')


def session_folder(session_id):
    if not re.fullmatch(r'[a-f0-9]{32}', session_id or ''):
        raise HTTPException(400, 'Invalid project ID')
    folder = STORAGE / session_id
    if not folder.exists():
        raise HTTPException(404, 'Project not found')
    return folder


def save_manifest(session_id, data):
    folder = STORAGE / session_id
    temp = folder / 'manifest.tmp'
    temp.write_text(json.dumps(data, indent=2), encoding='utf-8')
    temp.replace(folder / 'manifest.json')
    with LOCK:
        SESSIONS[session_id] = data


def load_manifest(session_id):
    folder = session_folder(session_id)
    path = folder / 'manifest.json'
    if not path.exists():
        raise HTTPException(404, 'Project data missing')
    return json.loads(path.read_text(encoding='utf-8'))


def probe_video(path):
    result = run([
        'ffprobe', '-v', 'error', '-show_entries',
        'format=duration,format_name:stream=codec_type,width,height:stream_disposition=attached_pic',
        '-of', 'json', str(path)
    ], timeout=45)
    if result.returncode != 0:
        raise ValueError('This file is not a readable video.')
    data = json.loads(result.stdout)
    # FFprobe can interpret plain text as a terminal-recording (tty) video.
    # Refuse that format and still images; do not confuse artwork with footage.
    detected = set(str(data.get('format', {}).get('format_name') or '').lower().split(','))
    if detected.intersection({'tty', 'image2', 'image2pipe', 'png_pipe', 'jpeg_pipe', 'bmp_pipe', 'webp_pipe'}):
        raise ValueError('This is not a recognized video recording. Select a real video file.')
    stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'
                   and not s.get('disposition', {}).get('attached_pic')), None)
    if not stream:
        raise ValueError('No video track was found in this file.')
    duration = float(data.get('format', {}).get('duration') or 0)
    if not 0.3 < duration < 86400:
        raise ValueError('Video duration must be between 1 second and 24 hours.')
    return {
        'duration': round(duration, 2),
        'width': int(stream.get('width') or 0),
        'height': int(stream.get('height') or 0),
        'has_audio': any(s.get('codec_type') == 'audio' for s in data.get('streams', [])),
    }


def new_session(source_path, filename, owner_user_id):
    sid = source_path.parent.name
    info = probe_video(source_path)
    data = {
        'id': sid, 'filename': filename[:140], 'source': source_path.name,
        'owner_user_id': owner_user_id,
        **info, 'clips': [], 'created_at': int(time.time()),
    }
    save_manifest(sid, data)
    return public_manifest(data)


def public_manifest(data):
    result = dict(data)
    result.pop('source', None)
    result['source_url'] = '/api/media/' + data['id'] + '/source'
    return result


# v36: The Shorts editor exports up to 1080p. 4K and 8K are not available.
QUALITY_LABELS = {'540':'540p','720':'720p','1080':'1080p'}


def _server_memory_limit_mb():
    """Best known RAM limit, respecting Linux cgroups (including Render/Docker)."""
    limits = []
    for file in ('/sys/fs/cgroup/memory.max',
                 '/sys/fs/cgroup/memory/memory.limit_in_bytes'):
        try:
            value = Path(file).read_text().strip()
            if value.isdigit():
                mb = int(value) // (1024 * 1024)
                if 64 <= mb < 1024 * 1024:
                    limits.append(mb)
        except (OSError, ValueError):
            pass
    try:
        mb = os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE') // (1024 * 1024)
        if mb > 0: limits.append(mb)
    except (OSError, ValueError, AttributeError):
        pass
    return min(limits) if limits else None


def quality_availability():
    result = {}
    for width, label in QUALITY_LABELS.items():
        result[width] = {'label': label, 'width': int(width), 'height': int(width)*16//9,
                         'available': True, 'reason': 'Ready to export on this server.'}
    return {'memory_mb': _server_memory_limit_mb(), 'qualities': result,
            'note': '1080p is the maximum export quality. Upscaling a source does not restore detail.'}


@app.get('/api/export/capabilities')
def export_capabilities(user=Depends(user_for_request)):
    return quality_availability()


@app.get('/api/health')
def health():
    return {'ok': True, 'ffmpeg': bool(shutil.which('ffmpeg')), 'ffprobe': bool(shutil.which('ffprobe')),
            'auto_captions': bool(os.getenv('OPENAI_API_KEY')) or importlib.util.find_spec('faster_whisper') is not None,
            'voiceover': importlib.util.find_spec('edge_tts') is not None,
            'version': '3.0', 'studio_version': '36', **media_runtime_status()}


@app.post('/api/upload')
async def upload(file: UploadFile = File(...), user=Depends(user_for_request)):
    # Accept video containers by content, not only a short list of extensions.
    # The original name is display-only, and never used as a filesystem path.
    filename = (file.filename or 'video').replace('\\', '/').rsplit('/', 1)[-1]
    ext = Path(filename).suffix.lower()
    if not re.fullmatch(r'\.[a-z0-9]{1,10}', ext):
        ext = '.bin'
    sid = uuid.uuid4().hex
    folder = STORAGE / sid
    folder.mkdir(parents=True)
    source_path = folder / ('source' + ext)
    total = 0
    try:
        with source_path.open('wb') as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise ValueError('File is larger than 1 GB. Please use a smaller video.')
                out.write(chunk)
        if total < 1024:
            raise ValueError('The uploaded file is empty or too small.')
        return new_session(source_path, filename, user['id'])
    except ValueError as err:
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(400, str(err))
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    finally:
        await file.close()


class SocialVideoImport(BaseModel):
    url: str = Field(min_length=10, max_length=1200)
    platform: str = Field(default='', max_length=20)


IMPORT_GATE = threading.BoundedSemaphore(1)


@app.post('/api/import-url')
def import_url(body: SocialVideoImport, user=Depends(user_for_request)):
    try:
        platform = source_platform(body.url)
    except ValueError as err:
        raise HTTPException(400,str(err))
    expected = {'YouTube':'youtube','TikTok':'tiktok','Instagram':'instagram'}[platform]
    if body.platform and body.platform.lower() != expected:
        raise HTTPException(400, f'This is a {platform} URL. Select the {platform} import tab.')
    if not IMPORT_GATE.acquire(blocking=False):
        raise HTTPException(429, 'A social import is already processing. Try again after it finishes.')
    sid = uuid.uuid4().hex
    folder = STORAGE / sid
    try:
        folder.mkdir(parents=True)
        cmd = [
            sys.executable, '-m', 'yt_dlp', '--ignore-config', '--no-playlist',
            '--no-progress', '--no-write-info-json',
            '--socket-timeout', '20', '--retries', '2',
            *javascript_runtime_options(),
            '--max-filesize', '1G', '--match-filter', 'duration < 86400',
            '-f', 'bv*+ba/best', '-S', 'res:1080',
            '--merge-output-format', 'mp4', '-o', str(folder / 'source.%(ext)s'),
            '--', body.url.strip()
        ]
        proc = run(cmd, timeout=900)
        if proc.returncode != 0:
            raise ValueError(extraction_failure_message(platform, proc.stderr or proc.stdout))
        files = [p for p in folder.glob('source.*') if p.suffix.lower() in ALLOWED_EXTS]
        if not files:
            raise ValueError('No video was downloaded. Try uploading the original video file instead.')
        source = files[0]
        if source.stat().st_size > MAX_UPLOAD_BYTES:
            raise ValueError('Video is larger than 1 GB.')
        return new_session(source, f'{platform} video', user['id'])
    except ValueError as err:
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(400, str(err))
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    finally:
        IMPORT_GATE.release()


@app.get('/api/project/{session_id}')
def get_project(session_id: str, user=Depends(user_for_request)):
    return public_manifest(checked_project(session_id, user))


def source_for(data):
    return STORAGE / data['id'] / data['source']


@app.get('/api/media/{session_id}/source')
def get_source(session_id: str, user=Depends(user_for_request)):
    data = checked_project(session_id, user)
    source = source_for(data)
    if not source.is_file():
        raise HTTPException(404, 'Source video missing')
    ext = source.suffix.lower()
    source_types = {'.3gp':'video/3gpp', '.3g2':'video/3gpp2', '.ts':'video/mp2t', '.m2ts':'video/mp2t'}
    media_type = source_types.get(ext) or __import__('mimetypes').guess_type(source.name)[0] or 'application/octet-stream'
    return FileResponse(source, media_type=media_type)


@app.get('/api/media/{session_id}/{filename}')
def get_media(session_id: str, filename: str, user=Depends(user_for_request)):
    data = checked_project(session_id, user)
    if not re.fullmatch(r'[a-z0-9_]+\.mp4', filename):
        raise HTTPException(400, 'Invalid clip name')
    if filename not in [v['file'] for v in data['clips']]:
        raise HTTPException(404, 'Clip not found')
    path = session_folder(session_id) / 'exports' / filename
    if not path.is_file():
        raise HTTPException(404, 'Clip file missing')
    return FileResponse(path, media_type='video/mp4')


@app.get('/api/download/{session_id}/{filename}')
def download_clip(session_id: str, filename: str, user=Depends(user_for_request)):
    data = checked_project(session_id, user)
    if filename not in [v['file'] for v in data['clips']]:
        raise HTTPException(404, 'Clip not found')
    path = session_folder(session_id) / 'exports' / filename
    if not path.is_file():
        raise HTTPException(404, 'Clip file missing')
    return FileResponse(path, media_type='video/mp4', filename=filename)


@app.get('/api/download-all/{session_id}')
def download_all(session_id: str, user=Depends(user_for_request)):
    data = checked_project(session_id, user)
    if not data['clips']:
        raise HTTPException(404, 'Generate a short first')
    folder = session_folder(session_id)
    dest = folder / 'shortmint_shorts.zip'
    with zipfile.ZipFile(dest, 'w', compression=zipfile.ZIP_STORED) as out:
        for clip in data['clips']:
            path = folder / 'exports' / clip['file']
            if path.exists():
                out.write(path, arcname=clip['file'])
    return FileResponse(dest, media_type='application/zip', filename='ShortMint_Shorts.zip')


@app.get('/api/download-generated/{session_id}/{task_id}')
def download_generated(session_id: str, task_id: str, user=Depends(user_for_request)):
    """Download only the Shorts produced by one finished export task.

    Generated file names include the task's 8-character prefix. We verify both
    project ownership and membership in its saved manifest before zipping.
    """
    data = checked_project(session_id, user)
    if not re.fullmatch(r'[a-f0-9]{32}', task_id):
        raise HTTPException(400, 'Invalid export ID')
    prefix = f'short_{task_id[:8]}_'
    batch = [clip['file'] for clip in data['clips']
             if re.fullmatch(re.escape(prefix) + r'[0-9]{2}\.mp4', clip.get('file', ''))]
    if not batch:
        raise HTTPException(404, 'This export has no completed Shorts')
    folder = session_folder(session_id)
    output_dir = folder / 'exports'
    files = [output_dir / name for name in batch]
    if any(not f.is_file() for f in files):
        raise HTTPException(404, 'A completed Short is no longer available')
    destination = folder / f'shortmint_batch_{task_id}.zip'
    # A separate filename for each task prevents a download from being silently
    # overwritten by another batch from the same project.
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_STORED) as archive:
        for filename, source in zip(batch, files):
            archive.write(source, arcname=filename)
    return FileResponse(destination, media_type='application/zip',
                        filename=f'ShortMint_Shorts_{task_id[:8]}.zip')


def detect_silence(path, duration):
    """Return quiet intervals using FFmpeg; used for heuristic editing, not transcription."""
    proc = run([
        'ffmpeg', '-hide_banner', '-nostdin', '-i', str(path), '-vn',
        '-af', 'silencedetect=noise=-32dB:d=0.35', '-f', 'null', '-'
    ], timeout=max(180, min(1500, duration * 0.7)))
    log = proc.stderr or ''
    if proc.returncode != 0:
        return []
    starts = re.findall(r'silence_start:\s*([\d.]+)', log)
    ends = re.findall(r'silence_end:\s*([\d.]+)', log)
    # Parse in time order, including one unfinished silence at the end.
    events = re.findall(r'silence_(start|end):\s*([\d.]+)', log)
    silences = []
    start = None
    for kind, value in events:
        when = float(value)
        if kind == 'start':
            start = when
        elif start is not None:
            silences.append((start, when))
            start = None
    if start is not None:
        silences.append((start, duration))
    return silences


def suggested_clips(path, duration, clip_length, count, has_audio):
    span = min(clip_length, duration)
    if duration <= span + 0.5:
        return [{'start': 0, 'duration': round(duration, 2), 'reason': 'Full video'}]
    quiet = detect_silence(path, duration) if has_audio else []
    maximum = duration - span
    spacing = max(4.0, span / 3)
    candidates = [0.0, maximum]
    x = 0.0
    while x < maximum:
        candidates.append(x)
        x += spacing
    # Prefer clean boundaries following short pauses.
    for a, b in quiet:
        if b < maximum and b >= 0:
            candidates.append(b)

    scored = []
    for start in sorted(set(round(min(max(c, 0), maximum), 1) for c in candidates)):
        end = start + span
        quiet_sec = sum(max(0, min(end, b) - max(start, a)) for a, b in quiet)
        active_ratio = max(0.0, 1 - quiet_sec / span)
        # Varied speaking beats are helpful; still only an approximate activity measure.
        pauses = sum(1 for a, b in quiet if start < b < end and b - a < 2.5)
        pace_bonus = min(pauses, 7) * 0.024
        first_seconds_penalty = 0.12 if start < 3 else 0
        score = active_ratio * 0.72 + pace_bonus - first_seconds_penalty
        if not has_audio:
            score = 0.5
        # Gentle preference for the middle over silent intros/outros.
        score += 0.015 * math.sin(math.pi * (start + span/2)/duration)
        scored.append((score, start))

    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = []
    min_gap = min(span * .75, max(6, (duration - span) / max(count, 1) / 2))
    for score, start in scored:
        if all(abs(start - old) >= min_gap for old in selected):
            selected.append(start)
            if len(selected) >= count:
                break
    if len(selected) < count:
        for start in [i * maximum / max(count - 1, 1) for i in range(count)]:
            if all(abs(start - old) >= min_gap * 0.6 for old in selected):
                selected.append(round(start, 1))
                if len(selected) >= count:
                    break
    return [{
        'start': round(start, 2), 'duration': round(span, 2),
        'reason': 'Audio-aware pick' if has_audio else 'Evenly spaced pick'
    } for start in sorted(selected)]


def text_overlay(path, size, title, position, watermark=''):
    w, h = size
    image = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    fonts = [
        'C:/Windows/Fonts/arialbd.ttf',
        'C:/Windows/Fonts/segoeuib.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
    ]
    font = None
    for font_file in fonts:
        if Path(font_file).exists():
            font = ImageFont.truetype(font_file, int(w * 0.064))
            break
    if font is None:
        font = ImageFont.load_default(size=int(w * 0.055))

    words = title.strip().split()
    lines, current = [], ''
    for word in words:
        trial = (current + ' ' + word).strip()
        if draw.textlength(trial, font=font) > w * .83 and current:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    lines = lines[:4]
    if not lines and not watermark:
        return None
    line_height = int(w * 0.084)
    block_h = line_height * len(lines) + int(w * .09)
    block_w = min(int(w * .9), int(max((draw.textlength(line, font=font) for line in lines), default=0) + w * .11))
    if position == 'middle':
        cy = h * .5
    elif position == 'bottom':
        cy = h * .78
    else:
        cy = h * .2
    x0, y0 = (w - block_w)/2, cy - block_h/2
    if lines:
        draw.rounded_rectangle((x0, y0, x0+block_w, y0+block_h), radius=int(w * .025), fill=(5, 9, 22, 176))
    for i, line in enumerate(lines):
        tw = draw.textlength(line, font=font)
        tx = (w - tw)/2
        ty = y0 + int(w * .034) + i * line_height
        draw.text((tx, ty), line, font=font, fill='white', stroke_width=max(1,int(w*.002)), stroke_fill=(5,10,25))
    if watermark:
        wm_font = font
        for font_file in fonts:
            if Path(font_file).exists():
                wm_font = ImageFont.truetype(font_file, int(w * .038))
                break
        mark = watermark.strip()[:36]
        text_w = draw.textlength(mark, font=wm_font)
        bx = int(w * .075)
        by = int(h * .80)
        draw.rounded_rectangle((bx-int(w*.02),by-int(w*.008),bx+text_w+int(w*.02),by+int(w*.065)), radius=10, fill=(5,9,22,180))
        draw.text((bx,by), mark, font=wm_font, fill=(255,255,255,240))
    image.save(path)
    return path


# Speech recognition is an OPTIONAL add-on. On small hosts, handwritten SRT
# subtitles are reliable without extra model downloads or paid APIs.
def background_transcribe(task_id, sid):
    task = TASKS[task_id]
    try:
        data = load_manifest(sid)
        if not data['has_audio']:
            raise ValueError('The video has no audio to transcribe.')
        if os.getenv('OPENAI_API_KEY'):
            task['message'] = 'Preparing cloud transcription…'
            result = whisper_srt(source_for(data), data['duration'], task, run)
        else:
            from faster_whisper import WhisperModel
            task['state'] = 'analyzing'
            task['message'] = 'Loading local caption model (first use may download it)…'
            model = WhisperModel(os.environ.get('WHISPER_MODEL', 'tiny'), device='cpu', compute_type='int8', cpu_threads=2)
            task['message'] = 'Transcribing spoken words locally…'
            raw_segments, info = model.transcribe(str(source_for(data)), beam_size=1, vad_filter=True)
            result = transcript_to_srt(list(raw_segments))
        if len(result) > 150000:
            raise ValueError('Speech transcript too long to use as subtitles; please supply a shorter SRT.')
        if task.get('cancel'):
            task['state'] = 'cancelled'
            task['message'] = 'Caption transcription cancelled.'
            return
        if not result.strip():
            raise ValueError('No speech was detected. You can paste your own SRT captions instead.')
        # Store private transcription under the same checked project.
        (STORAGE / sid / 'captions.srt').write_text(result, encoding='utf-8')
        task['caption_srt'] = result[:150000]
        task['progress'] = 100
        task['state'] = 'completed'
        task['message'] = 'Captions ready. Review the text before exporting.'
    except Exception as err:
        task['state'] = 'failed'
        task['message'] = str(err)[:500]


@app.post('/api/captions/{session_id}/auto')
def create_auto_captions(session_id: str, user=Depends(user_for_request)):
    data = checked_project(session_id, user)
    if not data.get('has_audio'):
        raise HTTPException(400, 'This video has no audio to transcribe.')
    if not os.getenv('OPENAI_API_KEY') and importlib.util.find_spec('faster_whisper') is None:
        raise HTTPException(503, 'Auto-transcribe needs the server owner to configure OPENAI_API_KEY in Render, or install the local Whisper add-on.')
    with LOCK:
        if os.getenv('OPENAI_API_KEY'):
            if data['duration'] > 1800:
                raise HTTPException(400, 'Cloud transcription supports videos up to 30 minutes. Try a shorter source.')
            now = time.monotonic()
            recent = [t for t in CLOUD_CAPTION_ACTIVITY.get(user['id'], []) if now-t < 3600]
            if len(recent) >= 3:
                raise HTTPException(429, 'Automatic captions have a limit of 3 requests per hour per account.')
        if session_id in ACTIVE_SESSIONS:
            raise HTTPException(409, 'This video is already being processed.')
        if len(ACTIVE_SESSIONS) >= 2:
            raise HTTPException(429, 'Video server is busy. Try captions again after an export finishes.')
        task_id = uuid.uuid4().hex
        ACTIVE_SESSIONS.add(session_id)
        if os.getenv('OPENAI_API_KEY'):
            CLOUD_CAPTION_ACTIVITY[user['id']] = recent + [now]
        TASKS[task_id] = {'state': 'queued', 'progress': 3, 'message': 'Starting captions…',
                          'caption_srt': '', 'process': None, 'cancel': False, 'user_id': user['id'], 'session_id': session_id}
    def do_work():
        try:
            background_transcribe(task_id, session_id)
        finally:
            with LOCK: ACTIVE_SESSIONS.discard(session_id)
    threading.Thread(target=do_work, daemon=True).start()
    return {'task_id': task_id}


# Voiceover endpoints are private, require a signed-in user, and never expose
# upstream speech-service credentials or user-to-user audio access.
class VoicePreviewRequest(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    voice: str = 'ava'


@app.get('/api/voice/voices')
def get_voices(user=Depends(user_for_request)):
    return {'voices': voice_options(),
            'voice_available': importlib.util.find_spec('edge_tts') is not None,
            'transcription_available': bool(os.getenv('OPENAI_API_KEY')) or importlib.util.find_spec('faster_whisper') is not None}


@app.post('/api/voice/preview')
def preview_voice(body: VoicePreviewRequest, user=Depends(user_for_request)):
    try:
        validate_voice(body.voice)
    except ValueError as err:
        raise HTTPException(400, str(err))
    if not body.text.strip():
        raise HTTPException(400, 'Enter text to hear the voice.')
    with LOCK:
        now = time.monotonic()
        recent = [t for t in VOICE_PREVIEW_ACTIVITY.get(user['id'], []) if now-t < 900]
        if len(recent) >= 10:
            raise HTTPException(429, 'Voice preview limit reached. Try again in 15 minutes.')
        recent.append(now)
        VOICE_PREVIEW_ACTIVITY[user['id']] = recent
    if not VOICE_GATE.acquire(blocking=False):
        raise HTTPException(429, 'Voice generator is busy. Try again shortly.')
    try:
        with tempfile.TemporaryDirectory(prefix='sm33-voice-') as tmp:
            dest = Path(tmp) / 'preview.mp3'
            try:
                generate_voice_mp3(body.text, body.voice, dest)
            except (ValueError, RuntimeError) as err:
                raise HTTPException(503, str(err))
            return Response(content=dest.read_bytes(), media_type='audio/mpeg',
                            headers={'Cache-Control': 'no-store',
                                     'Content-Disposition': 'attachment; filename="shortmint-voice-preview.mp3"'})
    finally:
        VOICE_GATE.release()


def voiceover_mix(clip, voice_file, length, mode, task):
    """Mux narration into final MP4 (including stitched montage/cut-list clips)."""
    voice_duration = run(['ffprobe','-v','error','-show_entries','format=duration',
                          '-of','default=noprint_wrappers=1:nokey=1',str(voice_file)],timeout=20)
    if voice_duration.returncode:
        raise ValueError('Could not read the generated voice audio.')
    spoken_seconds = float(voice_duration.stdout.strip())
    if spoken_seconds > length + .12:
        raise ValueError(f'Voiceover is {spoken_seconds:.1f}s but the Short is {length:.1f}s. Shorten your narration or choose a longer Short.')
    mixed = clip.with_name(clip.stem + '_voice_tmp.mp4')
    try:
        original_audio = probe_video(clip)['has_audio']
        if mode == 'mix' and original_audio:
            filt = (f'[0:a:0]volume=0.22[background];[1:a:0]volume=1.0,'
                    f'apad,atrim=duration={length:.3f}[narration];'
                    f'[background][narration]amix=inputs=2:duration=longest:normalize=0[a]')
        else:
            filt = f'[1:a:0]apad,atrim=duration={length:.3f}[a]'
        task['message'] = 'Mixing voice narration into your Short…'
        result = run(['ffmpeg','-y','-hide_banner','-loglevel','error','-nostdin',
                     '-i',str(clip),'-i',str(voice_file),'-filter_complex',filt,
                     '-map','0:v:0','-map','[a]', '-c:v','copy','-c:a','aac',
                     '-b:a','160k','-t',f'{length:.3f}','-movflags','+faststart',str(mixed)],timeout=180)
        if result.returncode or not mixed.is_file() or mixed.stat().st_size < 1000:
            raise ValueError('Could not add narration to the MP4. ' + (result.stderr or '')[-220:])
        mixed.replace(clip)
    finally:
        mixed.unlink(missing_ok=True)


class GenerateRequest(BaseModel):
    session_id: str
    mode: str = 'auto'
    clip_length: int = Field(default=30, ge=5, le=180)
    count: int = Field(default=3, ge=1, le=8)
    start: float = Field(default=0, ge=0)
    crop_mode: str = 'center'
    resolution: str = '720'
    title: str = Field(default='', max_length=120)
    title_position: str = 'top'
    caption_srt: str = Field(default='', max_length=150000)
    watermark: str = Field(default='', max_length=36)
    focus_x: int = Field(default=50, ge=0, le=100)
    normalize_audio: bool = True
    edit_pace: str = 'fast'
    punch_zoom: bool = True
    cuts_text: str = Field(default='', max_length=1200)
    voiceover_enabled: bool = False
    voiceover_text: str = Field(default='', max_length=2000)
    voiceover_voice: str = 'ava'
    voiceover_mode: str = 'replace'


def validate_generation(data, body):
    if body.mode not in {'auto', 'manual', 'montage', 'cutlist'}:
        raise ValueError('Invalid generation mode')
    if body.crop_mode not in {'center', 'left', 'right', 'blur'}:
        raise ValueError('Invalid crop preference')
    if body.edit_pace not in {'fast','balanced','story'}:
        raise ValueError('Invalid edit pace')
    if body.resolution not in QUALITY_LABELS:
        raise ValueError('Invalid quality')
    if not quality_availability()['qualities'][body.resolution]['available']:
        raise ValueError(quality_availability()['qualities'][body.resolution]['reason'])
    if body.title_position not in {'top', 'middle', 'bottom'}:
        raise ValueError('Invalid title position')
    if body.mode == 'manual' and body.start >= data['duration']:
        raise ValueError('Start point is beyond the end of the video')
    if body.mode == 'cutlist':
        parse_custom_cuts(body.cuts_text, data['duration'])
    # Validate untrusted subtitle text before reserving any member credits.
    parse_srt(body.caption_srt)
    if body.voiceover_enabled:
        validate_voice(body.voiceover_voice)
        if body.voiceover_mode not in ('mix', 'replace'):
            raise ValueError('Choose mix or replace for narration audio.')
        if not body.voiceover_text.strip():
            raise ValueError('Enter the narration text or turn off voiceover.')
        if importlib.util.find_spec('edge_tts') is None:
            raise ValueError('Voice generation is unavailable. Install edge-tts on the server.')


def output_filter(w, h, mode, use_title, focus_x=50, caption_file=None, punch=1.0):
    if mode == 'blur':
        filt = (f'[0:v]split=2[bg][fg];'
                f'[bg]scale={w}:{h}:force_original_aspect_ratio=increase,'
                f'crop={w}:{h},boxblur=16:1[blurred];'
                f'[fg]scale={w}:{h}:force_original_aspect_ratio=decrease[foreground];'
                f'[blurred][foreground]overlay=(W-w)/2:(H-h)/2,setsar=1[base]')
    else:
        xpos = {'center':f'(in_w-out_w)*{focus_x/100:.4f}', 'left':'0', 'right':'in_w-out_w'}[mode]
        scale_w = max(w, int(round(w*punch/2)*2))
        scale_h = max(h, int(round(h*punch/2)*2))
        filt = (f'[0:v]scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,'
                f'crop={w}:{h}:{xpos}:0,setsar=1[base]')
    if use_title:
        filt += ';[base][1:v]overlay=0:0:format=auto[composed]'
    else:
        filt += ';[base]null[composed]'
    if caption_file:
        # Escaping twice (filter option + filtergraph) is needed for Windows drive colons.
        video_path = caption_file.name
        # SRT force_style is supported by FFmpeg builds with libass (standard Docker image).
        return filt + ";[composed]subtitles=filename='" + video_path + "':force_style='FontName=DejaVu Sans,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1,Bold=1,Alignment=2,MarginV=65',format=yuv420p[out]"
    return filt + ';[composed]format=yuv420p[out]'


def render_clip(source, output, start, length, body, task, total_progress_base, count, title_img, caption_file, has_audio, punch=1.0):
    w = int(body.resolution)
    h = int(round(w * 16 / 9 / 2) * 2)
    command = [
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-nostdin',
        '-ss', f'{start:.3f}', '-i', str(source),
    ]
    if title_img:
        command.extend(['-loop', '1', '-i', str(title_img)])
    command.extend([
        '-filter_complex', output_filter(w, h, body.crop_mode, bool(title_img), body.focus_x, caption_file, punch),
        '-map', '[out]', '-map', '0:a?',
        '-c:v', 'libx264', '-preset', 'veryfast',
        '-crf', '22', '-threads', '2',
        '-r', '30',
        '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
        '-c:a', 'aac', '-b:a', '160k',
        *(['-af', 'loudnorm=I=-16:TP=-1.5:LRA=11'] if body.normalize_audio and has_audio else []),
        '-t', f'{length:.3f}', '-progress', 'pipe:1', '-nostats', str(output)
    ])
    log_path = output.with_suffix('.log')
    try:
        with log_path.open('w+', encoding='utf-8') as errlog:
            p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errlog, text=True, bufsize=1, cwd=str(output.parent))
            task['process'] = p
            for line in p.stdout:
                if task.get('cancel'):
                    p.terminate()
                    break
                if line.startswith('out_time='):
                    raw = line.split('=', 1)[1].strip()
                    try:
                        hh, mm, ss = raw.split(':')
                        seconds = int(hh)*3600 + int(mm)*60 + float(ss)
                        share = min(0.99, max(0, seconds/length))
                        task['progress'] = min(99, int((total_progress_base + share) / count * 100))
                    except (ValueError, ZeroDivisionError):
                        pass
            p.wait()
            task['process'] = None
            if task.get('cancel'):
                raise RuntimeError('Export cancelled')
            if p.returncode != 0:
                errlog.seek(0)
                error = errlog.read().strip()
                raise RuntimeError('FFmpeg export failed: ' + (error[-450:] if error else 'Unknown error'))
            if not output.is_file() or output.stat().st_size < 1000:
                raise RuntimeError('Export did not create a valid video')
    finally:
        log_path.unlink(missing_ok=True)


def render_montage(source, output, edit_points, body, task, clip_i, clip_total, title_img, cues, has_audio):
    """Render individual jump-cut beats then stream-copy them into one playable Short.

    Per-segment SRT is translated to local timestamps before burning; no audio
    discontinuity is disguised as a 'transition' and the source is not repeated.
    """
    segment_dir = output.parent / ('parts_' + output.stem)
    segment_dir.mkdir(parents=True, exist_ok=True)
    files = []
    any_captions = False
    try:
        for k, edit in enumerate(edit_points):
            if task.get('cancel'):
                raise RuntimeError('Export cancelled')
            task['message'] = f'Editing cut {k+1}/{len(edit_points)} in Short {clip_i+1}/{clip_total}…'
            tmp = segment_dir / f'beat_{k:02d}.mp4'
            subtitle = segment_dir / f'beat_{k:02d}.srt'
            has_cap = clip_srt(cues, edit['start'],edit['duration'],subtitle) if cues else False
            any_captions |= bool(has_cap)
            try:
                render_clip(source, tmp, edit['start'],edit['duration'],body,task,
                            clip_i + k/len(edit_points),clip_total,
                            title_img,subtitle if has_cap else None,has_audio,
                            punch=1.075 if body.punch_zoom and k%3 == 1 else 1.0)
            finally:
                subtitle.unlink(missing_ok=True)
            files.append(tmp)
            task['progress'] = min(94,int((clip_i+(k+1)/len(edit_points))/clip_total*94))
        if len(files)==1:
            files[0].replace(output)
        else:
            # Use a path-safe concat list with relative file names, no shell execution.
            concat_file = segment_dir / 'list.txt'
            concat_file.write_text(''.join(f"file '{p.name}'\n" for p in files),encoding='utf-8')
            cmd = ['ffmpeg','-y','-hide_banner','-loglevel','error','-nostdin',
                   '-f','concat','-safe','1','-i',str(concat_file),
                   '-c','copy','-movflags','+faststart',str(output)]
            result = run(cmd,timeout=240)
            if result.returncode:
                raise RuntimeError('Could not join the edited scenes: '+result.stderr[-350:])
        if not output.is_file() or output.stat().st_size < 1000:
            raise RuntimeError('The montage export did not create a playable file.')
        return any_captions
    finally:
        shutil.rmtree(segment_dir,ignore_errors=True)


def background_generate(task_id, body):
    task = TASKS[task_id]
    sid = body.session_id
    try:
        data = load_manifest(sid)
        source = source_for(data)
        folder = source.parent / 'exports'
        folder.mkdir(parents=True, exist_ok=True)
        task['state'] = 'analyzing'
        task['message'] = 'Analyzing the source for useful cuts…'
        if body.mode == 'manual':
            segments = [{
                'start': round(body.start, 2),
                'duration': round(min(body.clip_length, data['duration'] - body.start), 2),
                'reason': 'Custom selection'
            }]
        elif body.mode == 'cutlist':
            segments=[{'start':0,'duration':0,'reason':'Custom montage',
                       'edits':parse_custom_cuts(body.cuts_text, data['duration'])}]
        elif body.mode == 'montage':
            desired = min(body.count, max(1, int(data['duration']/max(12., body.clip_length*.9))))
            # Detect large scene changes in low resolution. Speech/silence is an
            # additional heuristic; neither is equivalent to semantic AI editing.
            scenes=scene_changes(source,data['duration'])
            quiet=detect_silence(source,data['duration']) if data['has_audio'] and data['duration']<=420 else []
            segments = [{
                'start':0, 'duration':0, 'reason':'Multi-cut montage',
                'edits':plan_montage(data['duration'],body.clip_length,scenes,quiet,
                                     body.edit_pace,variant=i,variants=desired)
            } for i in range(desired)]
        else:
            segments = suggested_clips(source, data['duration'], body.clip_length, body.count, data['has_audio'])
        if not segments:
            raise RuntimeError('Unable to find a suitable section')
        task['segments'] = segments
        cues = parse_srt(body.caption_srt)
        title = body.title.strip()
        w = int(body.resolution)
        h = int(round(w * 16 / 9 / 2) * 2)
        title_img = None
        if title or body.watermark.strip():
            title_img = folder / ('title_' + task_id[:8] + '.png')
            text_overlay(title_img, (w, h), title, body.title_position, body.watermark.strip())
        created = []
        narration_path = None
        if body.voiceover_enabled:
            task['state'] = 'analyzing'
            task['message'] = 'Generating your selected narration voice…'
            if not VOICE_GATE.acquire(timeout=25):
                raise RuntimeError('Narration service is busy. Please try the export again shortly.')
            try:
                narration_path = folder / ('voice_' + task_id[:8] + '.mp3')
                generate_voice_mp3(body.voiceover_text, body.voiceover_voice, narration_path)
            finally:
                VOICE_GATE.release()
        for i, segment in enumerate(segments):
            if task.get('cancel'):
                raise RuntimeError('Export cancelled')
            task['state'] = 'rendering'
            task['message'] = f'Exporting short {i+1} of {len(segments)}…'
            filename = 'short_' + task_id[:8] + '_' + str(i+1).zfill(2) + '.mp4'
            output = folder / filename
            captions_path = folder / ('captions_' + task_id[:8] + '_' + str(i) + '.srt')
            if body.mode in {'montage','cutlist'}:
                edits = segment['edits']
                has_captions = render_montage(source,output,edits,body,task,i,len(segments),
                                               title_img,cues,data['has_audio'])
                length=sum(x['duration'] for x in edits)
            else:
                has_captions = clip_srt(cues, segment['start'], segment['duration'], captions_path) if cues else False
                try:
                    render_clip(source, output, segment['start'], segment['duration'], body,
                                task, i, len(segments), title_img, captions_path if has_captions else None, data['has_audio'])
                finally:
                    captions_path.unlink(missing_ok=True)
                length=segment['duration']
            if narration_path:
                voiceover_mix(output, narration_path, length, body.voiceover_mode, task)
            clip = {
                'file': filename, 'start': segment['start'],
                'duration': round(length,2), 'reason': segment['reason'],
                'edits':segment.get('edits',[]),
                'resolution': f'{w}x{h}', 'captions': bool(has_captions),
                'voiceover': body.voiceover_voice if body.voiceover_enabled else None, 'label': f'Short {len(data["clips"]) + len(created) + 1}',
            }
            created.append(clip)
            task['results'] = created[:]
        if title_img:
            title_img.unlink(missing_ok=True)
        data = load_manifest(sid)
        data['clips'].extend(created)
        save_manifest(sid, data)
        task['progress'] = 100
        finish_credit_job(task_id, True, len(created))
        task['state'] = 'completed'
        task['message'] = f'{len(created)} short(s) ready to download.'
    except Exception as err:
        # Clean the just-created but not-yet-recorded MP4 as well (e.g. if a
        # narration is too long after video encoding has completed).
        for file in (STORAGE / sid / 'exports').glob('short_' + task_id[:8] + '_*.mp4'):
            file.unlink(missing_ok=True)
        finish_credit_job(task_id, False)
        task['state'] = 'cancelled' if task.get('cancel') else 'failed'
        task['message'] = str(err)[:600]
    finally:
        (STORAGE / sid / 'exports' / ('voice_' + task_id[:8] + '.mp3')).unlink(missing_ok=True)
        task['process'] = None
        with LOCK:
            ACTIVE_SESSIONS.discard(sid)


@app.post('/api/generate')
def generate(body: GenerateRequest, user=Depends(user_for_request)):
    data = checked_project(body.session_id, user)
    try:
        validate_generation(data, body)
    except ValueError as err:
        raise HTTPException(400, str(err))
    with LOCK:
        if body.session_id in ACTIVE_SESSIONS:
            raise HTTPException(409, 'An export is already running for this video.')
        if len(ACTIVE_SESSIONS) >= 2:
            raise HTTPException(429,'Two exports are already running. Try again when one finishes.')
        task_id = uuid.uuid4().hex
        count = 1 if body.mode in ('manual','cutlist') or (body.mode == 'auto' and data['duration'] <= body.clip_length + 0.5) else (min(body.count,max(1,int(data['duration']/max(12.,body.clip_length*.9)))) if body.mode == 'montage' else body.count)
        reserve_credits(user, task_id, count)
        ACTIVE_SESSIONS.add(body.session_id)
        TASKS[task_id] = {
            'state': 'queued', 'progress': 0, 'message': 'Starting export…',
            'results': [], 'segments': [], 'process': None, 'cancel': False,
            'session_id': body.session_id, 'user_id': user['id'], 'resolution': body.resolution,
        }
    threading.Thread(target=background_generate, args=(task_id, body), daemon=True).start()
    return {'task_id': task_id}


@app.get('/api/status/{task_id}')
def status(task_id: str, user=Depends(user_for_request)):
    task = TASKS.get(task_id)
    if not task or task['user_id'] != user['id']:
        raise HTTPException(404, 'Export not found')
    return {k:v for k,v in task.items() if k not in {'process','user_id'}}


@app.post('/api/cancel/{task_id}')
def cancel(task_id: str, user=Depends(user_for_request)):
    task = TASKS.get(task_id)
    if not task or task['user_id'] != user['id']:
        raise HTTPException(404, 'Export not found')
    if task['state'] in ('completed', 'failed', 'cancelled'):
        return {'ok': True}
    task['cancel'] = True
    proc = task.get('process')
    if proc:
        try:
            proc.terminate()
        except OSError:
            pass
    return {'ok': True}


@app.delete('/api/project/{session_id}')
def delete_project(session_id: str, user=Depends(user_for_request)):
    checked_project(session_id, user)
    folder = session_folder(session_id)
    with LOCK:
        if session_id in ACTIVE_SESSIONS:
            raise HTTPException(409, 'Cancel the export before deleting the project.')
        SESSIONS.pop(session_id, None)
    shutil.rmtree(folder, ignore_errors=True)
    return {'ok': True}


@app.get('/api/projects')
def list_projects(user=Depends(user_for_request)):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    start_week = now.timestamp() - 7*86400
    items = []
    for manifest_path in STORAGE.glob('*/manifest.json'):
        try:
            item = json.loads(manifest_path.read_text(encoding='utf-8'))
            if item.get('owner_user_id') is None:
                if user['role'] != 'owner':
                    continue
            elif item['owner_user_id'] != user['id']:
                continue
            items.append({'id':item['id'],'filename':item.get('filename','Untitled'),
                          'created_at':item.get('created_at',0),'duration':item.get('duration',0),
                          'width':item.get('width',0),'height':item.get('height',0),
                          'shorts':len(item.get('clips',[]))})
        except (OSError, ValueError, KeyError, TypeError):
            continue
    items.sort(key=lambda x:x['created_at'],reverse=True)
    month_count=sum(1 for x in items if datetime.fromtimestamp(x['created_at'],timezone.utc).year==now.year
                    and datetime.fromtimestamp(x['created_at'],timezone.utc).month==now.month)
    return {'projects':items,'stats':{'total_projects':len(items),'this_week':sum(1 for x in items if x['created_at']>=start_week),
           'this_month':month_count,'total_shorts':sum(x['shorts'] for x in items)}}



@app.get('/api/hosting/status')
def hosting_storage_status():
    return {'persistent_accounts': bool(os.environ.get('DATABASE_URL', '').strip()),
            'database': 'PostgreSQL' if os.environ.get('DATABASE_URL', '').strip() else 'temporary SQLite',
            'video_storage_persistent': False}

install_auth_routes(app)
from growth import install_growth_routes
install_growth_routes(app)
install_backup_routes(app, has_active_exports=lambda: bool(ACTIVE_SESSIONS))
install_download_routes(app,STORAGE)
app.mount('/', StaticFiles(directory=STATIC, html=True), name='static')
