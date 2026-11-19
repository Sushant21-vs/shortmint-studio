#!/bin/sh
set -e
cd "$(dirname "$0")"
command -v ffmpeg >/dev/null || { echo 'Install FFmpeg first.'; exit 1; }
command -v python3 >/dev/null || { echo 'Install Python 3.11+ first.'; exit 1; }
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -q
.venv/bin/python setup_owner.py
.venv/bin/python launch.py
