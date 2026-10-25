#!/usr/bin/env python3
"""Добавляет unit_ids в старые снимки из сохранённых страниц (разово)."""
import json, os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jdlib import parse_sku
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = '/tmp/jd'

def main():
    files = sorted(glob.glob(os.path.join(HERE, 'data', 'snapshots', 'snapshot_*.json')),
                   key=lambda x: json.load(open(x, encoding='utf-8')).get('ts', ''))
    snap = json.load(open(files[-1], encoding='utf-8'))
    ids = {}
    fam = os.path.join(SRC, 'family.json')
    if os.path.exists(fam):
        for r in json.load(open(fam, encoding='utf-8')):
            ids[str(r['sku'])] = [str(u['inspectSkuId']) for u in r.get('units', [])]
    for pth in glob.glob(os.path.join(SRC, 'p_*.html')):
        sku = os.path.basename(pth)[2:-5]
        try:
            p = parse_sku(open(pth, encoding='utf-8', errors='ignore').read())
            if p: ids[sku] = [str(u['inspectSkuId']) for u in p['units']]
        except Exception: pass
    u2 = os.path.join(SRC, 'u2.html')
    if os.path.exists(u2):
        p = parse_sku(open(u2, encoding='utf-8', errors='ignore').read())
        if p: ids[str(p['sku'])] = [str(u['inspectSkuId']) for u in p['units']]
    n = 0
    for lot in snap['lots']:
        if not lot.get('unit_ids') and lot['sku'] in ids:
            lot['unit_ids'] = ids[lot['sku']]; n += 1
    out = os.path.join(HERE, 'data', 'snapshots', 'snapshot_20261023_1410_base.json')
    snap['ts'] = '2026-10-23T14:10:00+07:00'
    json.dump(snap, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"лотов с unit_ids: {n} из {len(snap['lots'])} -> {out}")

if __name__ == '__main__':
    main()
