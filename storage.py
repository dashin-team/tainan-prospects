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
