#!/usr/bin/env python3
"""Сбор б/у ноутбуков RedmiBook Pro с JD (拍拍严选) -> снимок JSON.

用法:
  python collect.py collect            # живой сбор (с уважением к лимитам)
  python collect.py import-cache DIR   # разбор ранее сохранённых страниц
"""
import argparse, json, os, sys, time, glob
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jdlib import Fetcher, parse_search, parse_sku, parse_unit

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, 'config.json'), encoding='utf-8'))
SNAP_DIR = os.path.join(HERE, 'data', 'snapshots')
os.makedirs(SNAP_DIR, exist_ok=True)
TZ = timezone(timedelta(hours=7))

def now(): return datetime.now(TZ).isoformat(timespec='seconds')

def is_used(r):
    t = (r.get('title') or '') + (r.get('shop') or '')
    return any(k in t for k in CFG['used_markers'])

def discover(f):
    found = {}
    for q in CFG['queries']:
        for page in range(1, CFG['pages'] + 1):
            url = f"https://so.m.jd.com/ware/search.action?keyword={__import__('urllib.parse',fromlist=['quote']).quote(q)}&page={page}"
            h = f.get(url)
            if not h: return found, 'blocked'
            for r in parse_search(h):
                if is_used(r): found[r['sku']] = r
    return found, 'ok'

def probe_family(f, seeds, span):
    out = {}
    for s in seeds:
        for d in range(-span, span + 1):
            if d == 0: continue
            sku = str(s + d)
            h = f.get(f"https://item.m.jd.com/product/{sku}.html")
            if not h: return out, 'blocked'
            try:
                p = parse_sku(h)
            except Exception:
                continue
            if p: out[sku] = p
    return out, 'ok'

def read_units(f, sku, limit):
    h = f.get(f"https://item.m.jd.com/product/{sku}.html")
    if not h: return None, []
    p = parse_sku(h)
    if not p: return None, []
    units = []
    for u in p['units'][:limit]:
        hh = f.get(f"https://item.m.jd.com/product/{sku}.html?inspectSkuId={u['inspectSkuId']}")
        if not hh: break
        try:
            units.append(parse_unit(hh, sku, u['inspectSkuId'], u['price']))
        except Exception:
            continue
    return p, units

def cmd_collect(args):
    f = Fetcher(os.path.join(HERE, 'cache'), ttl=args.ttl, delay=(CFG.get('delay_min',2.5), CFG.get('delay_max',4.0)), proxy=None if args.no_proxy else CFG.get('proxy'))
    print(f"[{now()}] discovery...")
    found, st = discover(f)
    print(f"  найдено б/у лотов: {len(found)} ({st})")
    if st == 'blocked':
        print("  поиск закрыт антиботом — работаю по известным SKU и соседям (карточки могут быть открыты)")
        f.blocked = False
        for sku in CFG.get('known_skus', []):
            found.setdefault(sku, {'sku': sku, 'title': '', 'shop': '', 'price': None})
    lots, units = [], []
    for sku, meta in found.items():
        if f.requests >= args.max_requests: print("  лимит запросов исчерпан"); break
        p, us = read_units(f, sku, CFG['units_per_lot'])
        if p:
            lots.append({'sku': sku, 'title': p['title'], 'cur': p.get('cur'),
                         'prices': [float(u['price']) for u in p['units']],
                         'unit_ids': [str(u['inspectSkuId']) for u in p['units']],
                         'units_read': len(us)})
            units += us
            print(f"  {sku}: юнитов прочитано {len(us)}/{len(p['units'])}")
        if f.blocked: print("  антибот-блок, останавливаюсь"); break
    if not f.blocked and args.family:
        print(f"[{now()}] обход соседних SKU...")
        fam, st2 = probe_family(f, CFG['family_seeds'], CFG['family_span'])
        for sku, p in fam.items():
            if sku in found: continue
            if any(l['sku'] == sku for l in lots): continue
            lots.append({'sku': sku, 'title': p['title'], 'cur': p.get('cur'),
                         'prices': [float(u['price']) for u in p['units']],
                         'unit_ids': [str(u['inspectSkuId']) for u in p['units']],
                         'units_read': 0})
        print(f"  добавлено лотов семейства: {len(fam)}")
    if not units and not lots:
        json.dump({'ts': now(), 'blocked': f.blocked, 'requests': f.requests},
                  open(os.path.join(HERE, 'data', 'last_error.json'), 'w'), ensure_ascii=False, indent=1)
        print("данных нет (блок/сеть) — снимок не записан, прошлые данные сохранены")
        return 3
    snap = {'ts': now(), 'source': 'live', 'blocked': f.blocked, 'requests': f.requests,
            'units': dedup(units), 'lots': lots}
    path = os.path.join(SNAP_DIR, f"snapshot_{datetime.now(TZ).strftime('%Y%m%d_%H%M')}.json")
    json.dump(snap, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"снимок: {path} · юнитов {len(snap['units'])} · лотов {len(lots)} · заблокирован: {f.blocked}")
    return 0 if not f.blocked else 2

