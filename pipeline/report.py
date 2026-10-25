#!/usr/bin/env python3
"""Построение Excel-анализа по снимку JD (б/у RedmiBook Pro)."""
import argparse, glob, json, os, statistics as st, sys
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, Reference
from openpyxl.utils import get_column_letter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jdlib import COND, BATT, SCR, ADP, tr, model_of

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, 'config.json'), encoding='utf-8'))
RATE = CFG.get('rate_rub', 13)
TARGETS = CFG['targets']

HDR = PatternFill('solid', fgColor='C00000'); HF = Font(color='FFFFFF', bold=True, size=10)
BLU = PatternFill('solid', fgColor='1F4E79'); SUB = PatternFill('solid', fgColor='F2F2F2')
YEL = PatternFill('solid', fgColor='FFF2CC'); GRN = PatternFill('solid', fgColor='E2EFDA')
ORG = PatternFill('solid', fgColor='FCE4D6')
TH = Side(style='thin', color='BFBFBF'); BOX = Border(left=TH, right=TH, top=TH, bottom=TH)

def head(ws, cols, row=4, fill=BLU):
    for i, c in enumerate(cols, 1):
        cell = ws.cell(row, i, c); cell.fill = fill; cell.font = HF; cell.border = BOX
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

def widths(ws, ws_w):
    for i, w in enumerate(ws_w, 1): ws.column_dimensions[get_column_letter(i)].width = w

def title(ws, t, sub):
    ws['A1'] = t; ws['A1'].font = Font(bold=True, size=14)
    ws['A2'] = sub; ws['A2'].font = Font(italic=True, size=9, color='595959')

def unit_row(u):
    return [u['model'], u['cpu'], u['platform'], u['gpu'], f"{u['ram']}/{u['ssd']}",
            tr(COND, u['cond_cn']), tr(BATT, u['batt_cn']), tr(SCR, u['scratch_cn']),
            tr(ADP, u['adapter_cn']), u['price'], round(u['price'] * RATE), u['report'], u['url']]

UNIT_COLS = ['Модель','Процессор','Платформа','Графика','Память/SSD','Состояние','Износ батареи',
             'Экран: царапины','Адаптер','Цена, ¥','Цена, ₽','№ отчёта','Ссылка']

def units_sheet(wb, name, units, note=''):
    ws = wb.create_sheet(name)
    title(ws, f"{name} — б/у на JD, {len(units)} юнит(ов)", f"Курс 1 ¥ = {RATE} ₽ · в скобках исходные обозначения JD" if False else f"Курс 1 ¥ = {RATE} ₽ · цена за единицу без доставки")
    head(ws, UNIT_COLS)
    for j, u in enumerate(sorted(units, key=lambda x: x['price'])):
        for i, v in enumerate(unit_row(u), 1):
            c = ws.cell(5 + j, i, v); c.border = BOX; c.font = Font(size=10)
            if i in (10, 11): c.number_format = '#,##0'
            if i == 13: c.font = Font(size=8, color='1F4E79', underline='single')
        if u['platform'] == 'AMD':
            for i in range(1, 14): ws.cell(5 + j, i).fill = YEL
        elif u['cpu'].startswith('Ultra'):
            for i in range(1, 14): ws.cell(5 + j, i).fill = GRN
    ws.freeze_panes = 'A5'; ws.auto_filter.ref = f'A4:M{4+len(units)}'
    widths(ws, [20,20,11,18,12,14,13,20,12,10,10,19,44])
    if note: ws.cell(6 + len(units), 1, note).font = Font(italic=True, size=9, color='7F6000')



