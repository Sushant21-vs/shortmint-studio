"""Lightweight multi-cut edit planning for ShortMint.

This is a heuristically edited montage, NOT semantic AI highlight detection.
Selections are drawn from several source moments; no synthetic video is created.
"""
import math
import re
import subprocess


def scene_changes(path, duration):
    """Find obvious visual scene changes with downscaled FFmpeg analysis.

    Keep scan bounded for small hosts. If FFmpeg cannot analyze, fall back to
    distributed montage cuts rather than fail the user's export.
    """
    scan = min(420.0, max(0.0, float(duration)))
    if scan < 3:
        return []
    cmd = ['ffmpeg','-hide_banner','-nostdin','-loglevel','info','-i',str(path),
           '-t',f'{scan:.2f}', '-vf', "fps=2,scale=192:-2,select='gt(scene,0.10)',showinfo",
           '-an','-f','null','-']
    try:
        result = subprocess.run(cmd, capture_output=True,text=True,timeout=min(110, max(16,int(scan*.45))))
    except (OSError, subprocess.TimeoutExpired):
        return []
    times = [float(n) for n in re.findall(r'\bpts_time:([\d.]+)',result.stderr)]
    return sorted(set(round(t,2) for t in times if 1 < t < duration-0.5))[:200]


def active_ratio(start, length, silences):
    stopped = sum(max(0., min(start+length, b)-max(start,a)) for a,b in silences)
    return max(0.,1. - min(length,stopped)/max(.001,length))


def plan_montage(duration, target_length, scenes=None, silences=None, pace='fast', variant=0, variants=1):
    """Produce 2–12 non-touching source excerpts, in narrative/source order.

    The requested target is an upper bound, not a promise of exact duration:
    we skip footage rather than duplicate it just to fill requested seconds.
    """
    duration = float(duration)
    if duration < 4:
        return [{'start':0.,'duration':round(duration,2),'reason':'Source is too short for multiple cuts'}]
    if pace not in ('fast','balanced','story'):
        raise ValueError('Invalid edit pace')
    variants = max(1,min(8,int(variants)))
    variant = int(variant)
    # Different montage outputs use different sections of a long video.
    lo,hi = duration*variant/variants,duration*(variant+1)/variants
    region = hi-lo
    if region < 6:
        lo,hi,region = 0.,duration,duration
    gap = .65 if pace=='fast' else .85
    target = max(4.,min(float(target_length),region*.81))
    shot_goal={'fast':3.1,'balanced':4.8,'story':6.8}[pace]
    shots = max(2,min(12,round(target/shot_goal)))
    # Space required for editorial jump cuts.
    while shots>2 and target+(shots-1)*gap > region:
        shots-=1
    if target+(shots-1)*gap>region:
        target=max(3.,region-(shots-1)*gap-.2)
    # Vary shot lengths: short hook, a few beats, final payoff.
    weights=([.80,1.0,1.16,.92,1.12,1.05,.82,1.16,.92,1.04,1.1,.88])[:shots]
    scale=target/sum(weights)
    lengths=[round(max(.9,w*scale),2) for w in weights]
    total=sum(lengths)
    if total+(shots-1)*gap > region:
        factor=(region-(shots-1)*gap-.15)/total
        lengths=[round(max(.55,v*factor),2) for v in lengths]
    scenes = [float(t) for t in (scenes or []) if lo<=float(t)<=hi]
    silences = [(float(a),float(b)) for a,b in (silences or []) if b>lo and a<hi]
    # Divide video into time regions; each beat comes from a different region.
    segments=[]
    for i, length in enumerate(lengths):
        a=lo+region*i/shots
        b=lo+region*(i+1)/shots
        prev_end=segments[-1]['start']+segments[-1]['duration'] if segments else lo
        # Reserve time for all remaining shots BEFORE moving this shot.
        # Without this the final beats could overrun the source duration.
        future=sum(lengths[i:])+gap*(shots-i-1)
        latest=hi-future-.02
        minimum=max(a,prev_end+gap if segments else lo)
        maximum=min(b-length-.08,hi-length,latest)
        if maximum<minimum:
            minimum=max(lo,prev_end+gap if segments else lo)
            maximum=max(minimum, min(hi-length,latest))
        anchor=min(max(a+(.11 if i==0 else .30)*(b-a)-length*.1,minimum),maximum)
        # Bias start toward real scene boundaries, speech-resumption points,
        # and sustained audio, but stay in the current chronological region.
        candidates=[anchor,minimum,maximum]
        candidates += [t+.05 for t in scenes if minimum<=t+.05<=maximum]
        candidates += [end+.10 for begin,end in silences if minimum<=end+.10<=maximum]
        # A few other candidates avoid choosing silence when there are no scenes.
        candidates += [minimum+(maximum-minimum)*q for q in (.25,.5,.75)]
        ranked=[]
        for t in candidates:
            if not minimum-.001<=t<=maximum+.001:
                continue
            r=active_ratio(t,length,silences)
            visual_bonus=.1 if any(abs(t-s)<.35 for s in scenes) else 0
            align_penalty=.07*abs(t-anchor)/max(1.,b-a)
            ranked.append((r*.8+visual_bonus-align_penalty,t))
        start=max(minimum,min(maximum,max(ranked,key=lambda item:item[0])[1] if ranked else anchor))
        segments.append({'start':round(start,2),'duration':round(length,2),
                         'reason':'Scene / speech-aware cut' if scenes or silences else 'Distributed jump cut'})
    return segments


def parse_custom_cuts(text, duration):
    """Parse user-selected ranges such as 00:12-00:16, one per line."""
    def timestamp(value):
        parts=value.strip().split(':')
        if len(parts)>3 or not parts or not all(re.fullmatch(r'\d+(?:\.\d+)?', p) for p in parts):
            raise ValueError('Use timestamps like 00:12-00:16, one range per line.')
        amount=0.
        for n in parts:
            amount=amount*60+float(n)
        return amount
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    if len(lines)<2 or len(lines)>12:
        raise ValueError('Custom montage needs 2–12 cut ranges, one per line.')
    cuts=[]
    for line in lines:
        if line.count('-')!=1:
            raise ValueError('Use a dash between the start and end, like 00:12-00:17.')
        a,b=(timestamp(s) for s in line.split('-',1))
        if a<0 or b-a<.5 or b>duration+.04:
            raise ValueError('Every cut must last at least 0.5s and stay within the source video.')
        cuts.append({'start':round(a,2),'duration':round(b-a,2),'reason':'Hand-selected edit'})
    if sum(c['duration'] for c in cuts)>180.05:
        raise ValueError('Keep your final montage under 3 minutes.')
    return cuts
