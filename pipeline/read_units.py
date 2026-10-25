#!/usr/bin/env python3
"""Чтение паспортов юнитов для указанных SKU (ids и цены берём из свежего лот-скана)."""
import json, os, sys, glob
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jdlib import Fetcher, parse_unit

HERE = os.path.dirname(os.path.abspath(__file__))
TZ = timezone(timedelta(hours=7))
BUDGET = int(os.environ.get('BUDGET', '22'))

def main(skus):
    files = sorted(glob.glob(os.path.join(HERE, 'data', 'snapshots', 'snapshot_*.json')),
                   key=lambda x: json.load(open(x, encoding='utf-8')).get('ts', ''))
    src = json.load(open(files[-1], encoding='utf-8'))
    lots = {str(l['sku']): l for l in src['lots']}
    f = Fetcher(os.path.join(HERE, 'cache'), ttl=6*3600, delay=(7, 11))
    units = []
    for sku in skus:
        lot = lots.get(sku)
        if not lot: print(f"  {sku}: нет в свежем скане", flush=True); continue
        for uid, price in zip(lot['unit_ids'], lot['prices']):
            if f.blocked or f.requests >= BUDGET: break
            h = f.get(f"https://item.m.jd.com/product/{sku}.html?inspectSkuId={uid}")
            if not h: break
            try: units.append(parse_unit(h, sku, uid, price))
            except Exception as e: print("  parse error", uid, e, flush=True)
        print(f"  {sku}: прочитано {sum(1 for u in units if u['sku']==sku)}", flush=True)
        if f.blocked: break
    if not units:
        print("паспорта не прочитаны (блок)"); return 2
    snap = {'ts': datetime.now(TZ).isoformat(timespec='seconds'), 'source': 'units',
            'blocked': f.blocked, 'requests': f.requests, 'units': units, 'lots': []}
    p = os.path.join(HERE, 'data', 'snapshots', f"snapshot_{datetime.now(TZ).strftime('%Y%m%d_%H%M')}_units.json")
    json.dump(snap, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"юнитов {len(units)} · запросов {f.requests} · блок {f.blocked} -> {p}", flush=True)
    for u in sorted(units, key=lambda x: x['price'])[:12]:
        print(f"   {u['price']:>6.0f} {u['cpu']:<14} {u['cond_cn']}", flush=True)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
