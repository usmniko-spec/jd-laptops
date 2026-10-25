#!/usr/bin/env python3
"""Поиск всех лотов семейства RedmiBook Pro: поиск + обход соседних SKU.

Каждый найденный лот автоматически попадает в known_skus и в снимок,
поэтому пропусков «позиция есть на сайте, но не в статистике» быть не должно.
"""
import json, os, sys, time, urllib.parse
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jdlib import Fetcher, parse_sku, parse_search, model_of

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_P = os.path.join(HERE, 'config.json')
CFG = json.load(open(CFG_P, encoding='utf-8'))
TZ = timezone(timedelta(hours=7))
BUDGET = int(os.environ.get('DISCOVER_BUDGET', '8'))

def now(): return datetime.now(TZ)

def save_cfg(c): json.dump(c, open(CFG_P, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

def expand_candidates(c, seeds):
    """Соседние SKU вокруг всех известных лотов: семейство нумеруется подряд."""
    have = {str(s) for s in c['known_skus']}
    cands = [str(x) for x in c.get('probe_candidates', [])]
    seen = set(cands) | have
    for s in seeds:
        for d in range(-25, 26):
            if d == 0: continue
            i = str(int(s) + d)
            if i not in seen:
                seen.add(i); cands.append(i)
    c['probe_candidates'] = cands
    return c

def main():
    st_p = os.path.join(HERE, 'data', 'discover_state.json')
    st = json.load(open(st_p, encoding='utf-8')) if os.path.exists(st_p) else {'cursor': 0}
    if st.get('blocked_until') and now() < datetime.fromisoformat(st['blocked_until']):
        print(f"пауза до {datetime.fromisoformat(st['blocked_until']):%H:%M} — пропуск"); return 0

    f = Fetcher(os.path.join(HERE, 'cache'), ttl=0, delay=(5, 8))
    found = []          # лоты, найденные поиском/SKU
    # 1) поиск по ключевым словам (если доступен)
    for q in CFG['queries'][:3]:
        if f.blocked or f.requests >= BUDGET: break
        url = "https://so.m.jd.com/ware/search.action?keyword=" + urllib.parse.quote(q)
        h = f.get(url)
        if not h: break
        for r in parse_search(h):
            if any(k in (r['title'] + r['shop']) for k in CFG['used_markers']):
                found.append({'sku': str(r['sku']), 'title': r['title'], 'cur': '', 'prices': [], 'unit_ids': [], 'units_read': 0})
    # поиск может быть заблокирован отдельно от карточек — это не повод останавливаться
    if f.blocked:
        print("  поиск закрыт, иду по соседним SKU")
        f.blocked = False
    # 2) обход соседних SKU
    c = expand_candidates(CFG, CFG['known_skus'])
    save_cfg(c)
    cands = c['probe_candidates']
    st['cursor'] = st.get('cursor', 0) % max(1, len(cands))
    probed = 0
    while cands and probed < BUDGET and not f.blocked:
        sku = cands[st['cursor'] % len(cands)]
        st['cursor'] += 1; probed += 1
        h = f.get(f"https://item.m.jd.com/product/{sku}.html")
        if h is None: break      # блок
        if not h: continue       # 404 — такого SKU нет
        try: p = parse_sku(h)
        except Exception: continue
        if not p: continue
        mdl = model_of(p.get('cur') or '')
        title = p.get('title') or ''
        if mdl in CFG['targets']:   # только реальные Pro 14/15, иначе очередь забивается мусором
            found.append({'sku': str(p['sku']), 'title': title, 'cur': p.get('cur'),
                          'prices': [float(u['price']) for u in p['units']],
                          'unit_ids': [str(u['inspectSkuId']) for u in p['units']], 'units_read': 0})
            print(f"  найден лот {p['sku']}: {mdl} · {len(p['units'])} юнитов", flush=True)
    # 3) автодобавление в known_skus
    known = {str(s) for s in c['known_skus']}
    added = [l['sku'] for l in found if l['sku'] not in known]
    c['known_skus'] = list(dict.fromkeys([str(s) for s in c['known_skus']] + added))
    save_cfg(c)
    st['found_total'] = st.get('found_total', 0) + len(added)
    if f.blocked:
        st['blocked_until'] = (now() + timedelta(minutes=60)).isoformat(timespec='seconds')
    json.dump(st, open(st_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"запросов {f.requests} · найдено лотов {len(found)} · новых {len(added)} · блок {f.blocked}")
    if found:
        snap = {'ts': now().isoformat(timespec='seconds'), 'source': 'discover', 'blocked': f.blocked,
                'requests': f.requests, 'units': [], 'lots': found}
        p = os.path.join(HERE, 'data', 'snapshots', f"snapshot_{now():%Y%m%d_%H%M%S}_discover.json")
        json.dump(snap, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print("снимок:", p)
    return 0

if __name__ == '__main__':
    sys.exit(main())
