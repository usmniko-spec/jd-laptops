#!/bin/bash
# Собирает переносимый архив пайплайна (код + данные, без кэша и логов).
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)/pipeline"
OUT="${1:-$(pwd)/jd-pipeline.tar.gz}"
cd "$SRC"
tar --exclude='cache' --exclude='logs' --exclude='__pycache__' --exclude='*.pyc' \
    -czf "$OUT" .
echo "архив: $OUT ($(du -h "$OUT" | cut -f1))"
tar -tzf "$OUT" | head -12
