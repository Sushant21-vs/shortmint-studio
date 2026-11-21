# A supported JS runtime + yt-dlp EJS are required for modern YouTube formats.
# Pin both images to the same Debian family for binary compatibility.
FROM node:22-bookworm-slim AS js-runtime
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg fonts-dejavu-core ca-certificates gosu libstdc++6 && \
    rm -rf /var/lib/apt/lists/*
COPY --from=js-runtime /usr/local/bin/node /usr/local/bin/node
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    node --version && python -m yt_dlp --version
# Optional CPU speech-to-text; not enabled on free Render hosting.
ARG WITH_AUTO_CAPTIONS=0
COPY requirements-auto-captions.txt .
RUN if [ "$WITH_AUTO_CAPTIONS" = "1" ]; then pip install --no-cache-dir -r requirements-auto-captions.txt; fi
COPY . .
RUN chmod +x /app/docker-entrypoint.sh
RUN mkdir -p /app/storage/jobs /app/storage-data && \
    useradd --uid 10001 --create-home --shell /usr/sbin/nologin shortmint && \
    chown -R shortmint:shortmint /app/storage /app/storage-data
ENV SHORTMINT_STORAGE_DIR=/app/storage-data PORT=10000
EXPOSE 10000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
