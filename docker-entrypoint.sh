#!/bin/sh
set -eu
DATA_DIR="${SHORTMINT_STORAGE_DIR:-/app/storage-data}"
mkdir -p "$DATA_DIR"
# Render mounts an initially empty persistent disk; make it writable by the app.
chown shortmint:shortmint "$DATA_DIR"
exec gosu shortmint python cloud_start.py
