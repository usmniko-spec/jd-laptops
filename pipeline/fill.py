#!/usr/bin/env python3
"""Дочитывает только те юниты лотов, у которых нет паспорта."""
import json, os, sys, glob
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jdlib import Fetcher, parse_unit
HERE = os.path.dirname(os.path.abspath(__file__)); TZ = timezone(timedelta(hours=7))
BUDGET = int(os.environ.get('BUDGET','20'))
reg = json.load(open(os.path.join(HERE,'data','registry.json'), encoding='utf-8'))
files = sorted(glob.glob(os.path.join(HERE,'data','snapshots','snapshot_*.json')),
               key=lambda x: json.load(open(x, encoding='utf-8')).get('ts',''))
lots = {}
for f in files:
    s = json.load(open(f, encoding='utf-8'))
    for l in s.get('lots', []):
        if l.get('unit_ids'): lots[str(l['sku'])] = l
f = Fetcher(os.path.join(HERE,'cache'), ttl=0, delay=(5,8))
units = []
for sku in sys.argv[1:]:
    l = lots.get(str(sku))
    if not l: print(f"{sku}: нет лота"); continue
    todo = [(u,p) for u,p in zip(l['unit_ids'], l['prices']) if str(u) not in reg]
    print(f"{sku}: осталось {len(todo)}", flush=True)
    for uid, price in todo:
        if f.blocked or f.requests >= BUDGET: break
        h = f.get(f"https://item.m.jd.com/product/{sku}.html?inspectSkuId={uid}")
        if not h: break
        try:
            r = parse_unit(h, sku, uid, price); units.append(r)
            print(f"  {r['price']:>6.0f} {r['cpu']:<14} {r['cond_cn']}", flush=True)
        except Exception as e: print("  err", e, flush=True)
    if f.blocked: break
if units:
    snap = {'ts': datetime.now(TZ).isoformat(timespec='seconds'), 'source': 'fill',
            'blocked': f.blocked, 'requests': f.requests, 'units': units, 'lots': []}
    p = os.path.join(HERE,'data','snapshots',f"snapshot_{datetime.now(TZ).strftime('%Y%m%d_%H%M%S')}_fill.json")
    json.dump(snap, open(p,'w',encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"добрано {len(units)} · блок {f.blocked}")
