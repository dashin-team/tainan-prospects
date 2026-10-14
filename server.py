"""台南團險/產責險開發追蹤系統 後端（Python 標準函式庫 + openpyxl）。資料存在 data.json，多人共用。"""
import gzip, json, os, io, threading, time, uuid, datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import openpyxl, hashlib, secrets, hmac
import storage
def _j(p,d):
    try: return json.load(open(p))
    except Exception: return d
def hashpw(pw,salt=None):
    salt=salt or secrets.token_hex(16); return salt+"$"+hashlib.pbkdf2_hmac("sha256",pw.encode(),salt.encode(),200000).hex()
def checkpw(pw,h):
    salt=h.split("$")[0]; return hmac.compare_digest(hashpw(pw,salt),h)
def secret():
    k=os.environ.get("SECRET_KEY") or storage.get("secret")
    if not k: k=secrets.token_hex(32); storage.put("secret",k)
    return k.encode()
SECRET=None
def make_token(user):
    global SECRET; SECRET=SECRET or secret()
    p=json.dumps({"u":user,"e":int(time.time())+30*86400},ensure_ascii=False).encode().hex()
    return p+"."+hmac.new(SECRET,p.encode(),hashlib.sha256).hexdigest()
def read_token(t):
    global SECRET; SECRET=SECRET or secret()
    p,_,sig=t.partition(".")
    if not sig or not hmac.compare_digest(sig,hmac.new(SECRET,p.encode(),hashlib.sha256).hexdigest()): return None
    d=json.loads(bytes.fromhex(p)); return d["u"] if d["e"]>time.time() else None
def bootstrap_users():
    us=storage.get("users",{}) or {}
    for pair in filter(None,os.environ.get("INIT_USERS","").split(",")):
        n,_,pw=pair.partition(":")
        if n.strip() and pw and n.strip() not in us: us[n.strip()]=hashpw(pw)
    storage.put("users",us); return us
ADMINS={x.strip() for x in os.environ.get("ADMINS","shihhan,仕翰").split(",") if x.strip()}
def is_admin(u): return bool(u) and u in ADMINS
ADMIN_POST={"/api/refresh","/api/import.json","/api/import.xlsx","/api/users/add","/api/users/delete","/api/users/reset"}
PUBLIC={"/login.html","/api/login","/healthz"}
D=os.path.dirname(os.path.abspath(__file__)); DATA=os.path.join(D,"data.json"); LOCK=threading.Lock()
BF=["id","name","category","subtype","district","address","phone","website","lat","lng","status","source","note","industry","products","factory_reg_no","tax_id","owner","org_type","capital","employees","group5","geo_precision"]
BH=["ID","名稱","類別","細類","行政區","地址","電話","網站","緯度","經度","狀態","來源","備註","產業類別","主要產品","工廠登記編號","統一編號","負責人","組織型態","資本額","員工人數","團險5人以上","座標精度"]
VF=["id","business_id","business_name","district","date","visitor","contact","interest_group","interest_pl","status","next_followup","notes","created_by","updated"]
VH=["紀錄ID","店家ID","店家名稱","行政區","拜訪日期","拜訪人","聯絡人","團險興趣","產責險興趣","狀態","下次追蹤日","備註","登錄帳號","更新時間"]
def load():
    db=storage.get("db")
    if db is None:
        seed=json.load(open(os.path.join(D,"seed_businesses.json")))
        for b in seed: b.setdefault("status","未拜訪")
        db={"businesses":seed,"visits":[],"meta":{"last_refresh":"初始資料 2026-10-13"}}; save(db)
    return db
def save(db): storage.put("db",db)
def merge_businesses(db,new):
    idx={b["id"]:b for b in db["businesses"]}; added=updated=0
    for n in new:
        if n["id"] in idx:
            o=idx[n["id"]]
            for k in ("name","category","subtype","district","lat","lng","source"):
                o[k]=n[k]
            for k in ("address","phone","website"):   # 不覆蓋使用者手動填的
                if n.get(k) and not o.get(k): o[k]=n[k]
            updated+=1
        else:
            n["status"]="未拜訪"; db["businesses"].append(n); added+=1
    return added,updated
