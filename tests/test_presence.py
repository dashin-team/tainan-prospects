"""即時位置分享：獨立儲存、過期視為離開、需登入。不碰店家與拜訪資料。"""
import json, os, tempfile, threading, time, unittest
from datetime import datetime, timezone, timedelta
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import storage, server

def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat()

class PresenceStore(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.mkdtemp()
        self._D=storage.D; self._URL=storage.URL; self._cache=dict(storage._cache)
        storage.D=self.tmp; storage.URL=""; storage._cache.clear()
        self._db=os.path.join(self.tmp,"data.json")
        self._users=os.path.join(self.tmp,"users.json")

    def tearDown(self):
        storage.D=self._D; storage.URL=self._URL
        storage._cache.clear(); storage._cache.update(self._cache)

    def test_upsert_overwrites_one_row_and_lists_fresh(self):
        now=datetime(2026,11,11,6,0,tzinfo=timezone.utc)
        storage.upsert_presence("小明", 23.001234, 120.201234, 15, at=now)
        storage.upsert_presence("小明", 23.01, 120.22, 8, at=now)
        storage.upsert_presence("小華", 22.99, 120.16, None, at=now)
        rows=storage.list_presence(now=now, ttl=600, purge=True)
        self.assertEqual([r["user"] for r in rows], ["小明","小華"])
        ming=next(r for r in rows if r["user"]=="小明")
        self.assertEqual((ming["lat"], ming["lng"], ming["accuracy"]), (23.01, 120.22, 8.0))
        # 同一人只有一筆，檔案也只有這兩位
        data=json.loads(open(os.path.join(self.tmp,"presence.json")).read())
        self.assertEqual(set(data), {"小明","小華"})

    def test_stale_filtered_and_purged(self):
        now=datetime(2026,11,11,6,0,tzinfo=timezone.utc)
        storage.upsert_presence("新鮮", 23.0, 120.2, 10, at=now-timedelta(minutes=4))
        storage.upsert_presence("過期", 23.1, 120.3, 10, at=now-timedelta(minutes=11))
        rows=storage.list_presence(now=now, ttl=600, purge=True)
        self.assertEqual([r["user"] for r in rows], ["新鮮"])
        data=json.loads(open(os.path.join(self.tmp,"presence.json")).read())
        self.assertEqual(set(data), {"新鮮"})
        self.assertNotIn("過期", [r["user"] for r in rows])

    def test_delete_removes_only_that_user(self):
        now=datetime(2026,11,11,6,0,tzinfo=timezone.utc)
        storage.upsert_presence("小明", 23.0, 120.2, 1, at=now)
        storage.upsert_presence("小華", 22.9, 120.1, 1, at=now)
        storage.delete_presence("小明")
        rows=storage.list_presence(now=now, ttl=600)
        self.assertEqual([r["user"] for r in rows], ["小華"])
        storage.delete_presence("不存在的人")  # 不應報錯

    def test_does_not_touch_business_or_visit_files(self):
        db={"businesses":[{"id":"x","name":"店","note":"勿動"}],"visits":[{"id":"v","notes":"也不動"}],"meta":{}}
        open(self._db,"w").write(json.dumps(db,ensure_ascii=False))
        users={"仕翰":"hash"}; open(self._users,"w").write(json.dumps(users))
        now=datetime(2026,11,11,6,0,tzinfo=timezone.utc)
        storage.upsert_presence("仕翰", 23.0, 120.2, 5, at=now)
        storage.list_presence(now=now)
        storage.delete_presence("仕翰")
        self.assertEqual(json.loads(open(self._db).read()), db)
        self.assertEqual(json.loads(open(self._users).read()), users)
        self.assertFalse(os.path.exists(os.path.join(self.tmp,"data.json.tmp")))

class PresenceLogic(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.mkdtemp()
        self._D=storage.D; self._URL=storage.URL; self._cache=dict(storage._cache)
        storage.D=self.tmp; storage.URL=""; storage._cache.clear()

    def tearDown(self):
        storage.D=self._D; storage.URL=self._URL
        storage._cache.clear(); storage._cache.update(self._cache)

    def test_stop_flag_deletes(self):
        storage.upsert_presence("夥伴", 23.0, 120.2, 1, at=datetime.now(timezone.utc))
        res=server.presence_update("夥伴", {"stop":True,"lat":23,"lng":120})
        self.assertTrue(res["stopped"])
        self.assertEqual(storage.list_presence(), [])

    def test_bad_coords_rejected(self):
        for body in ({}, {"lat":"x","lng":120}, {"lat":23}, {"lat":999,"lng":120}, {"lat":23,"lng":999}):
            with self.assertRaises(ValueError):
                server.presence_update("夥伴", body)
        self.assertEqual(storage.list_presence(), [])

class _Quiet(server.H):
    def log_message(self, *a): pass

class PresenceHTTP(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.mkdtemp()
        self._D=storage.D; self._URL=storage.URL; self._cache=dict(storage._cache)
        self._SECRET=server.SECRET
        storage.D=self.tmp; storage.URL=""; storage._cache.clear()
        server.SECRET=None
        storage.put("users", {"夥伴": server.hashpw("pw12")})
        self.httpd=ThreadingHTTPServer(("127.0.0.1",0), _Quiet)
        self.t=threading.Thread(target=self.httpd.serve_forever, daemon=True); self.t.start()
        self.base="http://127.0.0.1:%d"%self.httpd.server_address[1]

    def tearDown(self):
        self.httpd.shutdown(); self.httpd.server_close()
        storage.D=self._D; storage.URL=self._URL
        storage._cache.clear(); storage._cache.update(self._cache)
        server.SECRET=self._SECRET

    def _req(self, method, path, body=None, cookie=None, expect=None):
        data=None if body is None else (body if isinstance(body,(bytes,bytearray)) else json.dumps(body).encode())
        headers={}
        if data is not None: headers["Content-Type"]="application/json"
        if cookie: headers["Cookie"]=cookie
        req=Request(self.base+path, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=8) as r:
                raw=r.read(); code=r.status
        except HTTPError as e:
            raw=e.read(); code=e.code
        if expect is not None:
            self.assertEqual(code, expect, raw[:300])
        try: return code, json.loads(raw.decode())
        except Exception: return code, raw

    def _login(self):
        code, j, = None, None
        req=Request(self.base+"/api/login", data=json.dumps({"username":"夥伴","password":"pw12"}).encode(),
                    headers={"Content-Type":"application/json"}, method="POST")
        with urlopen(req, timeout=8) as r:
            self.assertEqual(r.status, 200)
            cookie=r.headers.get("Set-Cookie") or ""
            # extract tp_session
            part=next((p.strip() for p in cookie.split(",") for p in p.split(";") if p.strip().startswith("tp_session=")), "")
            self.assertTrue(part, "missing session cookie")
            return part

    def test_auth_required_for_get_post_delete(self):
        for method, path, body in (("GET","/api/presence",None),("POST","/api/presence",{"lat":23.0,"lng":120.2}),("DELETE","/api/presence",None)):
            code,j=self._req(method,path,body)
            self.assertEqual(code, 401, (method,j))
            self.assertEqual(j.get("error"), "請先登入")

    def test_post_list_delete_and_stale(self):
        ck=self._login()
        code,j=self._req("POST","/api/presence",{"lat":23.0123456,"lng":120.2011111,"accuracy":12},cookie=ck,expect=200)
        self.assertTrue(j.get("ok"))
        code,j=self._req("GET","/api/presence",cookie=ck,expect=200)
        self.assertEqual(len(j["presence"]), 1)
        row=j["presence"][0]
        self.assertEqual(row["user"], "夥伴")
        self.assertEqual((row["lat"], row["lng"]), (23.012346, 120.201111))
        # 手動把這筆改成過期再 GET，應被過濾
        storage.upsert_presence("夥伴", 23.0, 120.2, 1, at=datetime.now(timezone.utc)-timedelta(minutes=15))
        code,j=self._req("GET","/api/presence",cookie=ck,expect=200)
        self.assertEqual(j["presence"], [])
        # 再寫入後 DELETE
        self._req("POST","/api/presence",{"lat":23.0,"lng":120.2},cookie=ck,expect=200)
        self._req("DELETE","/api/presence",cookie=ck,expect=200)
        code,j=self._req("GET","/api/presence",cookie=ck,expect=200)
        self.assertEqual(j["presence"], [])
        # sendBeacon 風格：POST {stop:true}
        self._req("POST","/api/presence",{"lat":23.0,"lng":120.2},cookie=ck,expect=200)
        code,j=self._req("POST","/api/presence",{"stop":True},cookie=ck,expect=200)
        self.assertTrue(j.get("stopped"))
        code,j=self._req("GET","/api/presence",cookie=ck,expect=200)
        self.assertEqual(j["presence"], [])

    def test_presence_write_does_not_change_businesses(self):
        ck=self._login()
        db={"businesses":[{"id":"keep","name":"原店","note":"原備註"}],"visits":[{"id":"v1","business_id":"keep","notes":"原紀錄"}],"meta":{"last_refresh":"x"}}
        storage.put("db", db)
        self._req("POST","/api/presence",{"lat":23.0,"lng":120.2,"accuracy":9},cookie=ck,expect=200)
        self._req("DELETE","/api/presence",cookie=ck,expect=200)
        got=storage.get("db")
        self.assertEqual(got, db)

if __name__=="__main__":
    unittest.main()
