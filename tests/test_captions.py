from captions import parse_srt, stamp, clip_srt
import pytest


def test_srt_clips_source_timestamps(tmp_path):
    cues=parse_srt('1\n00:00:04,000 --> 00:00:08,000\nFirst point!\n\n2\n00:00:11,500 --> 00:00:13,000\nNext point.')
    dest=tmp_path/'test.srt'
    assert clip_srt(cues, 6, 6, dest)
    content=dest.read_text()
    assert '00:00:00,000 --> 00:00:02,000' in content
    assert '00:00:05,500 --> 00:00:06,000' in content
    assert 'First point!' in content
    assert 'Next point.' in content
    assert stamp(61.207)=='00:01:01,207'


def test_rejects_bad_or_unsafe_subtitles():
    with pytest.raises(ValueError):
        parse_srt('hello world without timestamps')
    with pytest.raises(ValueError):
        parse_srt('1\n00:00:05,000 --> 00:00:01,000\nBackwards')
    assert parse_srt('1\n00:00:00,000 --> 00:00:02,000\n{\\pos(0,0)}Safe')[0][2] == '(\\pos(0,0))Safe'
