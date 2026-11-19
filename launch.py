"""Launch the localhost-only ShortMint Studio browser app."""
from pathlib import Path
import shutil
import threading
import time
import webbrowser

if __name__ == '__main__':
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise SystemExit('FFmpeg and FFprobe must be on your PATH. See README.md.')
    from app import app
    import uvicorn

    def open_browser():
        time.sleep(1.3)
        webbrowser.open('http://127.0.0.1:8765')

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host='127.0.0.1', port=8765, log_level='warning')
