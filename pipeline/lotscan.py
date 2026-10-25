#!/usr/bin/env python3
"""Дешёвый скан: только страницы лотов (состав + цены), без паспортов юнитов."""
import json, os, sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jdlib import Fetcher, parse_sku

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, 'config.json'), encoding='utf-8'))
TZ = timezone(timedelta(hours=7))

def main():
    f = Fetcher(os.path.join(HERE, 'cache'), ttl=0, delay=(7, 11))
    lots = []
    for sku in CFG['known_skus']:
        if f.blocked: break
        h = f.get(f"https://item.m.jd.com/product/{sku}.html")
        if not h:
            print(f"  {sku}: заглушка/блок, стоп", flush=True); break
        try: p = parse_sku(h)
        except Exception as e:
            print(f"  {sku}: parse error {e}", flush=True); continue
        if not p: continue
        lots.append({'sku': str(p['sku']), 'title': p['title'], 'cur': p.get('cur'),
                     'prices': [float(u['price']) for u in p['units']],
                     'unit_ids': [str(u['inspectSkuId']) for u in p['units']], 'units_read': 0})
        print(f"  {sku}: {len(p['units'])} юнитов, {min(lots[-1]['prices']):.0f}-{max(lots[-1]['prices']):.0f} ¥", flush=True)
    if not lots:
        print("данных нет — блок"); return 2
    snap = {'ts': datetime.now(TZ).isoformat(timespec='seconds'), 'source': 'lotscan',
            'blocked': f.blocked, 'requests': f.requests, 'units': [], 'lots': lots}
    pth = os.path.join(HERE, 'data', 'snapshots', f"snapshot_{datetime.now(TZ).strftime('%Y%m%d_%H%M')}_lotscan.json")
    json.dump(snap, open(pth, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"лотов {len(lots)} · запросов {f.requests} · блок {f.blocked} -> {pth}", flush=True)
    return 0

if __name__ == '__main__':
    sys.exit(main())
