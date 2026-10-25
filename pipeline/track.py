#!/usr/bin/env python3
"""Трекинг жизненного цикла юнитов: появился / подорожал / продан."""
import json, os, sys, glob
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))

def main():
    files = sorted(glob.glob(os.path.join(HERE, 'data', 'snapshots', 'snapshot_*.json')),
                   key=lambda x: json.load(open(x, encoding='utf-8')).get('ts', ''))
    reg, events, lot_first = {}, [], {}
    for f in files:
        snap = json.load(open(f, encoding='utf-8'))
        ts = snap['ts']
        lots = {str(l['sku']): {str(u): float(p) for u, p in zip(l['unit_ids'], l.get('prices') or [])}
                for l in snap.get('lots', []) if l.get('unit_ids')}
        for sku in lots:
            lot_first.setdefault(sku, ts)
        if snap.get('source') == 'merge':
            # производный снимок: берём из него только дату первой фиксации лотов,
            # статусы юнитов не трогаем (иначе проданные «воскресают»)
            continue
        # синхронизация цен по лоту (даже если паспорта не перечитывались)
        for _sku, _m in lots.items():
            for _uid, _pr in _m.items():
                if _uid in reg and abs(reg[_uid]['price'] - _pr) > 0.5:
                    events.append({'type':'price','ts':ts,'unit_id':_uid,'model':reg[_uid]['model'],
                                   'cpu':reg[_uid]['cpu'],'price':_pr,'prev':reg[_uid]['price']})
                    reg[_uid]['price'] = _pr
        for u in snap.get('units', []):
            uid = str(u['unit_id'])
            if uid not in reg:
                reg[uid] = {'unit_id': uid, 'sku': str(u['sku']), 'model': u['model'], 'cpu': u['cpu'],
                            'ram': u.get('ram',''), 'ssd': u.get('ssd',''), 'name': u.get('name',''),
                            'cond': u.get('cond_cn'), 'price': u['price'], 'first_seen': ts,
                            'last_seen': ts, 'status': 'active', 'sold_at': None, 'url': u.get('url','')}
                events.append({'type':'new','ts':ts,'unit_id':uid,'model':u['model'],'cpu':u['cpu'],
                               'price':u['price'],'prev':None,'lot_first':lot_first.get(str(u['sku']), ts)})
            else:
                r = reg[uid]
                if abs(u['price'] - r['price']) > 0.5:
                    events.append({'type':'price','ts':ts,'unit_id':uid,'model':u['model'],'cpu':u['cpu'],
                                   'price':u['price'],'prev':r['price']})
                    r['price'] = u['price']
                r['last_seen'] = ts
                if r['status'] != 'active':
                    r['status'] = 'active'; r['sold_at'] = None
        for uid, r in reg.items():
            if r['status'] == 'active' and r['sku'] in lots and uid not in lots[r['sku']]:
                r['status'] = 'sold'; r['sold_at'] = ts
                events.append({'type':'sold','ts':ts,'unit_id':uid,'model':r['model'],'cpu':r['cpu'],
                               'price':r['price'],'prev':r['price']})
    json.dump(reg, open(os.path.join(HERE,'data','registry.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(events, open(os.path.join(HERE,'data','events.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=1)
    from collections import Counter
    print("юнитов в реестре:", len(reg), "|", dict(Counter(r['status'] for r in reg.values())))
    print("событий:", dict(Counter(e['type'] for e in events)))

if __name__ == '__main__':
    main()
