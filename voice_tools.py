"""Optional narrated Shorts and cloud transcription helpers.

Voice synthesis uses online edge-tts; transcription uses an operator-provided
OPENAI_API_KEY (or the optional self-hosted faster-whisper path in app.py).
No generated audio or transcription is sent to another ShortMint user.
"""
import asyncio
import os
import tempfile
from pathlib import Path

from captions import parse_srt, stamp

VOICES = {
    'ava': {'name': 'Ava', 'group': 'Female', 'style': 'Warm & clear', 'service_voice': 'en-US-AvaNeural'},
    'jenny': {'name': 'Jenny', 'group': 'Female', 'style': 'Bright & friendly', 'service_voice': 'en-US-JennyNeural'},
    'aria': {'name': 'Aria', 'group': 'Female', 'style': 'Confident & expressive', 'service_voice': 'en-US-AriaNeural'},
    'andrew': {'name': 'Andrew', 'group': 'Male', 'style': 'Natural & warm', 'service_voice': 'en-US-AndrewNeural'},
    'guy': {'name': 'Guy', 'group': 'Male', 'style': 'Clear & energetic', 'service_voice': 'en-US-GuyNeural'},
    'brian': {'name': 'Brian', 'group': 'Male', 'style': 'Smooth & relaxed', 'service_voice': 'en-US-BrianNeural'},
}


def voice_options():
    return [{'id': slug, 'name': value['name'], 'group': value['group'],
             'style': value['style']} for slug, value in VOICES.items()]


def validate_voice(voice):
    if voice not in VOICES:
        raise ValueError('Choose one of the six available voice styles.')
    return VOICES[voice]['service_voice']


def generate_voice_mp3(text, voice, destination):
    """Synthesize one supported voice into a private MP3 file, synchronously."""
    service_voice = validate_voice(voice)
    text = (text or '').strip()
    if not 1 <= len(text) <= 2000:
        raise ValueError('Voiceover text must contain 1–2,000 characters.')
    try:
        import edge_tts
    except ImportError:
        raise RuntimeError('Voice generation is unavailable on this server. Install its Python dependency (edge-tts).')
    destination = Path(destination)
    try:
        # edge-tts uses an external online speech service. It may be rate-limited.
        asyncio.run(asyncio.wait_for(edge_tts.Communicate(text, service_voice).save(str(destination)), timeout=90))
        if not destination.is_file() or destination.stat().st_size < 500:
            raise RuntimeError('The voice service did not return usable audio.')
        return destination
    except (Exception) as err:
        destination.unlink(missing_ok=True)
        if isinstance(err, ValueError):
            raise
        raise RuntimeError('Voice service is temporarily unavailable. Try again later or export without narration.') from err


def whisper_srt(source, duration, task, run):
    """Transcribe up to 30 minutes in small chunks, maintaining SOURCE timestamps.

    The API key is kept on the server only. Audio leaves the server only when
    the user explicitly chooses automatic transcription.
    """
    if not os.getenv('OPENAI_API_KEY', '').strip():
        raise RuntimeError('Automatic captions need an OpenAI API key configured by the site owner.')
    if duration > 1800:
        raise ValueError('Cloud transcription supports source videos up to 30 minutes. Trim your source or enable local Whisper.')
    import httpx
    cues = []
    with tempfile.TemporaryDirectory(prefix='sm33-transcribe-') as temp:
        for i, start in enumerate(range(0, max(1, int(duration + .999)), 600)):
            if task.get('cancel'):
                raise RuntimeError('Transcription cancelled')
            length = min(600, duration - start)
            if length < .1:
                break
            task['progress'] = min(90, int(start / max(1, duration) * 90))
            task['message'] = f'Transcribing audio section {i+1}…'
            audio = Path(temp) / f'chunk_{i}.mp3'
            result = run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-nostdin',
                          '-ss', str(start), '-i', str(source), '-t', str(length),
                          '-map', '0:a:0', '-vn', '-ac', '1', '-ar', '16000',
                          '-b:a', '48k', str(audio)], timeout=150)
            if result.returncode != 0 or not audio.is_file():
                raise ValueError('Cannot extract the audio track for transcription.')
            with audio.open('rb') as f, httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
                try:
                    response = client.post('https://api.openai.com/v1/audio/transcriptions',
                        headers={'Authorization': f"Bearer {os.environ['OPENAI_API_KEY'].strip()}"},
                        files={'file': (audio.name, f, 'audio/mpeg')},
                        data={'model': 'whisper-1', 'response_format': 'srt'})
                except httpx.HTTPError as err:
                    raise RuntimeError('The transcription service could not be reached.') from err
                if response.status_code != 200:
                    raise RuntimeError('The transcription provider could not process this audio. Check the API key, quota and provider status.')
                cues.extend((a + start, b + start, txt) for a, b, txt in parse_srt(response.text))
    if len(cues) > 2500:
        raise ValueError('Too many caption segments. Try a shorter video.')
    result = '\n\n'.join(f'{i+1}\n{stamp(a)} --> {stamp(b)}\n{text}' for i,(a,b,text) in enumerate(cues))
    if not result.strip():
        raise ValueError('No speech was detected in your video.')
    if len(result) > 150000:
        raise ValueError('Transcript is too long. Try a shorter source video.')
    return result + '\n'
