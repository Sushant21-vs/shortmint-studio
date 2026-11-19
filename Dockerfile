FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg fonts-dejavu-core ca-certificates gosu && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Set --build-arg WITH_AUTO_CAPTIONS=1 for optional CPU speech recognition.
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
