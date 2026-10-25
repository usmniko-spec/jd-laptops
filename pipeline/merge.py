#!/usr/bin/env python3
"""Склеивает все снимки в один мастер-снимок (юниты — по № отчёта, лоты — по SKU)."""
import json, os, sys, glob
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
TZ = timezone(timedelta(hours=7))

def main():
    files = sorted(glob.glob(os.path.join(HERE, 'data', 'snapshots', 'snapshot_*.json')),
                   key=lambda x: json.load(open(x, encoding='utf-8')).get('ts', ''))
    units, lots = {}, {}
    for f in files:
        s = json.load(open(f, encoding='utf-8'))
        for u in s.get('units', []):
            k = u.get('report') or u['unit_id']
            if k not in units or u['price'] < units[k]['price']:
                units[k] = u
        for l in s.get('lots', []):
            cur = lots.get(l['sku'])
            if not cur:
                lots[l['sku']] = l
            else:
                # оставляем версию с прочитанными паспортами и более свежими ценами
                if l.get('units_read', 0) > cur.get('units_read', 0):
                    lots[l['sku']] = {**l, 'cur': l.get('cur') or cur.get('cur')}
                elif not cur.get('cur') and l.get('cur'):
                    cur['cur'] = l['cur']
    out = {'ts': datetime.now(TZ).isoformat(timespec='seconds'), 'source': 'merge',
           'blocked': False, 'requests': 0, 'units': list(units.values()), 'lots': list(lots.values())}
    p = os.path.join(HERE, 'data', 'snapshots', f"snapshot_{datetime.now(TZ).strftime('%Y%m%d_%H%M')}_master.json")
    json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"мастер-снимок: {p}\nюнитов {len(out['units'])} · лотов {len(out['lots'])}")
    print("по моделям:", {m: sum(1 for u in out['units'] if u['model'] == m) for m in sorted({u['model'] for u in out['units']})})

if __name__ == '__main__':
    main()
