#!/bin/bash
# Ежедневный прогон: сбор -> отчёт. Блокировка JD не ломает прошлые данные.
set -uo pipefail
cd "$(dirname "$0")"
PY="/Users/niko/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3"
STAMP=$(date +%Y%m%d_%H%M)
{
  echo "=== $STAMP START ==="
  "$PY" collect.py collect
  RC=$?
  echo "collect rc=$RC"
  if [ $RC -eq 3 ]; then echo "JD заблокирован — отчёт строим по последнему снимку"; fi
  "$PY" track.py
  "$PY" report.py --out "../redmibook_pro_auto.xlsx"
  echo "=== $STAMP DONE ==="
} >> "logs/run_${STAMP}.log" 2>&1
tail -5 "logs/run_${STAMP}.log"
