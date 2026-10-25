#!/bin/bash
# Проверка, пускает ли JD с этого IP: 1 запрос, без последствий.
cd "$(dirname "$0")/../pipeline"
PY="${PY:-python3}"
"$PY" - <<'PY'
import sys; sys.path.insert(0,'.')
from jdlib import Fetcher
f=Fetcher('/tmp/jd-check', delay=(0,0))
h=f.get('https://item.m.jd.com/product/10137951520213.html')
if h and 'inspectyoupin' in h: print(f"JD доступен: {len(h)} байт")
elif h: print("JD ответил заглушкой — IP под подозрением")
else: print(f"JD заблокировал: {f.block_kind or 'unknown'}")
PY
