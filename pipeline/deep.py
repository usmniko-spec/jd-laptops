#!/usr/bin/env python3
"""Глубокий обход: соседние SKU семейства + паспорта новых лотов."""
import json, os, sys, glob, time, random
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jdlib import Fetcher, parse_sku, parse_unit, model_of

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, 'config.json'), encoding='utf-8'))
TZ = timezone(timedelta(hours=7))
BUDGET = 20
SPAN = 6

def main():
    f = Fetcher(os.path.join(HERE, 'cache'), ttl=0, delay=(8, 16))
    files = sorted(glob.glob(os.path.join(HERE, 'data', 'snapshots', 'snapshot_*.json')),
                   key=lambda x: json.load(open(x, encoding='utf-8')).get('ts', ''))
    known = {l['sku'] for l in json.load(open(files[-1], encoding='utf-8'))['lots']}
    ids = set()
    for s in CFG['family_seeds']:
        for d in range(-SPAN, SPAN + 1):
            if d and f"{s+d}" not in known: ids.add(s + d)
    ids = sorted(ids)
    print(f"кандидатов: {len(ids)} · бюджет: {BUDGET}", flush=True)
    lots, units = [], []
    for sku in ids:
        if f.requests >= BUDGET or f.blocked: break
        h = f.get(f"https://item.m.jd.com/product/{sku}.html")
        if not h:
            print("  блок/ошибка, стоп", flush=True); break
        try: p = parse_sku(h)
        except Exception: continue
        if not p: continue
        mdl = model_of(p.get('cur') or '')
        print(f"  {sku} · {mdl} · юнитов {len(p['units'])}", flush=True)
        lots.append({'sku': sku, 'title': p['title'], 'cur': p.get('cur'),
                     'prices': [float(u['price']) for u in p['units']],
                     'unit_ids': [str(u['inspectSkuId']) for u in p['units']], 'units_read': 0})
        if mdl in CFG['targets'] or 'RedmiBookPro' in (p['title'] or ''):
            for u in p['units']:
                if f.requests >= BUDGET or f.blocked: break
                hh = f.get(f"https://item.m.jd.com/product/{sku}.html?inspectSkuId={u['inspectSkuId']}")
                if not hh: break
                try: units.append(parse_unit(hh, sku, u['inspectSkuId'], u['price']))
                except Exception: pass
            lots[-1]['units_read'] = sum(1 for x in units if x['sku'] == sku)
    snap = {'ts': datetime.now(TZ).isoformat(timespec='seconds'), 'source': 'deep',
            'blocked': f.blocked, 'requests': f.requests, 'units': units, 'lots': lots}
    p = os.path.join(HERE, 'data', 'snapshots', f"snapshot_{datetime.now(TZ).strftime('%Y%m%d_%H%M')}_deep.json")
    json.dump(snap, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"готово: {p} · лотов {len(lots)} · юнитов {len(units)} · запросов {f.requests} · блок {f.blocked}", flush=True)

if __name__ == '__main__':
    main()
