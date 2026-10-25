#!/usr/bin/env python3
"""Капельный режим: 2-3 паспорта за запуск, с очередью и бэкоффом при блоке."""
import json, os, sys, glob, time
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jdlib import Fetcher, parse_unit

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, 'config.json'), encoding='utf-8'))
TZ = timezone(timedelta(hours=7))
STATE = os.path.join(HERE, 'data', 'drip_state.json')
BATCH = int(os.environ.get('BATCH', '3'))
BACKOFF_MIN = 60

def now(): return datetime.now(TZ)

def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE, encoding='utf-8'))
    return {'cursor': 0, 'blocked_until': None, 'done': 0, 'fail': 0}

def save_state(s): json.dump(s, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

def main():
    st = load_state()
    if st.get('blocked_until'):
        until = datetime.fromisoformat(st['blocked_until'])
        if now() < until:
            print(f"пауза до {until:%H:%M} — пропуск"); return 0
    files = sorted(glob.glob(os.path.join(HERE, 'data', 'snapshots', 'snapshot_*.json')),
                   key=lambda x: json.load(open(x, encoding='utf-8')).get('ts', ''))
    if not files: print("нет снимков"); return 1
    src, lots = None, {}
    for f_ in reversed(files):
        s_ = json.load(open(f_, encoding='utf-8'))
        l_ = {str(x['sku']): x for x in s_.get('lots', []) if x.get('unit_ids')}
        if l_: src, lots = s_, l_; break
    if not lots: print("нет снимка с лотами"); return 1
    reg_p = os.path.join(HERE, 'data', 'registry.json')
    reg = json.load(open(reg_p, encoding='utf-8')) if os.path.exists(reg_p) else {}

    # приоритет: 2025 -> Ultra 2024 -> Pro 14/15 с 6600H/6800H
    prio = [str(s) for s in CFG.get('priority_skus', [])]
    order = [s for s in prio if s in lots] + [s for s in lots if s not in prio]
    queue = []
    for sku in order:
        l = lots[sku]
        for uid, price in zip(l['unit_ids'], l.get('prices') or []):
            if str(uid) not in reg:
                queue.append((sku, str(uid), float(price)))
    if not queue:
        print("очередь пуста: все юниты из лотов имеют паспорта"); return 0
    st['cursor'] = st.get('cursor', 0) % len(queue)
    batch = queue[st['cursor']:st['cursor']+BATCH] or queue[:BATCH]
    st['cursor'] = (st['cursor'] + len(batch)) % max(1, len(queue))

    f = Fetcher(os.path.join(HERE, 'cache'), ttl=0, delay=(4, 7))
    units = []
    for sku, uid, price in batch:
        h = f.get(f"https://item.m.jd.com/product/{sku}.html?inspectSkuId={uid}")
        if not h: break
        try: units.append(parse_unit(h, sku, uid, price))
        except Exception as e: print("  parse error", uid, e)
    print(f"очередь {len(queue)} · взято {len(batch)} · прочитано {len(units)} · блок {f.blocked}")
    for u in units: print(f"  {u['price']:>6.0f} {u['cpu']:<14} {u['cond_cn']} | {u['model']}")
    if units:
        snap = {'ts': now().isoformat(timespec='seconds'), 'source': 'drip', 'blocked': f.blocked,
                'requests': f.requests, 'units': units, 'lots': []}
        pth = os.path.join(HERE, 'data', 'snapshots', f"snapshot_{now():%Y%m%d_%H%M%S}_drip.json")
        json.dump(snap, open(pth, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        st['done'] = st.get('done', 0) + len(units)
    if f.blocked:
        st['blocked_until'] = (now() + timedelta(minutes=BACKOFF_MIN)).isoformat(timespec='seconds')
        st['fail'] = st.get('fail', 0) + 1
        print(f"блок — пауза {BACKOFF_MIN} мин")
    save_state(st)
    return 0

if __name__ == '__main__':
    sys.exit(main())
