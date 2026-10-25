#!/usr/bin/env python3
"""Единый самоподстраивающийся цикл: освежить лоты -> найти новые -> дочитать паспорта -> отчёт.

Сам решает, сколько запросов делать: при блокировке урезает бюджеты и уходит в паузу,
после успешных прогонов постепенно увеличивает. Ничего не требует от человека.
"""
import json, os, subprocess, sys, time, urllib.parse
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jdlib import Fetcher, parse_sku, parse_search, parse_unit, model_of

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_P, ST_P = os.path.join(HERE,'config.json'), os.path.join(HERE,'data','auto_state.json')
TZ = timezone(timedelta(hours=7))
MAXB = {'lots': 6, 'probe': 4, 'pass': 3}

def now(): return datetime.now(TZ)
def load(p, d):
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return d
def save(p, o): json.dump(o, open(p,'w',encoding='utf-8'), ensure_ascii=False, indent=1)

def snapshot(kind, units, lots):
    if not units and not lots: return
    ts = now()
    p = os.path.join(HERE,'data','snapshots', f"snapshot_{ts:%Y%m%d_%H%M%S}_{kind}.json")
    save(p, {'ts': ts.isoformat(timespec='seconds'), 'source': kind, 'blocked': False,
             'requests': 0, 'units': units, 'lots': lots})

def main():
    cfg = load(CFG_P, {}); st = load(ST_P, {})
    st.setdefault('budget', dict(MAXB)); st.setdefault('consec_blocks', 0)
    st.setdefault('probe_cursor', 0); st.setdefault('lot_cursor', 0)
    st['runs'] = st.get('runs', 0) + 1
    st['last_run'] = now().isoformat(timespec='seconds')
    if st.get('backoff_until') and now() < datetime.fromisoformat(st['backoff_until']):
        print(f"пауза до {datetime.fromisoformat(st['backoff_until']):%H:%M}"); save(ST_P, st); return 0

    f = Fetcher(os.path.join(HERE,'cache'), ttl=0, delay=(6, 10))
    known = [str(s) for s in cfg.get('known_skus', [])]
    units, lots = [], []

    # 1) освежаем лоты: состав и цены (дешёвый эндпоинт, держит много запросов)
    lc = st['lot_cursor'] % max(1, len(known))
    for i in range(st['budget']['lots']):
        if f.blocked: break
        sku = known[(lc + i) % len(known)]
        h = f.get(f"https://item.m.jd.com/product/{sku}.html")
        if h is None: break
        if not h: continue
        try: p = parse_sku(h)
        except Exception: continue
        if p:
            lots.append({'sku': str(p['sku']), 'title': p['title'], 'cur': p.get('cur'),
                         'prices': [float(u['price']) for u in p['units']],
                         'unit_ids': [str(u['inspectSkuId']) for u in p['units']], 'units_read': 0})
    st['lot_cursor'] = (lc + st['budget']['lots']) % max(1, len(known))

    # 2) разведка новых лотов семейства
    if not f.blocked:
        cands = [str(x) for x in cfg.get('probe_candidates', [])]
        c = st['probe_cursor'] % max(1, len(cands))
        for i in range(st['budget']['probe']):
            if f.blocked or not cands: break
            sku = cands[(c + i) % len(cands)]
            h = f.get(f"https://item.m.jd.com/product/{sku}.html")
            if h is None: break
            if not h: continue
            try: p = parse_sku(h)
            except Exception: continue
            if not p: continue
            if model_of(p.get('cur') or '') in cfg['targets']:
                lots.append({'sku': str(p['sku']), 'title': p['title'], 'cur': p.get('cur'),
                             'prices': [float(u['price']) for u in p['units']],
                             'unit_ids': [str(u['inspectSkuId']) for u in p['units']], 'units_read': 0})
                if str(p['sku']) not in known:
                    known.append(str(p['sku'])); cfg['known_skus'] = known; save(CFG_P, cfg)
                    print(f"  новый лот {p['sku']}: {p.get('cur','')[:40]}")
        st['probe_cursor'] = (c + st['budget']['probe']) % max(1, len(cands))

    # 3) паспорта: только у целевых лотов без паспорта
    if not f.blocked:
        reg = load(os.path.join(HERE,'data','registry.json'), {})
        target_lots = [l for l in lots if model_of(l.get('cur') or '') in cfg['targets']] or lots
        todo = [(l['sku'], u, pr) for l in target_lots
                for u, pr in zip(l['unit_ids'], l['prices']) if str(u) not in reg]
        prio = {str(s): i for i, s in enumerate(cfg.get('priority_skus', []))}
        todo.sort(key=lambda x: prio.get(x[0], 99))
        for sku, uid, price in todo[:st['budget']['pass']]:
            if f.blocked: break
            h = f.get(f"https://item.m.jd.com/product/{sku}.html?inspectSkuId={uid}")
            if h is None: break
            if not h: continue
            try:
                r = parse_unit(h, sku, uid, price)
                if r['model'] in cfg['targets']: units.append(r)
            except Exception: pass

    snapshot('auto', units, lots)

    # 4) адаптивные бюджеты и пауза
    if f.blocked:
        st['consec_blocks'] = st.get('consec_blocks', 0) + 1
        for k in st['budget']: st['budget'][k] = max(1, st['budget'][k] // 2)
        minutes = min(60, 10 * (2 ** (st['consec_blocks'] - 1)))
        st['backoff_until'] = (now() + timedelta(minutes=minutes)).isoformat(timespec='seconds')
        st['last_block'] = f.block_kind or 'unknown'
        print(f"блок ({f.block_kind}) → пауза {minutes} мин, бюджеты {st['budget']}")
    else:
        st['consec_blocks'] = 0; st['backoff_until'] = None
        for k in MAXB: st['budget'][k] = min(MAXB[k], st['budget'][k] + 1)
        print(f"чисто: лотов {len(lots)}, паспортов {len(units)}, бюджеты {st['budget']}")

    # 5) трекинг и отчёт
    for script in ('track.py', 'report.py'):
        try: subprocess.run([sys.executable, os.path.join(HERE, script),
                             *(['--out', os.path.join(HERE,'..','redmibook_pro_auto.xlsx')] if script=='report.py' else [])],
                            check=False, capture_output=True, timeout=120)
        except Exception as e: print("  ошибка", script, e)
    st['stats'] = {'lots_total': len(known), 'units_registry': len(load(os.path.join(HERE,'data','registry.json'), {}))}
    save(ST_P, st)
    return 0

if __name__ == '__main__':
    sys.exit(main())
