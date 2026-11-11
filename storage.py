"""儲存層：設定 DATABASE_URL（Neon/Supabase 免費 Postgres）就存資料庫，否則存本機 JSON 檔。"""
import os, json, threading, ssl
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, unquote
D=os.path.dirname(os.path.abspath(__file__))
import re, sys
_raw=os.environ.get("DATABASE_URL","")
_m=re.findall(r"postgres(?:ql)?://[^\s'\"]+",_raw)   # 容許前後有 psql、引號、空白
URL=_m[0] if _m else ""
if _raw and not URL: print("警告：DATABASE_URL 不是 postgresql:// 連線字串，改用本機檔案", file=sys.stderr)
FILES={"db":"data.json","users":"users.json"}
_cache={}; _lock=threading.Lock()
NOCACHE={"users"}   # 帳號每次都重讀，CLI 改帳號不必重啟
def _conn():
    import pg8000.native
    u=urlparse(URL)
    return pg8000.native.Connection(user=unquote(u.username or ""),password=unquote(u.password or ""),host=u.hostname,port=u.port or 5432,
        database=(u.path or "/postgres")[1:],ssl_context=ssl.create_default_context(),timeout=30)
HTTP=os.environ.get("DB_TRANSPORT")=="http"   # Neon 的 HTTPS SQL 端點（5432 埠被擋時用）
def _http(sql,params):
    import urllib.request
    host=urlparse(URL).hostname
    r=urllib.request.Request(f"https://{host}/sql",data=json.dumps({"query":sql,"params":params}).encode(),
        headers={"Neon-Connection-String":URL,"Content-Type":"application/json"})
    return [list(x.values()) for x in json.load(urllib.request.urlopen(r,timeout=60)).get("rows",[])]
def _q(sql,params=()):
    """sql 用 $1,$2 參數"""
    global HTTP
    if not HTTP:
        try:
            c=_conn(); d={f"p{i+1}":v for i,v in enumerate(params)}
            r=c.run(re.sub(r"\$(\d+)",r":p\1",sql),**d); c.close(); return r or []
        except Exception as e:
            if "neon.tech" not in URL: raise
            print("TCP 連線失敗，改用 Neon HTTPS 端點：",type(e).__name__,file=sys.stderr); HTTP=True
    return _http(sql,list(params))
if URL:
    _q("CREATE TABLE IF NOT EXISTS kv (k text PRIMARY KEY, v text NOT NULL, updated timestamptz DEFAULT now())")
    _q("CREATE TABLE IF NOT EXISTS user_presence (username text PRIMARY KEY, lat double precision NOT NULL, lng double precision NOT NULL, accuracy double precision, updated_at timestamptz NOT NULL DEFAULT now())")
def backend(): return ("postgres-http" if HTTP else "postgres") if URL else "file"
def get(k,default=None):
    with _lock:
        if k in _cache and k not in NOCACHE: return json.loads(_cache[k])
        if URL:
            r=_q("SELECT v FROM kv WHERE k=$1",(k,)); raw=r[0][0] if r else None
        else:
            p=os.path.join(D,FILES.get(k,k+".json")); raw=open(p).read() if os.path.exists(p) else None
        if raw is None: return default
        _cache[k]=raw; return json.loads(raw)
def put(k,v):
    raw=json.dumps(v,ensure_ascii=False)
    with _lock:
        if URL:
            _q("INSERT INTO kv(k,v) VALUES($1,$2) ON CONFLICT(k) DO UPDATE SET v=$2, updated=now()",(k,raw))
        else:
            p=os.path.join(D,FILES.get(k,k+".json")); open(p+".tmp","w").write(raw); os.replace(p+".tmp",p)
        _cache[k]=raw

PRESENCE_FILE="presence.json"
PRESENCE_TTL=600
def _parse_ts(v):
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if v is None or v=="": return None
    s=str(v).strip().replace("Z","+00:00")
    try:
        dt=datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
def _fmt_ts(v):
    dt=_parse_ts(v)
    return dt.astimezone(timezone.utc).isoformat() if dt else str(v or "")
def _presence_path():
    return os.path.join(D, PRESENCE_FILE)
def _presence_file_load():
    p=_presence_path()
    if not os.path.exists(p): return {}
    try:
        d=json.loads(open(p).read())
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}
def _presence_file_save(d):
    p=_presence_path(); raw=json.dumps(d,ensure_ascii=False)
    open(p+".tmp","w").write(raw); os.replace(p+".tmp",p)
def upsert_presence(username, lat, lng, accuracy=None, at=None):
    """每位使用者一列，覆寫，不留歷史。at 僅測試用。"""
    if not username: raise ValueError("缺少使用者")
    acc=None if accuracy in (None,"") else float(accuracy)
    ts=at if isinstance(at, datetime) else (_parse_ts(at) if at else datetime.now(timezone.utc))
    if ts.tzinfo is None: ts=ts.replace(tzinfo=timezone.utc)
    with _lock:
        if URL:
            iso=ts.astimezone(timezone.utc).isoformat()
            _q("INSERT INTO user_presence(username,lat,lng,accuracy,updated_at) VALUES($1,$2,$3,$4,$5::timestamptz) ON CONFLICT(username) DO UPDATE SET lat=$2, lng=$3, accuracy=$4, updated_at=$5::timestamptz",
               (username, float(lat), float(lng), acc, iso))
        else:
            d=_presence_file_load()
            d[username]={"lat":float(lat),"lng":float(lng),"accuracy":acc,"updated_at":ts.astimezone(timezone.utc).isoformat()}
            _presence_file_save(d)
def delete_presence(username):
    if not username: return
    with _lock:
        if URL:
            _q("DELETE FROM user_presence WHERE username=$1",(username,))
        else:
            d=_presence_file_load(); d.pop(username, None); _presence_file_save(d)
def _row_presence(user,lat,lng,accuracy,updated_at):
    return {"user":user,"lat":float(lat),"lng":float(lng),"accuracy":(None if accuracy in (None,"") else float(accuracy)),"updated_at":_fmt_ts(updated_at)}
def list_presence(now=None, ttl=PRESENCE_TTL, purge=True):
    """只回傳 ttl 秒內有更新的位置；過期視為離開，可一併清除。"""
    now=_parse_ts(now) or datetime.now(timezone.utc)
    if now.tzinfo is None: now=now.replace(tzinfo=timezone.utc)
    cutoff=now-timedelta(seconds=int(ttl))
    cut_iso=cutoff.astimezone(timezone.utc).isoformat()
    out=[]
    with _lock:
        if URL:
            if purge:
                _q("DELETE FROM user_presence WHERE updated_at < $1::timestamptz",(cut_iso,))
            rows=_q("SELECT username, lat, lng, accuracy, updated_at FROM user_presence WHERE updated_at >= $1::timestamptz ORDER BY username",(cut_iso,))
            for r in rows or []:
                out.append(_row_presence(r[0],r[1],r[2],r[3],r[4]))
        else:
            d=_presence_file_load(); changed=False
            for u,rec in list(d.items()):
                if not isinstance(rec, dict):
                    if purge: d.pop(u, None); changed=True
                    continue
                ts=_parse_ts(rec.get("updated_at"))
                if ts is None or ts < cutoff:
                    if purge: d.pop(u, None); changed=True
                    continue
                out.append(_row_presence(u, rec.get("lat"), rec.get("lng"), rec.get("accuracy"), ts))
            if changed: _presence_file_save(d)
    out.sort(key=lambda x:x["user"])
    return out