def focus(wb, units, ev, reg, cpus, lots=None):
    """Фокусный лист: только интересующие CPU, Pro 14/15."""
    f = wb.create_sheet('Фокус 6600H-6800H-Ultra')
    title(f, 'Фокус: Ryzen 5 6600H, Ryzen 7 6800H, Ultra 2024 и 2025',
          f"RedmiBook Pro 14/15, б/у JD · курс 1 ¥ = {RATE} ₽ · {len([u for u in units if u['cpu'] in cpus])} активных юнитов")
    r = 4
    f.cell(r,1,'Статистика по конфигурациям').font = Font(bold=True, size=11); f.cell(r,1).fill = SUB; r += 1
    head(f, ['Модель','Процессор','Память/SSD','Юнитов','Мин, ¥','Медиана, ¥','Макс, ¥','Медиана, ₽'], row=r); r += 1
    g = {}
    for u in units:
        if u['cpu'] in cpus: g.setdefault((u['model'], u['cpu'], f"{u['ram']}/{u['ssd']}"), []).append(u['price'])
    for k in sorted(g, key=lambda x: (x[0], list(cpus).index(x[1]) if x[1] in cpus else 9)):
        ps = sorted(g[k]); med = st.median(ps)
        vals = [k[0], k[1], k[2], len(ps), min(ps), med, max(ps), round(med*RATE)]
        for i,v in enumerate(vals,1):
            c = f.cell(r,i,v); c.border = BOX; c.font = Font(size=10)
            if i >= 5: c.number_format = '#,##0'
        r += 1
    r += 1
    f.cell(r,1,'Насколько дороже каждое следующее поколение').font = Font(bold=True, size=11); f.cell(r,1).fill = SUB; r += 1
    head(f, ['Переход','Было, ¥','Стало, ¥','Δ, ¥','Δ, %','Δ, ₽'], row=r); r += 1
    def med_of(cpu):
        ps = [u['price'] for u in units if u['cpu'] == cpu]
        return st.median(ps) if ps else None
    pairs = [('Ultra 5 125H','Ultra 5 225H'), ('Ultra 7 155H','Ultra 7 255H'),
             ('Ultra 5 125H','Ultra 7 155H'), ('Ultra 5 225H','Ultra 7 255H')]
    for a,b in pairs:
        ma, mb = med_of(a), med_of(b)
        if not ma or not mb: continue
        vals = [f'{a} → {b}', ma, mb, round(mb-ma), f'+{(mb/ma-1)*100:.0f}%', round((mb-ma)*RATE)]
        for i,v in enumerate(vals,1):
            c = f.cell(r,i,v); c.border = BOX; c.font = Font(size=10)
            if i in (2,3,4,6): c.number_format = '#,##0'
        r += 1
    r += 1
    f.cell(r,1,'Изменения по этим позициям').font = Font(bold=True, size=11); f.cell(r,1).fill = SUB; r += 1
    evf = [e for e in ev if e['cpu'] in cpus and e['model'] in TARGETS]
    sold = [e for e in evf if e['type']=='sold']
    chg  = [e for e in evf if e['type']=='price']
    new  = [e for e in evf if e['type']=='new' and e['ts'] > e.get('lot_first','')]
    head(f, ['Тип','Дата','Модель','Процессор','Цена, ¥','Цена, ₽'], row=r); r += 1
    rows = [('продан', e) for e in sold] + [('новый', e) for e in new] + [('цена', e) for e in chg]
    if not rows:
        f.cell(r,1,'Изменений пока нет — трекинг начат сегодня, история копится.').font = Font(italic=True, size=9, color='595959'); r += 1
    for kind, e in sorted(rows, key=lambda x: x[1]['ts'], reverse=True)[:50]:
        price = e['price']
        txt = f"{e['prev']} → {e['price']}" if kind == 'цена' else price
        vals = [kind, e['ts'][:16].replace('T',' '), e['model'], e['cpu'], txt, round(price*RATE)]
        for i,v in enumerate(vals,1):
            c = f.cell(r,i,v); c.border = BOX; c.font = Font(size=10)
            if i in (5,6): c.number_format = '#,##0'
            if kind == 'продан': c.fill = ORG
            if kind == 'новый': c.fill = GRN
        r += 1
    if lots:
        pro_lots = [l for l in lots if l.get('prices') and model_of(l.get('cur') or l.get('title') or '') in TARGETS]
        if pro_lots:
            r += 1
            f.cell(r,1,'Наличие по лотам (цены лота, без паспортов)').font = Font(bold=True, size=11); f.cell(r,1).fill = SUB; r += 1
            head(f, ['Лот','Модель','Юнитов','Мин, ¥','Медиана, ¥','Макс, ¥','Медиана, ₽'], row=r); r += 1
            for l in sorted(pro_lots, key=lambda x: str(x['sku'])):
                ps = sorted(float(x) for x in l['prices'])
                vals = [l['sku'], model_of(l.get('cur') or ''), len(ps), min(ps), st.median(ps), max(ps), round(st.median(ps)*RATE)]
                for i,v in enumerate(vals,1):
                    c = f.cell(r,i,v); c.border = BOX; c.font = Font(size=10)
                    if i >= 4: c.number_format = '#,##0'
                r += 1
            f.cell(r,1,'Лоты обновляются даже когда паспорта недоступны: это фактическое наличие и цены на момент снимка.').font = Font(italic=True, size=9, color='7F6000')
    widths(f, [20,20,14,9,11,13,11,13])

