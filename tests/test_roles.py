"""管理員名單存資料庫：可轉移、至少保留一位、不受預設 ADMINS 影響。"""
import json, tempfile, threading, unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import storage, server

class _Quiet(server.H):
    def log_message(self, *a): pass

class Roles(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.mkdtemp()
        self._D=storage.D; self._URL=storage.URL; self._cache=dict(storage._cache); self._SECRET=server.SECRET
        storage.D=self.tmp; storage.URL=""; storage._cache.clear(); server.SECRET=None
        storage.put("users",{n:server.hashpw("1234") for n in ("仕翰","shihhan","南恩","夥伴")})
        self.httpd=ThreadingHTTPServer(("127.0.0.1",0),_Quiet)
        threading.Thread(target=self.httpd.serve_forever,daemon=True).start()
        self.base="http://127.0.0.1:%d"%self.httpd.server_address[1]
    def tearDown(self):
        self.httpd.shutdown(); self.httpd.server_close()
        storage.D=self._D; storage.URL=self._URL; storage._cache.clear(); storage._cache.update(self._cache); server.SECRET=self._SECRET
    def req(self,path,body=None,ck=None):
        h={"Content-Type":"application/json"}
        if ck: h["Cookie"]=ck
        r=Request(self.base+path,data=None if body is None else json.dumps(body).encode(),headers=h,method="POST" if body is not None else "GET")
        try:
            with urlopen(r,timeout=8) as x: return x.status,json.loads(x.read() or b"{}"),x.headers.get("Set-Cookie") or ""
        except HTTPError as e: return e.code,json.loads(e.read() or b"{}"),""
    def login(self,n):
        c,j,ck=self.req("/api/login",{"username":n,"password":"1234"}); self.assertEqual(c,200)
        return ck.split(";")[0]
    def test_transfer_admin_and_keep_one(self):
        s=self.login("仕翰")
        self.assertTrue(self.req("/api/me",ck=s)[1]["is_admin"])   # 預設名單
        self.assertEqual(self.req("/api/users/role",{"username":"南恩","admin":True},s)[0],200)
        n=self.login("南恩")
        self.assertTrue(self.req("/api/me",ck=n)[1]["is_admin"])
        for u in ("仕翰","shihhan"):
            self.assertEqual(self.req("/api/users/role",{"username":u,"admin":False},n)[0],200)
        self.assertFalse(self.req("/api/me",ck=s)[1]["is_admin"])
        self.assertEqual(self.req("/api/users",ck=s)[0],403)
        self.assertEqual(self.req("/api/users/role",{"username":"仕翰","admin":True},s)[0],403)
        self.assertEqual(self.req("/api/users/role",{"username":"南恩","admin":False},n)[0],400)   # 不能變成零管理員
        self.assertEqual(storage.get("admins"),["南恩"])
        storage._cache.clear()   # 模擬重啟：仍由資料庫決定
        self.assertEqual(server.admins(),{"南恩"})
        self.assertEqual(self.req("/api/users/role",{"username":"不存在","admin":True},n)[0],404)

if __name__=="__main__": unittest.main()
