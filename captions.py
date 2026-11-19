"""Subtitle parsing and source-time to clip-time SRT conversion.

Input subtitles use SOURCE-video timecodes, making it possible to reuse one
transcript for every Smart Pick. No external API is needed to burn SRT captions.
"""
import re
from pathlib import Path

TIME = re.compile(r'^\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*$')
ARROW = re.compile(r'^(.+?)\s*-->\s*(.+?)(?:\s+\S.*)?$')


def parse_time(value):
    match = TIME.fullmatch(value.strip())
    if not match:
        raise ValueError('Captions need SRT timecodes such as 00:00:01,200 --> 00:00:03,900.')
    h, m, s, ms = match.groups()
    if int(m) >= 60 or int(s) >= 60:
        raise ValueError('Invalid SRT timestamp (minutes and seconds must be under 60).')
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, '0')) / 1000


def parse_srt(srt):
    if not srt or not srt.strip():
        return []
    if len(srt) > 150_000:
        raise ValueError('Caption file is too large (max 150,000 characters).')
    srt = srt.replace('\r\n', '\n').replace('\r', '\n').lstrip('\ufeff')
    blocks = re.split(r'\n\s*\n', srt.strip())
    cues = []
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        timeline = next((i for i, l in enumerate(lines[:2]) if '-->' in l), None)
        if timeline is None:
            raise ValueError('Invalid SRT block: each caption needs a start and end time.')
        m = ARROW.fullmatch(lines[timeline])
        if not m:
            raise ValueError('Invalid SRT timing line.')
        start, end = parse_time(m.group(1)), parse_time(m.group(2))
        if not 0 <= start < end <= 86400:
            raise ValueError('SRT caption end must follow its start and be within 24 hours.')
        txt = ' '.join(lines[timeline+1:]).strip()
        if not txt:
            continue
        if len(txt) > 500:
            raise ValueError('Each caption must be at most 500 characters.')
        # Prevent subtitles containing ASS override formatting or complex payloads.
        txt = re.sub(r'<[^>]*>', '', txt).replace('{', '(').replace('}', ')')
        cues.append((start, end, txt))
        if len(cues) > 2500:
            raise ValueError('Too many caption blocks (max 2500).')
    return sorted(cues)


def stamp(seconds):
    milliseconds = round(max(0, seconds) * 1000)
    hours, rem = divmod(milliseconds, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f'{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}'


def clip_srt(cues, start, duration, path):
    """Write only source cues overlapping a given clip, shifting to clip timeline."""
    end = start + duration
    blocks = []
    for a, b, txt in cues:
        left, right = max(a, start) - start, min(b, end) - start
        if right - left >= .075:
            blocks.append(f'{len(blocks)+1}\n{stamp(left)} --> {stamp(right)}\n{txt}')
    if not blocks:
        return False
    Path(path).write_text('\n\n'.join(blocks) + '\n', encoding='utf-8')
    return True


def transcript_to_srt(segments):
    return '\n\n'.join(
        f'{i+1}\n{stamp(float(s.start))} --> {stamp(float(s.end))}\n{s.text.strip()}'
        for i, s in enumerate(segments) if s.text.strip()
    ) + '\n'
