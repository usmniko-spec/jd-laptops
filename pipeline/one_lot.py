#!/usr/bin/env python3
"""Полное чтение одного лота: страница + паспорта всех юнитов."""
import json, os, sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jdlib import Fetcher, parse_sku, parse_unit
HERE = os.path.dirname(os.path.abspath(__file__)); TZ = timezone(timedelta(hours=7))
sku = sys.argv[1]
f = Fetcher(os.path.join(HERE, 'cache'), ttl=0, delay=(5, 8))
h = f.get(f"https://item.m.jd.com/product/{sku}.html")
if not h: print("лот не открылся"); sys.exit(2)
p = parse_sku(h)
print(f"лот {sku}: {p['cur']} · юнитов {len(p['units'])}", flush=True)
units = []
for u in p['units']:
    if f.blocked: break
    hh = f.get(f"https://item.m.jd.com/product/{sku}.html?inspectSkuId={u['inspectSkuId']}")
    if not hh: break
    try:
        r = parse_unit(hh, sku, u['inspectSkuId'], u['price']); units.append(r)
        print(f"  {r['price']:>6.0f} {r['cpu']:<14} {r['cond_cn']} | {r['ram']}/{r['ssd']}", flush=True)
    except Exception as e: print("  parse error", e, flush=True)
lot = {'sku': str(sku), 'title': p['title'], 'cur': p.get('cur'),
       'prices': [float(u['price']) for u in p['units']],
       'unit_ids': [str(u['inspectSkuId']) for u in p['units']], 'units_read': len(units)}
snap = {'ts': datetime.now(TZ).isoformat(timespec='seconds'), 'source': 'one_lot',
        'blocked': f.blocked, 'requests': f.requests, 'units': units, 'lots': [lot]}
pt = os.path.join(HERE, 'data', 'snapshots', f"snapshot_{datetime.now(TZ).strftime('%Y%m%d_%H%M%S')}_onelot.json")
json.dump(snap, open(pt, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f"итого {len(units)}/{len(p['units'])} · блок {f.blocked} -> {pt}", flush=True)