def xlsx(sheets):
    wb=openpyxl.Workbook(); wb.remove(wb.active)
    for title,hdr,fields,rows in sheets:
        ws=wb.create_sheet(title); ws.append(hdr)
        for r in rows: ws.append([("是" if r.get(f) is True else "否" if r.get(f) is False else r.get(f,"")) for f in fields])
        for i,h in enumerate(hdr): ws.column_dimensions[openpyxl.utils.get_column_letter(i+1)].width=max(10,min(40,len(h)*3))
        ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions
    b=io.BytesIO(); wb.save(b); return b.getvalue()
def read_sheet(ws,hdr,fields):
    rows=list(ws.iter_rows(values_only=True))
    if not rows: return []
    m={h:i for i,h in enumerate(rows[0])}; out=[]
    for r in rows[1:]:
        if not any(r): continue
        d={}
        for h,f in zip(hdr,fields):
            if h in m:
                v=r[m[h]]
                if isinstance(v,(datetime.date,datetime.datetime)): v=v.strftime("%Y-%m-%d")
                d[f]="" if v is None else v
        for f in("interest_group","interest_pl","group5"):
            if f in d: d[f]= str(d[f]).strip() in("是","True","TRUE","1","Y","y")
        out.append(d)
    return out
class H(SimpleHTTPRequestHandler):
    def __init__(s,*a,**k): super().__init__(*a,directory=os.path.join(D,"public"),**k)
    def send_bytes(s,b,ctype,code=200):
        s.send_response(code); s.send_header("Content-Type",ctype); s.send_header("Cache-Control","no-store"); s.send_header("Vary","Accept-Encoding")
        if len(b)>1024 and "gzip" in s.headers.get("Accept-Encoding",""):
            b=gzip.compress(b,6); s.send_header("Content-Encoding","gzip")
        s.send_header("Content-Length",len(b)); s.end_headers(); s.wfile.write(b)
    def send_json(s,o,code=200):
        s.send_bytes(json.dumps(o,ensure_ascii=False,separators=(",",":")).encode(),"application/json; charset=utf-8",code)
    def body(s): return s.rfile.read(int(s.headers.get("Content-Length",0)))
    def user(s):
        for c in s.headers.get("Cookie","").split(";"):
            k,_,v=c.strip().partition("=")
            if k=="tp_session":
                try:
                    u=read_token(v)
                    if u: return u
                except Exception: pass
    def guard(s):
        p=urlparse(s.path).path
        if p in PUBLIC or s.user(): return False
        if p.startswith("/api/"): s.send_json({"error":"請先登入"},401)
        else: s.send_response(302); s.send_header("Location","/login.html"); s.end_headers()
        return True
    def do_GET(s):
        if s.guard(): return
        u=urlparse(s.path); q=parse_qs(u.query)
        if u.path=="/api/me": return s.send_json({"user":s.user(),"is_admin":is_admin(s.user())})
        if u.path in("/api/export.xlsx","/api/users") and not is_admin(s.user()): return s.send_json({"error":"僅管理員可使用"},403)
        if u.path=="/api/users":
            us=storage.get("users",{}) or {}
            return s.send_json({"users":[{"name":n,"is_admin":is_admin(n)} for n in us]})
        if u.path=="/api/logout":
            s.send_response(302); s.send_header("Set-Cookie","tp_session=; Max-Age=0; Path=/"); s.send_header("Location","/login.html"); s.end_headers(); return
        if u.path=="/healthz": return s.send_json({"ok":True,"storage":storage.backend()})
        if u.path=="/api/sync":   # 輕量輪詢：只回拜訪紀錄與已變更狀態
            with LOCK:
                db=load(); return s.send_json({"visits":db["visits"],"status":{b["id"]:b.get("status") for b in db["businesses"] if b.get("status") and b.get("status")!="未拜訪"},"n":len(db["businesses"])})
        if u.path in("/","/index.html","/login.html"):
            fp=os.path.join(D,"public","index.html" if u.path=="/" else u.path[1:])
            with open(fp,"rb") as f: return s.send_bytes(f.read(),"text/html; charset=utf-8")
        if u.path=="/api/data":
            with LOCK: db=load()
            # 精簡：去掉空值欄位（前端皆以 ||'' 處理）
            return s.send_json({**db,"businesses":[{k:v for k,v in b.items() if v not in (None,"")} for b in db["businesses"]]})
        if u.path=="/api/export.xlsx":
            with LOCK: db=load()
            t=q.get("type",["all"])[0]; sh=[]
            if t in("visits","all"): sh.append(("拜訪紀錄",VH,VF,sorted(db["visits"],key=lambda v:v.get("date",""),reverse=True)))
            if t in("businesses","all"): sh.append(("店家名單",BH,BF,db["businesses"]))
            b=xlsx(sh); s.send_response(200)
            s.send_header("Content-Type","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            s.send_header("Content-Disposition",f"attachment; filename=tainan_{t}_{datetime.date.today()}.xlsx"); s.send_header("Content-Length",len(b)); s.end_headers(); return s.wfile.write(b)
        return super().do_GET()
    def do_POST(s):
        if s.guard(): return
        u=urlparse(s.path); me=s.user()
        if u.path in ADMIN_POST and not is_admin(me): return s.send_json({"error":"僅管理員可使用"},403)
        try:
            if u.path in("/api/users/add","/api/users/delete","/api/users/reset"):
                n=str(json.loads(s.body()).get("name","")).strip()
                if not n or len(n)>40: return s.send_json({"error":"請輸入名稱"},400)
                with LOCK:
                    us=storage.get("users",{}) or {}
                    if u.path.endswith("add"):
                        if n in us: return s.send_json({"error":"帳號已存在"},400)
                        us[n]=hashpw(os.environ.get("DEFAULT_PASSWORD","1234"))
                    else:
                        if n not in us: return s.send_json({"error":"帳號不存在"},404)
                        if u.path.endswith("delete"):
                            if n==me: return s.send_json({"error":"不能刪除自己"},400)
                            del us[n]
                        else: us[n]=hashpw(os.environ.get("DEFAULT_PASSWORD","1234"))
                    storage.put("users",us)
                return s.send_json({"ok":True})
            if u.path=="/api/login":
                d=json.loads(s.body()); us=storage.get("users",{}) or {}; n=d.get("username","").strip()
                if n not in us or not checkpw(d.get("password",""),us[n]):
                    time.sleep(1); return s.send_json({"error":"帳號或密碼錯誤"},401)
                t=make_token(n)
                sec="; Secure" if s.headers.get("X-Forwarded-Proto")=="https" or any(x in s.headers.get("Host","") for x in ("trycloudflare","ngrok")) else ""
                b=b'{"ok":true}'; s.send_response(200); s.send_header("Content-Type","application/json")
                s.send_header("Set-Cookie",f"tp_session={t}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000{sec}"); s.send_header("Content-Length",len(b)); s.end_headers(); s.wfile.write(b); return
            if u.path=="/api/business":
                b=json.loads(s.body())
                with LOCK:
                    db=load()
                    if not b.get("id"):
                        if not is_admin(me): return s.send_json({"error":"僅管理員可新增店家"},403)
                        b["id"]="manual-"+uuid.uuid4().hex[:8]; b.setdefault("source","手動新增"); b.setdefault("status","未拜訪"); db["businesses"].append(b)
                    else:
                        o=next(x for x in db["businesses"] if x["id"]==b["id"]); o.update(b); b=o
                    save(db)
                return s.send_json(b)
            if u.path=="/api/visit":
                v=json.loads(s.body())
                with LOCK:
                    db=load(); bz=next(x for x in db["businesses"] if x["id"]==v["business_id"])
                    v["business_name"]=bz["name"]; v["district"]=bz["district"]
                    if v.get("id"): db["visits"]=[x for x in db["visits"] if x["id"]!=v["id"]]
                    else: v["id"]=uuid.uuid4().hex[:10]
                    me=s.user(); v["visitor"]=(str(v.get("visitor") or "").strip() or me) if is_admin(me) else me
                    v["updated"]=time.strftime("%Y-%m-%d %H:%M"); v["created_by"]=me; db["visits"].append(v)
                    if v.get("status"): bz["status"]=v["status"]
                    save(db)
                return s.send_json(v)
            if u.path=="/api/visit/delete":
                i=json.loads(s.body())["id"]
                with LOCK:
                    db=load(); x=next((x for x in db["visits"] if x["id"]==i),None)
                    if x and not is_admin(me) and x.get("created_by")!=me: return s.send_json({"error":"只能刪除自己登錄的紀錄"},403)
                    db["visits"]=[x for x in db["visits"] if x["id"]!=i]; st=None
                    if x:
                        bz=next((b for b in db["businesses"] if b["id"]==x.get("business_id")),None)
                        if bz:
                            rest=sorted([v for v in db["visits"] if v.get("business_id")==bz["id"]],key=lambda v:(str(v.get("date","")),str(v.get("updated",""))))
                            bz["status"]=st=(rest[-1].get("status") if rest else None) or "未拜訪"
                    save(db)
                return s.send_json({"ok":True,"business_status":st})
            if u.path=="/api/refresh":
                import fetch_osm
                new=fetch_osm.fetch()
                with LOCK:
                    db=load(); a,up=merge_businesses(db,new); db["meta"]["last_refresh"]=time.strftime("%Y-%m-%d %H:%M"); save(db)
                return s.send_json({"added":a,"updated":up,"total":len(db["businesses"])})
            if u.path=="/api/import.json":
                d=json.loads(s.body())
                with LOCK:
                    db=load(); a,_=merge_businesses(db,[b for b in d.get("businesses",[])])
                    ids={v["id"] for v in db["visits"]}; nv=[v for v in d.get("visits",[]) if v.get("id") not in ids]; db["visits"]+=nv; save(db)
                return s.send_json({"businesses_added":a,"visits_added":len(nv)})
            if u.path=="/api/import.xlsx":
                wb=openpyxl.load_workbook(io.BytesIO(s.body()),data_only=True); rb=rv=0
                with LOCK:
                    db=load(); bidx={b["id"]:b for b in db["businesses"]}
                    if "店家名單" in wb.sheetnames:
                        for r in read_sheet(wb["店家名單"],BH,BF):
                            for k in("lat","lng"):
                                try: r[k]=float(r[k])
                                except: r.pop(k,None)
                            if r.get("id") in bidx: bidx[r["id"]].update({k:v for k,v in r.items()}); rb+=1
                            elif r.get("name"):
                                r["id"]=r.get("id") or "manual-"+uuid.uuid4().hex[:8]; r.setdefault("status","未拜訪"); r.setdefault("source","Excel 匯入")
                                db["businesses"].append(r); bidx[r["id"]]=r; rb+=1
                    if "拜訪紀錄" in wb.sheetnames:
                        vidx={v["id"]:v for v in db["visits"]}
                        for r in read_sheet(wb["拜訪紀錄"],VH,VF):
                            if not r.get("business_id") or r["business_id"] not in bidx: continue
                            if r.get("id") in vidx: vidx[r["id"]].update(r)
                            else: r["id"]=r.get("id") or uuid.uuid4().hex[:10]; db["visits"].append(r)
                            rv+=1
                        for b in db["businesses"]:
                            vs=sorted([v for v in db["visits"] if v["business_id"]==b["id"]],key=lambda v:str(v.get("date","")))
                            if vs and vs[-1].get("status"): b["status"]=vs[-1]["status"]
                    save(db)
                return s.send_json({"businesses":rb,"visits":rv})
        except Exception as e:
            return s.send_json({"error":str(e)},500)
        s.send_json({"error":"not found"},404)
if __name__=="__main__":
    import sys
    if len(sys.argv)>2 and sys.argv[1]=="adduser":
        us=storage.get("users",{}) or {}; pw=sys.argv[3] if len(sys.argv)>3 else secrets.token_urlsafe(12)
        us[sys.argv[2]]=hashpw(pw); storage.put("users",us); print(sys.argv[2],pw,"(",storage.backend(),")"); sys.exit()
    if len(sys.argv)>2 and sys.argv[1]=="addusers":   # 一次新增多位同事，預設密碼 1234：python3 server.py addusers 小明 小華
        us=storage.get("users",{}) or {}; pw=os.environ.get("DEFAULT_PASSWORD","1234")
        for n in sys.argv[2:]: us[n]=hashpw(pw); print(n,pw)
        storage.put("users",us); print("(",storage.backend(),")"); sys.exit()
    if len(sys.argv)>1 and sys.argv[1]=="listusers":
        print("\n".join(storage.get("users",{}) or {})); sys.exit()
    if len(sys.argv)>1 and sys.argv[1]=="import-json":   # 把本機 data.json 上傳到雲端資料庫
        storage.put("db",json.load(open(sys.argv[2])))
        if len(sys.argv)>3: storage.put("users",json.load(open(sys.argv[3])))   # 可一併搬帳號：import-json data.json users.json
        print("imported to",storage.backend()); sys.exit()
    bootstrap_users()
    p=int(os.environ.get("PORT",8080)); print("http://0.0.0.0:%d"%p)
    ThreadingHTTPServer(("0.0.0.0",p),H).serve_forever()
