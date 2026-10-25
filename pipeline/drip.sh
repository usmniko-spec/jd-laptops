#!/bin/bash
# Автоцикл: всё решает auto.py. Работает и на Mac (launchd), и на VPS (systemd).
cd "$(dirname "$0")"
PY="${PY:-python3}"
# на Mac удобнее бандл-питон, на VPS — системный
if [ -x "/Users/niko/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3" ] && [ "$(uname)" = "Darwin" ]; then
  PY="/Users/niko/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3"
fi
OUT="${REPORT_OUT:-../redmibook_pro_auto.xlsx}"
{
  echo "=== $(date '+%H:%M:%S') ==="
  "$PY" auto.py
} >> "logs/auto_$(date +%Y%m%d).log" 2>&1
tail -3 "logs/auto_$(date +%Y%m%d).log"
