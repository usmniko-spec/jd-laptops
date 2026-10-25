"""Общая библиотека: разбор карточек JD 二手 (拍拍严选) и нормализация данных."""
import json, re, hashlib, os, time, subprocess, random

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

# ---------- переводы обозначений JD ----------
COND = {'7成新':'7/10','8成新':'8/10','9成新':'9/10','95新':'95% нового','99新':'99% нового','6成新':'6/10'}
BATT = {'80%-90%':'80–90%','90%以上':'90%+','70%-80%':'70–80%','60%-70%':'60–70%','50%-60%':'50–60%'}
SCR  = {'轻微':'лёгкие','细微':'почти незаметные','明显':'заметные','无':'нет','严重':'сильные'}
ADP  = {'有':'есть','无':'нет'}

def tr(d, v):
    return d.get(v, v) if v else ''

# ---------- устойчивый разбор JS-объекта (trailing commas) ----------
def _js_to_py(raw):
    out=[]; i=0; instr=False; esc=False
    while i < len(raw):
        c=raw[i]
        if instr:
            out.append(c)
            if esc: esc=False
            elif c=='\\': esc=True
            elif c=='"': instr=False
        else:
            if c=='"': instr=True; out.append(c)
            elif c==',':
                k=i+1
                while k<len(raw) and raw[k] in ' \t\r\n': k+=1
                if k<len(raw) and raw[k] in '}]': i+=1; continue
                out.append(c)
            else: out.append(c)
        i+=1
    return json.loads(''.join(out))

def extract_obj(html, varname):
    i = html.find(varname)
    if i < 0: raise ValueError(f'{varname} not found')
    s = html.find('{', i)
    if s < 0: raise ValueError('no object')
    d=0; instr=False; esc=False
    for j in range(s, len(html)):
        c=html[j]
        if instr:
            if esc: esc=False
            elif c=='\\': esc=True
            elif c=='"': instr=False
        else:
            if c=='"': instr=True
            elif c=='{': d+=1
            elif c=='}':
                d-=1
                if d==0: return _js_to_py(html[s:j+1])
    raise ValueError('unbalanced object')

# ---------- CPU нормализация ----------
AMD_BY_MODEL = {
    'Pro 14': {('5','5'):'Ryzen 5 5500U', ('7','5'):'Ryzen 7 5700U',
               ('5','6'):'Ryzen 5 6600H', ('7','6'):'Ryzen 7 6800H'},
    'Pro 15': {('5','5'):'Ryzen 5 5600H', ('7','5'):'Ryzen 7 5800H',
               ('5','6'):'Ryzen 5 6600H', ('7','6'):'Ryzen 7 6800H'},
}
AMD_FALLBACK = {('5','5'):'Ryzen 5 5000', ('7','5'):'Ryzen 7 5000',
                ('5','6'):'Ryzen 5 6000', ('7','6'):'Ryzen 7 6000'}

def model_of(name):
    n = (name or '').replace('Redmi Book Pro', 'RedmiBook Pro').replace('RedmiBookPro', 'RedmiBook Pro')
    low = n.lower()
    for size in ('16', '15', '14', '13'):
        if f'book pro {size}' in low: return f'RedmiBook Pro {size}'
    if 'redmi book 14' in low: return 'REDMI Book 14'
    if 'redmibook 14' in low: return 'RedmiBook 14'
    if 'redmi g pro' in low: return 'Redmi G Pro'
    if 'redmi g' in low: return 'Redmi G'
    if '笔记本air' in n or 'book air' in low: return 'Xiaomi Air'
    if '游戏本 15.6' in n: return 'Xiaomi Gaming 15'
    if '笔记本 pro 15' in low: return 'Xiaomi Pro 15'
    return re.sub(r'\s+\d+(\.\d+)?英寸.*$', '', n.replace('小米','').strip())[:32] or '—'

def cpu_of(name):
    n = name or ''
    mdl = model_of(n)
    u = re.search(r'Ultra ([57]) (\d{3}H)', n)
    if u: return f"Ultra {u.group(1)} {u.group(2)}", 'Intel'
    a = re.search(r'Ryzen ([57]) (\d)代', n)
    if a:
        key = (a.group(1), a.group(2))
        tbl = AMD_BY_MODEL.get(' '.join(mdl.split()[-2:])) if mdl.startswith('RedmiBook Pro') else None
        return (tbl or AMD_FALLBACK).get(key, f'Ryzen {a.group(1)} {a.group(2)}000'), 'AMD'
    i = re.search(r'(i[357]) (\d{1,2})代', n)
    if i: return f"Intel {i.group(1)} {i.group(2)}-го пок.", 'Intel'
    c = re.search(r'Core ([357]) (\d{3}H)', n)
    if c: return f"Core {c.group(1)} {c.group(2)}", 'Intel'
    if 'M3' in n: return 'M3', 'ARM'
    return '—', '—'

def gpu_of(name):
    n = name or ''
    m = re.search(r'(RTX\s?\d{4}|GTX\s?\d{4}|MX\d{3})', n)
    if m: return m.group(1)
    if '集显' in n: return 'встроенная'
    if '独显' in n:
        d = re.search(r'独显(\d)G', n)
        return f'дискретная {d.group(1)} ГБ' if d else 'дискретная'
    return ''

