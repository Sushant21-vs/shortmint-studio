"""Optional LOCAL file import for videos users are authorized to download/edit.

Uses the user's own network, not the Render cloud server. No cookies,
platform-login bypass, or DRM support. Files are saved to Downloads/ShortMint Imports
for upload via the ShortMint website's existing Upload file tab.
"""
from pathlib import Path
import shutil
import subprocess
import sys
from media_runtime import javascript_runtime_options
from downloads import source_platform


def build_command(url, outdir):
    return [sys.executable, '-m', 'yt_dlp', '--ignore-config', '--no-playlist',
            '--no-progress', '--socket-timeout', '20', '--retries', '2',
            *javascript_runtime_options(),
            '--max-filesize', '1G', '-f', 'bv*+ba/best', '-S', 'res:1080',
            '--merge-output-format', 'mp4',
            '-o', str(outdir / 'ShortMint_%(title).80B_%(id)s.%(ext)s'), '--', url]


def main():
    print('ShortMint Local Import — for videos you have permission to download.\n')
    print('This downloads using your own computer and connection instead of Render.')
    print('No login cookies or account passwords are requested.\n')
    if not shutil.which('ffmpeg'):
        print('FFmpeg was not found. Install FFmpeg and reopen the terminal.')
        return 2
    url=input('Paste a YouTube, TikTok or Instagram video URL: ').strip()
    try:
        platform=source_platform(url)
    except ValueError as exc:
        print('Invalid link:',exc)
        return 2
    if platform=='YouTube' and not (shutil.which('deno') or shutil.which('node')):
        print('Tip: YouTube support improves with a current Node.js or Deno runtime.')
    outdir=Path.home()/'Downloads'/'ShortMint Imports'
    outdir.mkdir(parents=True,exist_ok=True)
    result=subprocess.run(build_command(url,outdir),check=False)
    if result.returncode:
        print('\nThe source platform did not allow this download. Try the original video file.')
        return result.returncode
    print('\nDownload completed. Files are in:',outdir)
    print('Open ShortMint online → Create Shorts → Upload file, then choose your MP4.')
    return 0

if __name__=='__main__':
    sys.exit(main())
