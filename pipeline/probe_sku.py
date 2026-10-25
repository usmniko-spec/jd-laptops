import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jdlib import Fetcher, parse_sku, model_of
f = Fetcher(os.path.join(os.path.dirname(os.path.abspath(__file__)),'cache'), ttl=0, delay=(5,8))
for sku in sys.argv[1:]:
    if f.blocked: break
    h = f.get(f"https://item.m.jd.com/product/{sku}.html")
    if not h: print(f"{sku}: блок"); break
    try: p = parse_sku(h)
    except Exception: print(f"{sku}: нет данных"); continue
    if not p: print(f"{sku}: не лот"); continue
    ps = sorted(float(u['price']) for u in p['units'])
    print(f"{sku}: {model_of(p.get('cur') or '')} · {len(ps)} юнитов · {ps[:6]} · {(p.get('cur') or '')[:46]}", flush=True)
