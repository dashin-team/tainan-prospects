"""儲存層：設定 DATABASE_URL（Neon/Supabase 免費 Postgres）就存資料庫，否則存本機 JSON 檔。"""
import os, json, threading, ssl
from urllib.parse import urlparse, unquote
D=os.path.dirname(os.path.abspath(__file__))
import re, sys
_raw=os.environ.get("DATABASE_URL","")
_m=re.findall(r"postgres(?:ql)?://[^\s'\"]+",_raw)   # 容許前後有 psql、引號、空白
URL=_m[0] if _m else ""
if _raw and not URL: print("警告：DATABASE_URL 不是 postgresql:// 連線字串，改用本機檔案", file=sys.stderr)
FILES={"db":"data.json","users":"users.json"}
_cache={}; _lock=threading.Lock()
def _conn():
    import pg8000.native
    u=urlparse(URL)
    return pg8000.native.Connection(user=unquote(u.username or ""),password=unquote(u.password or ""),host=u.hostname,port=u.port or 5432,
        database=(u.path or "/postgres")[1:],ssl_context=ssl.create_default_context(),timeout=30)
if URL:
    c=_conn(); c.run("CREATE TABLE IF NOT EXISTS kv (k text PRIMARY KEY, v text NOT NULL, updated timestamptz DEFAULT now())"); c.close()
def backend(): return "postgres" if URL else "file"
def get(k,default=None):
    with _lock:
        if k in _cache: return json.loads(_cache[k])
        if URL:
            c=_conn(); r=c.run("SELECT v FROM kv WHERE k=:k",k=k); c.close(); raw=r[0][0] if r else None
        else:
            p=os.path.join(D,FILES.get(k,k+".json")); raw=open(p).read() if os.path.exists(p) else None
        if raw is None: return default
        _cache[k]=raw; return json.loads(raw)
def put(k,v):
    raw=json.dumps(v,ensure_ascii=False)
    with _lock:
        if URL:
            c=_conn(); c.run("INSERT INTO kv(k,v) VALUES(:k,:v) ON CONFLICT(k) DO UPDATE SET v=:v, updated=now()",k=k,v=raw); c.close()
        else:
            p=os.path.join(D,FILES.get(k,k+".json")); open(p+".tmp","w").write(raw); os.replace(p+".tmp",p)
        _cache[k]=raw