def movement(wb, name, subtitle, reg, ev, cpus):
    """Лист движения позиций. cpus=None -> без фильтра по процессору."""
    mv = wb.create_sheet(name)
    title(mv, 'Движение позиций: в продаже, появились, проданы, изменились в цене',
          f"{subtitle} · курс 1 ¥ = {RATE} ₽")
    def flt(x): return x['model'] in TARGETS and (cpus is None or x['cpu'] in cpus)
    watched = [r for r in reg.values() if flt(r)]
    evw = [e for e in ev if flt(e)]
    r = 4
    mv.cell(r,1,'Сейчас в продаже').font = Font(bold=True, size=11); mv.cell(r,1).fill = SUB; r += 1
    head(mv, ['Модель','Процессор','Память/SSD','Состояние','Цена, ¥','Цена, ₽','Дней в продаже','Ссылка'], row=r); r += 1
    act = sorted([x for x in watched if x['status']=='active'], key=lambda x:(x['cpu'],x['price']))
    today = datetime.now().astimezone()
    for x in act:
        try: days = (today - datetime.fromisoformat(x['first_seen'])).days
        except Exception: days = 0
        vals = [x['model'], x['cpu'], f"{x['ram']}/{x['ssd']}", tr(COND, x['cond']),
                x['price'], round(x['price']*RATE), days, x.get('url','')]
        for i,v in enumerate(vals,1):
            c = mv.cell(r,i,v); c.border = BOX; c.font = Font(size=10)
            if i in (5,6): c.number_format = '#,##0'
            if i == 8: c.font = Font(size=8, color='1F4E79', underline='single')
        r += 1
    if not act:
        mv.cell(r,1,'нет активных позиций по фильтру').font = Font(italic=True, size=9); r += 1
    r += 1
    new_all = [e for e in ev if e['type']=='new']
    _dates = sorted({e['ts'][:10] for e in new_all})
    base_date = _dates[0] if _dates else ''
    mv.cell(r,1,'Добавились').font = Font(bold=True, size=11); mv.cell(r,1).fill = SUB; r += 1
    new = [e for e in evw if e['type']=='new' and e['ts'] > e.get('lot_first','')]
    if not new:
        mv.cell(r,1,'Новых позиций нет с момента первой фиксации лотов.').font = Font(italic=True, size=9, color='595959'); r += 1
    else:
        head(mv, ['Дата','Модель','Процессор','Цена, ¥','Цена, ₽'], row=r); r += 1
        for e in sorted(new, key=lambda x:x['ts'], reverse=True)[:60]:
            for i,v in enumerate([e['ts'][:16].replace('T',' '), e['model'], e['cpu'], e['price'], round(e['price']*RATE)],1):
                c = mv.cell(r,i,v); c.border = BOX; c.font = Font(size=10); c.fill = GRN
                if i in (4,5): c.number_format = '#,##0'
            r += 1
    r += 1
    sold = [e for e in evw if e['type']=='sold']
    mv.cell(r,1,'Проданы / сняты с продажи').font = Font(bold=True, size=11); mv.cell(r,1).fill = SUB; r += 1
    if not sold:
        mv.cell(r,1,'Пока нет: нужен повторный прогон по тому же лоту.').font = Font(italic=True, size=9, color='595959'); r += 1
    else:
        head(mv, ['Дата','Модель','Процессор','Последняя цена, ¥','Последняя цена, ₽'], row=r); r += 1
        for e in sorted(sold, key=lambda x:x['ts'], reverse=True)[:60]:
            for i,v in enumerate([e['ts'][:16].replace('T',' '), e['model'], e['cpu'], e['price'], round(e['price']*RATE)],1):
                c = mv.cell(r,i,v); c.border = BOX; c.font = Font(size=10); c.fill = ORG
                if i in (4,5): c.number_format = '#,##0'
            r += 1
    r += 1
    chg = [e for e in evw if e['type']=='price']
    mv.cell(r,1,'Изменились в цене').font = Font(bold=True, size=11); mv.cell(r,1).fill = SUB; r += 1
    if not chg:
        mv.cell(r,1,'Пока нет изменений цены по этим позициям.').font = Font(italic=True, size=9, color='595959'); r += 1
    else:
        head(mv, ['Дата','Модель','Процессор','Было, ¥','Стало, ¥','Δ, ¥','Δ, ₽'], row=r); r += 1
        for e in sorted(chg, key=lambda x:x['ts'], reverse=True)[:60]:
            for i,v in enumerate([e['ts'][:16].replace('T',' '), e['model'], e['cpu'], e['prev'], e['price'], round(e['price']-e['prev']), round((e['price']-e['prev'])*RATE)],1):
                c = mv.cell(r,i,v); c.border = BOX; c.font = Font(size=10)
                if i in (4,5,6,7): c.number_format = '#,##0'
            r += 1
    widths(mv, [20,22,14,14,12,12,14,44])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--snapshot'); ap.add_argument('--out')
    a = ap.parse_args()
    snaps = sorted(glob.glob(os.path.join(HERE, 'data', 'snapshots', 'snapshot_*.json')),
                   key=lambda x: json.load(open(x, encoding='utf-8')).get('ts',''))
    path = a.snapshot or (snaps[-1] if snaps else None)
    if not path: sys.exit('нет снимков: сначала запустите collect.py')
    # отчёт всегда строится по склейке всех снимков: частичные прогоны не обнуляют данные
    units_all, lots_all = {}, {}
    for _f in snaps if not a.snapshot else [a.snapshot]:
        _s = json.load(open(_f, encoding='utf-8'))
        for _u in _s.get('units', []):
            _k = _u.get('report') or _u['unit_id']
            if _k not in units_all or _u['price'] < units_all[_k]['price']:
                units_all[_k] = _u
        for _l in _s.get('lots', []):
            _key = str(_l['sku'])
            _old = lots_all.get(_key)
            lots_all[_key] = {**_l, 'cur': _l.get('cur') or (_old or {}).get('cur')}
    snap = {'ts': json.load(open(path, encoding='utf-8'))['ts'],
            'units': list(units_all.values()), 'lots': list(lots_all.values())}
    # в статистику идут только активные юниты; проданные видны лишь в листах движения
    reg_all = {}
    _reg = os.path.join(HERE, 'data', 'registry.json')
    if os.path.exists(_reg):
        _r = json.load(open(_reg, encoding='utf-8')); reg_all = _r
        _keep = []
        for u in snap['units']:
            _e = _r.get(str(u['unit_id']))
            if _e and _e.get('status', 'active') != 'active':
                continue
            if _e:
                u['price'] = _e['price']   # цена из реестра (свежая, из лота)
            _keep.append(u)
        snap['units'] = _keep
    prev = None
    if len(snaps) >= 2 and snaps[-1] == path:
        prev = json.load(open(snaps[-2], encoding='utf-8'))
    units = [u for u in snap['units'] if u['model'] in TARGETS]
    lots = snap.get('lots', [])
    out = a.out or os.path.join(HERE, '..', 'redmibook_pro_auto.xlsx')
    ts = snap['ts'].replace(':','-').replace('+','_')

    wb = Workbook(); wb.remove(wb.active)

    # --- Сводка ---
    s = wb.create_sheet('Сводка')
    title(s, 'RedmiBook Pro 14/15 — б/у на JD: сводка по процессорам', f"Снимок {snap['ts']} · курс 1 ¥ = {RATE} ₽ · юнитов {len(units)}")
    head(s, ['Модель','Процессор','Платформа','Юнитов','Мин, ¥','Медиана, ¥','Макс, ¥','Медиана, ₽','Δ к базе модели, ¥'])
    groups = {}
    for u in units: groups.setdefault((u['model'], u['cpu']), []).append(u['price'])
    base = {}
    for (m, c), ps in groups.items(): base.setdefault(m, []).append((c, len(ps), st.median(ps)))
    # база модели — самый массовый CPU
    base = {m: sorted(v, key=lambda x: -x[1])[0][2] for m, v in base.items()}
    r = 5
    for (m, c) in sorted(groups, key=lambda k: (k[0], st.median(groups[k]))):
        ps = sorted(groups[(m, c)]); med = st.median(ps)
        fam = 'AMD' if c.startswith('Ryzen') else 'Intel'
        for i, v in enumerate([m, c, fam, len(ps), min(ps), med, max(ps), round(med*RATE), round(med-base[m])], 1):
            cell = s.cell(r, i, v); cell.border = BOX; cell.font = Font(size=10)
            if i >= 5: cell.number_format = '#,##0'
            if fam == 'AMD': cell.fill = YEL
            if c.startswith('Ultra'): cell.fill = GRN
        r += 1
    if r > 5:
        ch = BarChart(); ch.type='col'; ch.title='Медиана, ¥'; ch.height=8; ch.width=16
        ch.add_data(Reference(s, min_col=6, min_row=4, max_row=r-1), titles_from_data=True)
        ch.set_categories(Reference(s, min_col=2, min_row=5, max_row=r-1)); ch.legend=None
        s.add_chart(ch, 'K5')
    s.cell(r+1, 1, 'Δ — к самой массовой версии этой же модели. Ultra выделены зелёным, AMD — жёлтым.').font = Font(italic=True, size=9, color='595959')
    widths(s, [20,22,11,9,10,14,10,14,20])

    # --- Ценовая лестница ---
    l = wb.create_sheet('Ценовая лестница')
    title(l, 'Что двигает цену: состояние, поколение, класс CPU', f"Курс 1 ¥ = {RATE} ₽ · дельты по медианам")
    r = 4
    def block(t):
        nonlocal r
        c = l.cell(r, 1, t); c.font = Font(bold=True, size=11); c.fill = SUB; r += 1
        head(l, ['Ступень','Юнитов','Медиана, ¥','Медиана, ₽','Δ, ¥','Δ, %'], row=r); r += 1
    def line(v, bold=False):
        nonlocal r
        for i, x in enumerate(v, 1):
            c = l.cell(r, i, x); c.border = BOX; c.font = Font(size=10, bold=bold)
            if i in (3,4,5): c.number_format = '#,##0'
        r += 1
    for model in sorted({u['model'] for u in units}):
        mus = [u for u in units if u['model'] == model and u['platform'] == 'AMD']
        if len(mus) >= 3:
            block(f'{model}: шаг по состоянию (AMD)')
            prevmed = None
            for cond in ['7成新','8成新','9成新','95新','99新']:
                ps = [u['price'] for u in mus if u['cond_cn'] == cond]
                if not ps: continue
                med = st.median(ps); d = med - prevmed if prevmed else None
                line([tr(COND, cond), len(ps), med, round(med*RATE), round(d) if d else '—',
                      f"+{d/prevmed*100:.0f}%" if d else '—'])
                prevmed = med
            r += 1
    for model in sorted({u['model'] for u in units}):
        cpus = sorted({(u['cpu'], u['platform']) for u in units if u['model'] == model})
        amd = [c for c, p in cpus if p == 'AMD']
        if len(amd) >= 2:
            block(f'{model}: Ryzen 5 → 7')
            for pair in [('Ryzen 5','Ryzen 7')]:
                a_ = [u['price'] for u in units if u['model']==model and u['cpu'].startswith(pair[0])]
                b_ = [u['price'] for u in units if u['model']==model and u['cpu'].startswith(pair[1])]
                if a_ and b_:
                    ma, mb = st.median(a_), st.median(b_)
                    line([f"{pair[0]} → {pair[1]}", len(b_), mb, round(mb*RATE), round(mb-ma), f"+{(mb/ma-1)*100:.0f}%"])
            r += 1
    l.cell(r, 1, 'Состояние влияет сильнее процессора. Пустые блоки — мало данных в снимке.').font = Font(italic=True, size=9, color='7F6000')
    widths(l, [42,9,13,13,12,9])

    # --- юниты ---
    pro14 = [u for u in units if u['model'] == 'RedmiBook Pro 14']
    pro15 = [u for u in units if u['model'] == 'RedmiBook Pro 15']
    ultra = [u for u in units if u['cpu'].startswith('Ultra')]
    other = [u for u in snap['units'] if u['model'] not in TARGETS]
    if pro14: units_sheet(wb, 'Pro 14 юниты', pro14, 'Жёлтый — AMD, зелёный — Ultra, белый — Intel.')
    if pro15: units_sheet(wb, 'Pro 15 юниты', pro15, 'Жёлтый — AMD, зелёный — Ultra, белый — Intel.')
    if other: units_sheet(wb, 'Прочие юниты', other, 'Не целевые модели — для контекста рынка.')

    # --- Ultra ---
    u = wb.create_sheet('Ultra (все версии)')
    title(u, 'RedmiBook Pro 2024 на Core Ultra: б/у и справочные цены новых', f"Курс 1 ¥ = {RATE} ₽ · снимок {snap['ts']}")
    head(u, ['Версия','Память/SSD','Юнитов','Мин, ¥','Медиана, ¥','Макс, ¥','Медиана, ₽'])
    rr = 5
    _vers = sorted({x['cpu'] for x in units if x['cpu'].startswith('Ultra')}) or ['Ultra 5 125H']
    for ver in _vers:
        rows = [(f"{x['ram']}/{x['ssd']}", x['price']) for x in units if ver in x['cpu']]
        if not rows:
            for i, v in enumerate([ver,'—','—','—','—','—','—'], 1):
                c = u.cell(rr, i, v); c.border = BOX; c.font = Font(size=10); c.fill = GRN
            rr += 1; continue
        for k in sorted({r[0] for r in rows}):
            ps = sorted(p for kk, p in rows if kk == k)
            for i, v in enumerate([ver, k, len(ps), min(ps), st.median(ps), max(ps), round(st.median(ps)*RATE)], 1):
                c = u.cell(rr, i, v); c.border = BOX; c.font = Font(size=10); c.fill = GRN
                if i >= 3: c.number_format = '#,##0'
            rr += 1
        ps = sorted(p for _, p in rows)
        for i, v in enumerate([ver, 'все', len(ps), min(ps), st.median(ps), max(ps), round(st.median(ps)*RATE)], 1):
            c = u.cell(rr, i, v); c.border = BOX; c.font = Font(size=10, bold=True); c.fill = GRN
            if i >= 3: c.number_format = '#,##0'
        rr += 1
    rr += 1
    u.cell(rr, 1, 'Справочно: новые (не JD-карточки, пресса/агрегаторы)').font = Font(bold=True, size=11); u.cell(rr,1).fill = SUB
    rr += 1
    head(u, ['Версия','Статус','Цена, ¥','Цена, ₽','Комментарий'], row=rr); rr += 1
    ref = [('Ultra 5 125H','Новый, старт',4999,'Старт линейки Pro 14 2024'),
           ('Ultra 5 125H','Новый, акция',3219,'Минимум по ZOL'),
           ('Ultra 5 125H','Новый, акция',3759,'Типичная акционная цена'),
           ('Ultra 7 155H','Новый, верх (32/1T)',6499,'Верхняя граница линейки')]
    for ver, stt, pr, com in ref:
        for i, v in enumerate([ver, stt, pr, round(pr*RATE), com], 1):
            c = u.cell(rr, i, v); c.border = BOX; c.font = Font(size=10)
            if i in (3,4): c.number_format = '#,##0'
        rr += 1
    u5 = [x['price'] for x in units if x['cpu']=='Ultra 5 125H']
    u7 = [x['price'] for x in units if x['cpu']=='Ultra 7 155H']
    n = 0
    if u5:
        m5 = st.median(u5)
        u.cell(rr+1, 1, f'Сравнение: б/у Ultra 5 125H — медиана {m5:.0f} ¥ ({m5*RATE:.0f} ₽), новый по акции 3 759 ¥ (48 867 ₽) → б/у {"дороже" if m5>3759 else "дешевле"} на {abs(m5-3759):.0f} ¥.').font = Font(italic=True, size=10, color='C00000')
        n = 1
    if u7:
        m7 = st.median(u7)
        u.cell(rr+2, 1, f'Ultra 7 155H б/у: медиана {m7:.0f} ¥ ({m7*RATE:.0f} ₽) против нового по верхней цене 6 499 ¥ (84 487 ₽) — экономия {6499-m7:.0f} ¥ ({(1-m7/6499)*100:.0f}%).').font = Font(italic=True, size=10, color='375623')
        n = 2
    u.cell(rr+3+n, 1, 'Вывод: б/у Ultra 5 при живой акции на новый невыгоден; смысл есть только в Ultra 7 155H 32/1T.').font = Font(italic=True, size=9, color='7F6000')
    widths(u, [20,14,9,10,13,10,14])

    # --- лоты без паспортов ---
    lots_only = [l_ for l_ in lots if l_.get('units_read', 0) < len(l_.get('prices', [])) and len(l_.get('prices', [])) >= 3
                 and model_of(l_.get('cur') or '') in TARGETS]
    if lots_only:
        w = wb.create_sheet('Лоты без паспортов')
        title(w, 'Лоты, где прочитались только цены (паспорта недоступны)', f"Курс 1 ¥ = {RATE} ₽ · {len(lots_only)} лот(ов)")
        head(w, ['Лот','Модель (по названию)','Юнитов','Мин, ¥','Q1, ¥','Медиана, ¥','Q3, ¥','Макс, ¥','Медиана, ₽'])
        r = 5
        for l_ in sorted(lots_only, key=lambda x: -len(x['prices'])):
            ps = sorted(l_['prices']); q = st.quantiles(ps, n=4)
            name = model_of(l_.get('cur') or '')
            for i, v in enumerate([l_['sku'], name, len(ps), min(ps), q[0], st.median(ps), q[2], max(ps), round(st.median(ps)*RATE)], 1):
                c = w.cell(r, i, v); c.border = BOX; c.font = Font(size=10)
                if i >= 4: c.number_format = '#,##0'
            r += 1
        w.cell(r+1, 1, 'Это цены юнитов из лота без конфигураций: годится для диапазона, не для цены за конкретный CPU.').font = Font(italic=True, size=9, color='C00000')
        widths(w, [16,24,9,10,10,14,10,10,14])

    # --- динамика ---
    d = wb.create_sheet('Динамика')
    title(d, 'Динамика цен между снимками', f"Текущий снимок {snap['ts']}")
    if not prev:
        d.cell(4, 1, 'Нужен второй снимок: запустите collect.py повторно (например, через сутки) — здесь появится сравнение.').font = Font(size=11)
        d.cell(5, 1, 'Что будет считаться: медиана по каждому CPU (было/стало/Δ), цена каждого юнита по № отчёта, число проданных юнитов.').font = Font(italic=True, size=9, color='595959')
    else:
        head(d, ['Модель','Процессор','Было, ¥','Стало, ¥','Δ, ¥','Δ, %','Δ, ₽','Юнитов было','Юнитов стало'])
        g1, g2 = {}, {}
        for x in prev['units']:
            if x['model'] in TARGETS: g1.setdefault((x['model'], x['cpu']), []).append(x['price'])
        for x in units: g2.setdefault((x['model'], x['cpu']), []).append(x['price'])
        r = 5
        for k in sorted(set(g1) | set(g2)):
            a_, b_ = st.median(g1[k]) if k in g1 else None, st.median(g2[k]) if k in g2 else None
            vals = [k[0], k[1], a_ or '—', b_ or '—',
                    round(b_-a_) if a_ and b_ else '—',
                    f"{(b_/a_-1)*100:+.0f}%" if a_ and b_ else '—',
                    round((b_-a_)*RATE) if a_ and b_ else '—',
                    len(g1.get(k,[])), len(g2.get(k,[]))]
            for i, v in enumerate(vals, 1):
                c = d.cell(r, i, v); c.border = BOX; c.font = Font(size=10)
                if i in (3,4,5,7): c.number_format = '#,##0'
            r += 1
        gone = {x.get('report') for x in prev['units']} - {x.get('report') for x in units}
        d.cell(r+1, 1, f"Исчезло юнитов (вероятно проданы): {len(gone)}").font = Font(bold=True, size=10)
        widths(d, [20,22,11,11,10,9,10,13,13])

    # --- движение юнитов (два листа: фильтр по CPU и все Pro) ---
    watch = CFG.get('watch_cpus', [])
    reg_p, ev_p = os.path.join(HERE,'data','registry.json'), os.path.join(HERE,'data','events.json')
    if os.path.exists(reg_p) and os.path.exists(ev_p):
        reg = json.load(open(reg_p, encoding='utf-8'))
        ev = json.load(open(ev_p, encoding='utf-8'))
        focus(wb, units, ev, reg, watch, snap.get('lots', []))
        movement(wb, 'Движение юнитов', f"Фильтр CPU: {', '.join(watch)} · только RedmiBook Pro 14/15", reg, ev, watch)
        movement(wb, 'Движение все Pro', 'Все процессоры · RedmiBook Pro 14/15', reg, ev, None)

    # --- статус автопайплайна ---
    ast_p = os.path.join(HERE, 'data', 'auto_state.json')
    stt = json.load(open(ast_p, encoding='utf-8')) if os.path.exists(ast_p) else {}
    sts = wb.create_sheet('Статус сбора')
    title(sts, 'Статус автоматического сбора', 'Обновляется само, без участия человека')
    head(sts, ['Параметр','Значение'], row=4)
    b = stt.get('budget', {})
    reg_n = len(reg_all)
    lot_ids = {str(u) for l in lots for u in (l.get('unit_ids') or [])}
    lot_units = len(lot_ids)
    pending = len([u for u in lot_ids if u not in reg_all])
    rows = [('Последний прогон', stt.get('last_run','—')),
            ('Всего прогонов', stt.get('runs','—')),
            ('Последняя блокировка', stt.get('last_block','нет')),
            ('Пауза до', stt.get('backoff_until') or 'нет'),
            ('Бюджет: лотов / разведка / паспорта', f"{b.get('lots','—')} / {b.get('probe','—')} / {b.get('pass','—')}"),
            ('Лотов в базе', stt.get('stats',{}).get('lots_total','—')),
            ('Юнитов с паспортом', reg_n),
            ('Юнитов в лотах (всего)', lot_units),
            ('Осталось дочитать', pending)]
    r0 = 5
    for k, v in rows:
        sts.cell(r0,1,k).border = BOX; sts.cell(r0,1).font = Font(size=10)
        c = sts.cell(r0,2,v); c.border = BOX; c.font = Font(size=10, bold=(k=='Осталось дочитать'))
        if k=='Осталось дочитать' and isinstance(v,int) and v>0: c.fill = ORG
        r0 += 1
    sts.cell(r0+1,1,'Агент запускается каждые 20 минут. При блокировке сам увеличивает паузу (10→20→40→60 мин) и урезает бюджеты,').font = Font(italic=True, size=9, color='7F6000')
    sts.cell(r0+2,1,'после успешных прогонов — плавно возвращает. Вмешательство не требуется.').font = Font(italic=True, size=9, color='7F6000')
    widths(sts, [38,42])

    # --- покрытие: сколько юнитов в лотах реально опознано ---
    cov = wb.create_sheet('Покрытие')
    title(cov, 'Покрытие данных: есть ли дыры', f"Снимок {snap['ts']} · курс 1 ¥ = {RATE} ₽")
    pro_lots = [l for l in lots if l.get('unit_ids') and model_of(l.get('cur') or l.get('title') or '') in TARGETS]
    ids_all, ids_known = set(), set()
    gaps = []
    for l in pro_lots:
        miss = [u for u in l['unit_ids'] if str(u) not in reg_all]
        ids_all |= {str(u) for u in l['unit_ids']}
        ids_known |= {str(u) for u in l['unit_ids']} - {str(u) for u in miss}
        if miss: gaps.append((l['sku'], model_of(l.get('cur') or ''), len(l['unit_ids']), len(miss)))
    total = len(ids_all) or 1
    head(cov, ['Показатель','Значение'], row=4)
    rows = [('Лотов Pro 14/15', len(pro_lots)),
            ('Юнитов в лотах', len(ids_all)),
            ('Опознано (есть паспорт)', len(ids_known)),
            ('Покрытие', f"{len(ids_known)/total*100:.0f}%")]
    r0 = 5
    for k, v in rows:
        cov.cell(r0,1,k).border = BOX; cov.cell(r0,1).font = Font(size=10)
        c = cov.cell(r0,2,v); c.border = BOX; c.font = Font(size=10, bold=(k=='Покрытие'))
        c.fill = GRN if k=='Покрытие' and len(ids_known)/total > 0.95 else (ORG if k=='Покрытие' else PatternFill())
        r0 += 1
    r0 += 1
    cov.cell(r0,1,'Лоты с непрочитанными юнитами').font = Font(bold=True, size=11); cov.cell(r0,1).fill = SUB; r0 += 1
    head(cov, ['Лот','Модель','Юнитов всего','Без паспорта'], row=r0); r0 += 1
    if not gaps:
        cov.cell(r0,1,'Дыр нет: все юниты опознаны.').font = Font(italic=True, size=9, color='375623')
    for g in gaps:
        for i,v in enumerate(g,1):
            c = cov.cell(r0,i,v); c.border = BOX; c.font = Font(size=10); c.fill = ORG
        r0 += 1
    cov.cell(r0+1,1,'Покрытие ниже 95% означает: часть позиций сайта ещё не опознана по CPU — они доберутся капельным режимом.').font = Font(italic=True, size=9, color='7F6000')
    widths(cov, [26,22,16,16])

    # --- словарь ---
    g = wb.create_sheet('Словарь обозначений')
    title(g, 'Китайские обозначения JD и перевод', '')
    head(g, ['Обозначение JD','Перевод','Что означает на практике'], row=3)
    items = [('成色 / 7成新','состояние «7 из 10»','заметные следы использования'),
             ('8成新','«8 из 10»','умеренные следы, косметика в норме'),
             ('9成新','«9 из 10»','слабые следы, почти как новый'),
             ('95新','«95% нового»','почти новый, минимальные следы'),
             ('99新','«99% нового»','практически новый'),
             ('电池效率 80%-90%','износ батареи 80–90%','ёмкость 80–90% от исходной'),
             ('电池效率 90%以上','износ 90%+','батарея в хорошем состоянии'),
             ('屏幕划痕 轻微','царапины: лёгкие','видны под углом'),
             ('屏幕划痕 细微','царапины: почти незаметные','микроследы'),
             ('屏幕划痕 明显','царапины: заметные','видны при работе'),
             ('适配器 有','адаптер: есть','зарядка в комплекте'),
             ('适配器 无','адаптер: нет','зарядку покупать отдельно (+50–100 ¥)'),
             ('集显','встроенная графика','без дискретной карты'),
             ('独显2G / MX450 / MX550','дискретная 2 ГБ','NVIDIA MX-серия'),
             ('二手','б/у','вторичный товар'),
             ('拍拍严选','«Папай отборное»','официальный б/у-канал JD с проверкой')]
    for j, row in enumerate(items, 4):
        for k, v in enumerate(row, 1):
            c = g.cell(j, k, v); c.border = BOX; c.font = Font(size=10)
        if j % 2 == 0:
            for k in range(1, 4): g.cell(j, k).fill = SUB
    widths(g, [26,30,60])

    # --- методика ---
    m = wb.create_sheet('Методика')
    m.column_dimensions['A'].width = 112
    txt = [('Как считается', True),
      ('Источник: карточки item.m.jd.com, продавец «拍拍二手自营旗舰店» (официальный б/у-канал JD 拍拍严选).', False),
      ('Каждая единица — отдельный юнит с паспортом проверки: CPU, память, SSD, состояние, батарея, царапины, адаптер.', False),
      ('Цена берётся из списка юнитов лота (selectableList), а не из «цены от» в поиске.', False),
      ('Дедупликация по номеру отчёта, чтобы один и тот же юнит не попал дважды.', False),
      ('Модель определяется по названию юнита; для AMD поколение уточняется по модели (Pro 14: 5500U/5700U, Pro 15: 5600H/5800H).', False),
      ('Курс 1 ¥ = {} ₽ задаётся в config.json.'.format(RATE), False),
      ('', False),
      ('Ограничения', True),
      ('JD включает антибот (risk_handler) после серии запросов: поиск и карточки отдают 302. Сбор останавливается и помечает снимок как blocked.', False),
      ('При блоке данные не теряются: лоты и цены юнитов сохраняются, паспорта добираются в следующем прогоне.', False),
      ('Лоты без паспортов попадают на отдельный лист — по ним считается только диапазон цен.', False),
    ]
    for i, (t, b) in enumerate(txt, 1):
        c = m.cell(i, 1, t); c.font = Font(bold=True, size=12 if b else 10)
        c.alignment = Alignment(wrap_text=True, vertical='top')
        if b: c.fill = SUB

    wb.save(out)
    print(f"отчёт: {out}")
    print(f"снимок: {path} · юнитов {len(units)} (Pro 14: {len(pro14)}, Pro 15: {len(pro15)}, Ultra: {len(ultra)}) · лотов {len(lots)}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
