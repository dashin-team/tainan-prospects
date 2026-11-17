"""最後登入／最後上線：成功登入才記錄、活動節流、僅管理員可查。不碰店家與拜訪資料。"""
import json, os, tempfile, threading, time, unittest
from datetime import datetime, timezone, timedelta
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import storage, server

TPE = timezone(timedelta(hours=8))

def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat()

class _Quiet(server.H):
    def log_message(self, *a): pass

class ActivityHelpers(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.mkdtemp()
        self._D=storage.D; self._URL=storage.URL; self._cache=dict(storage._cache)
        self._touch=dict(server._last_touch)
        storage.D=self.tmp; storage.URL=""; storage._cache.clear(); server._last_touch.clear()
        storage.put("users",{n:"x" for n in ("南恩","仕翰","夥伴")})
        storage.put("admins",["南恩"])

    def tearDown(self):
        storage.D=self._D; storage.URL=self._URL
        storage._cache.clear(); storage._cache.update(self._cache)
        server._last_touch.clear(); server._last_touch.update(self._touch)

    def test_iso_tpe_converts_utc(self):
        # 2026-11-17 09:52 UTC = 17:52 台北
        dt=datetime(2026,11,17,9,52,tzinfo=timezone.utc)
        self.assertEqual(server.iso_tpe(dt), "2026-11-17T17:52:00+08:00")
        self.assertEqual(server.iso_tpe(_iso(dt)), "2026-11-17T17:52:00+08:00")

    def test_record_login_sets_both_and_activity_sorts(self):
        now=datetime(2026,11,17,9,52,tzinfo=timezone.utc)
        earlier=now-timedelta(days=3)
        server.record_login("仕翰", at=earlier)
        server.record_login("南恩", at=now)
        r=server.users_activity()
        names=[u["name"] for u in r["users"]]
        self.assertEqual(names[0], "南恩")
        self.assertEqual(names[1], "仕翰")
        self.assertEqual(names[2], "夥伴")   # 從未登入排最後
        nan=r["users"][0]
        self.assertTrue(nan["is_admin"])
        self.assertEqual(nan["last_login"], "2026-11-17T17:52:00+08:00")
        self.assertEqual(nan["last_active"], "2026-11-17T17:52:00+08:00")
        never=next(u for u in r["users"] if u["name"]=="夥伴")
        self.assertIsNone(never["last_login"])
        self.assertIsNone(never["last_active"])
        self.assertFalse(never["is_admin"])

    def test_touch_active_throttled(self):
        t0=datetime(2026,11,17,1,0,tzinfo=timezone.utc)
        server.record_login("仕翰", at=t0)
        self.assertFalse(server.touch_active("仕翰", at=t0+timedelta(minutes=4), throttle=300))
        seen=storage.get("last_seen")
        self.assertEqual(seen["仕翰"]["last_active"], _iso(t0))
        self.assertTrue(server.touch_active("仕翰", at=t0+timedelta(minutes=6), throttle=300))
        seen=storage.get("last_seen")
        self.assertEqual(server.parse_ts(seen["仕翰"]["last_active"]), t0+timedelta(minutes=6))
        self.assertEqual(server.parse_ts(seen["仕翰"]["last_login"]), t0)  # 登入時間不變

    def test_does_not_touch_business_or_visit_files(self):
        db={"businesses":[{"id":"x","name":"店","note":"勿動"}],"visits":[{"id":"v","notes":"也不動"}],"meta":{}}
        dbp=os.path.join(self.tmp,"data.json"); open(dbp,"w").write(json.dumps(db,ensure_ascii=False))
        users={"仕翰":"hash"}; open(os.path.join(self.tmp,"users.json"),"w").write(json.dumps(users,ensure_ascii=False))
        storage._cache.clear()
        now=datetime(2026,11,17,1,0,tzinfo=timezone.utc)
        server.record_login("仕翰", at=now)
        server.touch_active("仕翰", at=now+timedelta(minutes=10))
        server.users_activity()
        self.assertEqual(json.loads(open(dbp).read()), db)
        self.assertEqual(json.loads(open(os.path.join(self.tmp,"users.json")).read()), users)


class ActivityAPI(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.mkdtemp()
        self._D=storage.D; self._URL=storage.URL; self._cache=dict(storage._cache)
        self._SECRET=server.SECRET; self._touch=dict(server._last_touch)
        storage.D=self.tmp; storage.URL=""; storage._cache.clear(); server.SECRET=None; server._last_touch.clear()
        storage.put("users",{n:server.hashpw("1234") for n in ("仕翰","南恩","夥伴")})
        storage.put("admins",["南恩"])
        self.httpd=ThreadingHTTPServer(("127.0.0.1",0),_Quiet)
        threading.Thread(target=self.httpd.serve_forever,daemon=True).start()
        self.base="http://127.0.0.1:%d"%self.httpd.server_address[1]

    def tearDown(self):
        self.httpd.shutdown(); self.httpd.server_close()
        storage.D=self._D; storage.URL=self._URL
        storage._cache.clear(); storage._cache.update(self._cache)
        server.SECRET=self._SECRET
        server._last_touch.clear(); server._last_touch.update(self._touch)

    def req(self,path,body=None,ck=None,method=None):
        h={"Content-Type":"application/json"}
        if ck: h["Cookie"]=ck
        if method is None: method="POST" if body is not None else "GET"
        r=Request(self.base+path,data=None if body is None else json.dumps(body).encode(),headers=h,method=method)
        try:
            with urlopen(r,timeout=8) as x: return x.status,json.loads(x.read() or b"{}"),x.headers.get("Set-Cookie") or ""
        except HTTPError as e: return e.code,json.loads(e.read() or b"{}"),""

    def login(self,n,pw="1234"):
        c,j,ck=self.req("/api/login",{"username":n,"password":pw}); self.assertEqual(c,200)
        return ck.split(";")[0]

    def test_login_records_and_failed_login_does_not(self):
        before=time.time()
        self.login("南恩")
        after=time.time()
        seen=storage.get("last_seen") or {}
        rec=seen["南恩"]
        for key in ("last_login","last_active"):
            dt=server.parse_ts(rec[key])
            self.assertIsNotNone(dt)
            self.assertGreaterEqual(dt.timestamp(), before-1)
            self.assertLessEqual(dt.timestamp(), after+2)
        self.assertNotIn("夥伴", seen)
        c,j,_=self.req("/api/login",{"username":"夥伴","password":"wrong"})
        self.assertEqual(c,401)
        seen=storage.get("last_seen") or {}
        self.assertNotIn("夥伴", seen)

    def test_activity_admin_only_and_lists_all_accounts(self):
        partner=self.login("夥伴")
        self.assertEqual(self.req("/api/users/activity",ck=partner)[0],403)
        self.assertEqual(self.req("/api/users/activity")[0],401)
        admin=self.login("南恩")
        c,j,_=self.req("/api/users/activity",ck=admin)
        self.assertEqual(c,200)
        names=[u["name"] for u in j["users"]]
        self.assertEqual(set(names), {"仕翰","南恩","夥伴"})
        # 南恩、夥伴剛登入，應排在沒登入的仕翰前面；時間為台北時區
        shihan=next(u for u in j["users"] if u["name"]=="仕翰")
        self.assertIsNone(shihan["last_login"])
        self.assertIsNone(shihan["last_active"])
        nan=next(u for u in j["users"] if u["name"]=="南恩")
        self.assertTrue(nan["is_admin"])
        self.assertTrue(nan["last_login"].endswith("+08:00"))
        self.assertTrue(nan["last_active"].endswith("+08:00"))
        self.assertEqual(names[-1], "仕翰")

    def test_cookie_request_updates_last_active_after_throttle(self):
        ck=self.login("夥伴")
        rec=storage.get("last_seen")["夥伴"]
        login_ts=server.parse_ts(rec["last_login"])
        # 5 分鐘內再打 API，最後上線不應改
        self.assertEqual(self.req("/api/me",ck=ck)[0],200)
        rec2=storage.get("last_seen")["夥伴"]
        self.assertEqual(rec2["last_active"], rec["last_active"])
        self.assertEqual(rec2["last_login"], rec["last_login"])
        # 模擬 6 分鐘前的上線，下一次 API 應更新上線、保留登入時間
        old=login_ts-timedelta(minutes=6)
        d=storage.get("last_seen"); d["夥伴"]["last_active"]=server.iso_utc(old); storage.put("last_seen",d)
        server._last_touch.pop("夥伴", None)
        self.assertEqual(self.req("/api/me",ck=ck)[0],200)
        rec3=storage.get("last_seen")["夥伴"]
        self.assertEqual(server.parse_ts(rec3["last_login"]), login_ts)
        self.assertGreater(server.parse_ts(rec3["last_active"]), login_ts)
        self.assertGreater(server.parse_ts(rec3["last_active"]), old)

if __name__=="__main__":
    unittest.main()
