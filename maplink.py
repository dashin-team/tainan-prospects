"""從 Google 地圖連結或「緯度, 經度」取出座標。短網址才會連線，且只跟隨 Google 網域。"""
import re, urllib.parse
from urllib.request import Request, HTTPSHandler, build_opener, HTTPErrorProcessor

SHORT_HOSTS={"maps.app.goo.gl","goo.gl"}
MAP_HOSTS={"www.google.com","google.com","maps.google.com","www.google.com.tw","maps.google.com.tw"}
PAIR=re.compile(r"^\s*(-?\d{1,3}(?:\.\d+)?)\s*[,，]\s*(-?\d{1,3}(?:\.\d+)?)\s*$")
PIN=re.compile(r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)")
AT=re.compile(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)")
QKEYS=("query","q","ll")

class _StopRedirect(HTTPErrorProcessor):
    def http_response(self, request, response):
        return response
    https_response=http_response

def _host(url):
    return (urllib.parse.urlsplit(url).hostname or "").lower().rstrip(".")

def _https(url):
    p=urllib.parse.urlsplit(url)
    return p.scheme=="https" and bool(p.hostname)

def _pair(a,b):
    la,ln=float(a),float(b)
    if la!=la or ln!=ln or abs(la)==float("inf") or abs(ln)==float("inf"):
        raise ValueError("座標格式不正確")
    if not (-90<=la<=90 and -180<=ln<=180):
        raise ValueError("座標格式不正確")
    return la,ln

def _maybe_pair(s):
    s=re.sub(r"^loc:\s*","",(s or "").strip(),flags=re.I)
    m=PAIR.fullmatch(s)
    return _pair(m.group(1),m.group(2)) if m else None

def parse_map_text(text):
    """本地解析。!3d!4d 是地標本身，優先於 @ 地圖中心。"""
    text=urllib.parse.unquote((text or "").strip())
    m=PAIR.fullmatch(text)
    if m: return _pair(m.group(1),m.group(2))
    pins=PIN.findall(text)
    if pins: return _pair(*pins[-1])
    m=AT.search(text)
    if m: return _pair(m.group(1),m.group(2))
    qs=urllib.parse.parse_qs(urllib.parse.urlsplit(text).query)
    for k in QKEYS:
        if qs.get(k):
            got=_maybe_pair(qs[k][0])
            if got: return got
    raise ValueError("找不到座標，請貼上 Google 地圖連結或「緯度, 經度」")

def default_fetch(url, timeout):
    if not _https(url) or _host(url) not in SHORT_HOSTS|MAP_HOSTS:
        raise ValueError("不支援的連結")
    opener=build_opener(HTTPSHandler(), _StopRedirect())
    req=Request(url, headers={"User-Agent":"tainan-prospects/1.0"})
    with opener.open(req, timeout=timeout) as r:
        code=getattr(r,"status",None) or r.getcode()
        body=r.read(8192) if code==200 else b""
        return code, r.headers.get("Location"), body

def _html_next(body):
    text=body.decode("utf-8","replace") if isinstance(body,(bytes,bytearray)) else str(body or "")
    m=re.search(r"http-equiv=[\"']refresh[\"'][^>]*content=[\"'][^\"']*?url=([^\"']+)", text, re.I)
    if not m: m=re.search(r"content=[\"']\d+\s*;\s*url=([^\"']+)", text, re.I)
    if m: return m.group(1).strip()
    m=re.search(r"rel=[\"']canonical[\"'][^>]*href=[\"']([^\"']+)", text, re.I)
    return m.group(1).strip() if m else None

def resolve_short_link(url, timeout=8, fetch=None):
    fetch=fetch or default_fetch
    cur=(url or "").strip(); seen=set()
    for _ in range(5):
        if cur in seen: raise ValueError("連結重新導向循環")
        seen.add(cur)
        if not _https(cur): raise ValueError("只接受 https 連結")
        host=_host(cur)
        if host in MAP_HOSTS: return cur
        if host not in SHORT_HOSTS: raise ValueError("不支援的連結")
        code, loc, body=fetch(cur, timeout)
        if code in (301,302,303,307,308) and loc:
            cur=urllib.parse.urljoin(cur, loc.strip()); continue
        if code==200:
            nxt=_html_next(body)
            if nxt:
                cur=urllib.parse.urljoin(cur, nxt); continue
        raise ValueError("無法解析這個短連結，請改貼完整網址或座標")
    raise ValueError("短連結重新導向次數過多")

def extract_point(text, timeout=8, fetch=None):
    raw=(text or "").strip()
    if not raw: raise ValueError("請貼上 Google 地圖連結或座標")
    if PAIR.fullmatch(raw): return parse_map_text(raw)
    looks=raw.startswith("http://") or raw.startswith("https://") or "goo.gl" in raw or "google." in raw or raw.startswith("maps.app")
    if not looks: return parse_map_text(raw)
    url=raw if raw.startswith("http://") or raw.startswith("https://") else "https://"+raw
    if not _https(url): raise ValueError("只接受 https 連結")
    host=_host(url)
    if host in SHORT_HOSTS: url=resolve_short_link(url, timeout=timeout, fetch=fetch)
    elif host not in MAP_HOSTS: raise ValueError("不支援的連結")
    return parse_map_text(url)