def cfg_of(name):
    n = name or ''
    m = re.search(r'(\d+)G (\d+)(G|T)\b', n)
    if not m: return '', ''
    ssd = m.group(2) + (' ТБ' if m.group(3)=='T' else ' ГБ')
    return m.group(1) + ' ГБ', ssd

# ---------- загрузка ----------
class Fetcher:
    """Загрузка с таймаутами через requests (curl на этом канале зависает)."""
    def __init__(self, cache_dir, ttl=6*3600, delay=(2.5,4.0), proxy=None):
        self.cache_dir=cache_dir; self.ttl=ttl; self.delay=delay; self.proxy=proxy
        os.makedirs(cache_dir, exist_ok=True)
        self.blocked=False; self.requests=0; self.empty_streak=0
        import urllib.request, http.cookiejar
        self.cj = http.cookiejar.MozillaCookieJar(os.path.join(cache_dir, 'cookies.txt'))
        try: self.cj.load(ignore_discard=True, ignore_expires=True)
        except Exception: pass
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
        self.block_kind = None
    def _path(self,url): return os.path.join(self.cache_dir, hashlib.sha1(url.encode()).hexdigest()+'.html')
    def get(self, url, refresh=False):
        p=self._path(url)
        if not refresh and os.path.exists(p) and time.time()-os.path.getmtime(p) < self.ttl:
            return open(p, encoding='utf-8', errors='ignore').read()
        if self.blocked: return None
        time.sleep(random.uniform(*self.delay))
        target = url if not self.proxy else self.proxy.replace('{url}', __import__('urllib.parse',fromlist=['quote']).quote(url, safe=''))
        import urllib.request, urllib.error, socket, ssl
        req = urllib.request.Request(target, headers={'User-Agent': UA,
                                      'Accept-Language': 'zh-CN,zh;q=0.9',
                                      'Referer': 'https://item.m.jd.com/'})
        code, raw = None, b''
        for attempt in range(3):
            try:
                with self.opener.open(req, timeout=20) as resp:
                    code = resp.getcode(); raw = resp.read()
                break
            except urllib.error.HTTPError as e:
                code = e.code; raw = b''; break
            except Exception:
                # сеть/DPI: TLS-обрывы и таймауты — повторяем, это не бан
                time.sleep(2 + attempt * 3)
        if code is None:
            self.blocked = True; self.block_kind = 'network'; return None
        self.requests += 1
        if code in (404, 410):
            return ''      # такого SKU нет — не блок
        if code != 200:
            self.blocked = True; self.block_kind = 'challenge'; return None
        html = raw.decode('utf-8', 'ignore')
        if 'risk_handler' in html[:2000]:
            self.blocked = True; self.block_kind = 'challenge'; return None
        if 'search_prolist_item' not in html and 'inspectyoupin' not in html:
            # пустая заглушка: обычно значит «такого SKU/лота нет», но серия подряд = блок
            self.empty_streak += 1
            if self.empty_streak >= 15:
                self.blocked = True; self.block_kind = 'shell'
            return ''
        self.empty_streak = 0
        open(p,'w',encoding='utf-8').write(html)
        try: self.cj.save(ignore_discard=True, ignore_expires=True)
        except Exception: pass
        return html

# ---------- парсинг ----------
def parse_sku(html):
    d = extract_obj(html, 'window._itemInfo')
    ins = d.get('inspectyoupin') or {}
    if not ins.get('baseInfo'): return None
    return {
        'sku': str(d['product'].get('skuId')),
        'title': d['product'].get('skuName',''),
        'vender': d.get('venderId'),
        'units': ins.get('selectableInfo',{}).get('selectableList',[]),
        'cur': ins['baseInfo'].get('inspectSkuName'),
    }

def parse_unit(html, sku, unit_id, price):
    d = extract_obj(html, 'window._itemInfo')
    ins = d['inspectyoupin']; b = ins['baseInfo']
    ol = {a['attrName']: a['attrValue'] for a in ins['outlineInfo']['baseOutlineInfos']}
    name = b.get('inspectSkuName','')
    cpu, plat = cpu_of(name)
    ram, ssd = cfg_of(name)
    return {
        'sku': sku, 'unit_id': str(unit_id), 'model': model_of(name), 'name': name,
        'cpu': cpu, 'platform': plat, 'gpu': gpu_of(name), 'ram': ram, 'ssd': ssd,
        'cond_cn': ol.get('成色'), 'batt_cn': ol.get('电池效率'),
        'scratch_cn': ol.get('屏幕划痕'), 'adapter_cn': ol.get('适配器'),
        'price': float(price), 'report': ins['reportInfo'].get('uniqueCode'),
        'url': f"https://item.m.jd.com/product/{sku}.html?inspectSkuId={unit_id}",
    }

def parse_search(html):
    out=[]
    for b in html.split('<div class="search_prolist_item"')[1:]:
        sku=re.search(r'skuid=(\d+)',b); pr=re.search(r'firprice="([\d.]+)"',b)
        nm=re.search(r'class="search_prolist_title"[^>]*>(.*?)</div>',b,re.S)
        sh=re.search(r'class="shop_name">(.*?)</span>',b,re.S)
        if not (sku and nm): continue
        out.append({'sku':sku.group(1),'price':pr.group(1) if pr else None,
                    'title':re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',nm.group(1))).strip(),
                    'shop':re.sub(r'<[^>]+>','',sh.group(1)).strip() if sh else ''})
    return out
