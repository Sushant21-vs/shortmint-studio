"""Small, shared yt-dlp setup for authorized public media imports.

The supported 2026 yt-dlp YouTube extractor requires its EJS package and a JS
runtime. Our Docker image supplies Node 22 + yt-dlp[default]. Deno is enabled
by yt-dlp automatically; Node must be enabled explicitly.

This does not bypass login challenges, regional restrictions, DRM, or platform
blocks of cloud hosting IP addresses.
"""
import importlib.metadata
import shutil


def javascript_runtime_options():
    """Return options for a supported installed runtime (Deno takes priority)."""
    if shutil.which('deno'):
        return []  # yt-dlp enables Deno automatically.
    if shutil.which('node'):
        return ['--js-runtimes', 'node']
    return []


def media_runtime_status():
    try:
        ytdlp = importlib.metadata.version('yt-dlp')
    except importlib.metadata.PackageNotFoundError:
        ytdlp = None
    try:
        ejs = importlib.metadata.version('yt-dlp-ejs')
    except importlib.metadata.PackageNotFoundError:
        ejs = None
    return {
        'yt_dlp_version': ytdlp,
        'yt_dlp_ejs_installed': bool(ejs),
        'javascript_runtime': 'deno' if shutil.which('deno') else ('node' if shutil.which('node') else None),
    }