def dedup(units):
    seen = {}
    for u in units:
        k = u.get('report') or u['unit_id']
        if k not in seen or u['price'] < seen[k]['price']:
            seen[k] = u
    return list(seen.values())

def cmd_import(args):
    lots, units = {}, []
    for pth in sorted(glob.glob(os.path.join(args.dir, 'p_*.html'))):
        sku = os.path.basename(pth)[2:-5]
        try:
            p = parse_sku(open(pth, encoding='utf-8', errors='ignore').read())
        except Exception:
            continue
        if not p: continue
        lots[sku] = {'sku': sku, 'title': p['title'], 'cur': p.get('cur'),
                     'prices': [float(u['price']) for u in p['units']],
                     'unit_ids': [str(u['inspectSkuId']) for u in p['units']], 'units_read': 0}
    for pth in sorted(glob.glob(os.path.join(args.dir, 'u_*.html'))):
        uid = os.path.basename(pth)[2:-5]
        try:
            html = open(pth, encoding='utf-8', errors='ignore').read()
        except Exception:
            continue
        m = __import__('re').search(r'inspectSkuId=(\d+)', html)
        sku = m.group(1) if m else ''
        html_sku = __import__('re').search(r'/product/(\d+)\.html', html)
        if html_sku: sku = html_sku.group(1)
        for lot in lots.values():
            pass
    # связываем юниты с лотами по списку selectableList
    price_of = {}
    for pth in sorted(glob.glob(os.path.join(args.dir, 'p_*.html'))):
        sku = os.path.basename(pth)[2:-5]
        try:
            p = parse_sku(open(pth, encoding='utf-8', errors='ignore').read())
        except Exception:
            continue
        if not p: continue
        for u in p['units']: price_of[str(u['inspectSkuId'])] = (sku, float(u['price']))
    for pth in sorted(glob.glob(os.path.join(args.dir, 'u_*.html'))):
        uid = os.path.basename(pth)[2:-5]
        if uid not in price_of: continue
        sku, price = price_of[uid]
        try:
            units.append(parse_unit(open(pth, encoding='utf-8', errors='ignore').read(), sku, uid, price))
        except Exception:
            continue
    # лоты, у которых известны только цены (family.json из разведки)
    fp = os.path.join(args.dir, 'family.json')
    if os.path.exists(fp):
        for r in json.load(open(fp, encoding='utf-8')):
            sku = str(r['sku'])
            if sku in lots: continue
            lots[sku] = {'sku': sku, 'title': r.get('name',''),
                         'prices': [float(u['price']) for u in r.get('units', [])],
                         'unit_ids': [str(u['inspectSkuId']) for u in r.get('units', [])],
                         'units_read': 0, 'cur': r.get('cur')}
    for sku, lot in lots.items():
        lot['units_read'] = sum(1 for u in units if u['sku'] == sku)
    snap = {'ts': now(), 'source': 'cache', 'blocked': False, 'requests': 0,
            'units': dedup(units), 'lots': list(lots.values())}
    path = os.path.join(SNAP_DIR, f"snapshot_{datetime.now(TZ).strftime('%Y%m%d_%H%M')}_cache.json")
    json.dump(snap, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"снимок из кэша: {path} · юнитов {len(snap['units'])} · лотов {len(snap['lots'])}")
    return 0

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('collect'); c.add_argument('--max-requests', type=int, default=CFG['max_requests'])
    c.add_argument('--ttl', type=int, default=CFG['cache_ttl']); c.add_argument('--no-proxy', action='store_true')
    c.add_argument('--family', action='store_true', default=True)
    i = sub.add_parser('import-cache'); i.add_argument('dir')
    a = ap.parse_args()
    return cmd_collect(a) if a.cmd == 'collect' else cmd_import(a)

if __name__ == '__main__':
    sys.exit(main())
