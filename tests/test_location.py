"""同事修正位置：只改座標欄，並保留每週 OSM 鎖定。不連線、不寫資料庫。"""
import copy, unittest
import server

def biz():
    return {"id":"osm-node-1","name":"舊名","category":"餐飲","subtype":"cafe","district":"安平區",
            "address":"台南市安平區古堡街1號","phone":"06-1234567","website":"https://example.test",
            "note":"同事備註","lat":22.999,"lng":120.16,"status":"已聯絡","source":"OpenStreetMap node/1",
            "created_by":"仕翰","pl":"Y","employees":"8","owner":"原負責人"}

def db_of(o):
    return {"businesses":[o],"visits":[{"id":"v","business_id":o["id"],"notes":"勿動","interest_group":True,"interest_pl":True,"created_by":"仕翰"}],"meta":{}}

class TeamLocation(unittest.TestCase):
    def test_endpoint_write_is_coordinate_only_and_locked(self):
        o=biz(); db=db_of(o); before=copy.deepcopy(db)
        res=server.apply_team_location(db,"osm-node-1","夥伴",{
            "lat":22.987654,"lng":120.155555,"name":"被改名","category":"工廠","address":"別處",
            "phone":"000","note":"洗掉","visits":[],"interest_group":False,"owner":"別人"})
        self.assertTrue(res["geo_locked"])
        self.assertEqual(res["geo_precision"],"manual")
        self.assertEqual(res["geo_updated_by"],"夥伴")
        self.assertEqual((o["lat"],o["lng"]),(22.987654,120.155555))
        for k in ("name","category","subtype","district","address","phone","website","note","status","source","created_by","pl","employees","owner"):
            self.assertEqual(o[k], before["businesses"][0][k])
        self.assertEqual(db["visits"], before["visits"])
        self.assertEqual(len(db["location_history"]),1)
        self.assertEqual(db["location_history"][0]["old"]["lat"],22.999)
        self.assertEqual(db["location_history"][0]["new"]["lng"],120.155555)
        osm=biz(); osm["lat"]=23.05; osm["lng"]=120.3; osm["name"]="OSM"
        added,updated=server.merge_businesses(db,[osm],strict=True,preserve=True)
        self.assertEqual((added,updated),(0,0))
        self.assertEqual((o["lat"],o["lng"]),(22.987654,120.155555))
        self.assertEqual(o["name"],"舊名")

    def test_preview_and_rejected_values_do_not_write(self):
        o=biz(); db=db_of(o); snap=copy.deepcopy(o)
        res=server.apply_team_location(db,"osm-node-1","夥伴",{"input":"22.981, 120.151","preview":True,"name":"不該寫"})
        self.assertTrue(res["preview"])
        self.assertEqual((res["lat"],res["lng"]),(22.981,120.151))
        self.assertEqual(o, snap)
        self.assertNotIn("location_history", db)
        for body in ({"lat":25,"lng":121,"note":"x"},{"input":"https://www.google.com/maps/search/?api=1&query=安平老街"},{"lat":"","lng":""}):
            with self.assertRaises(ValueError):
                server.apply_team_location(db,"osm-node-1","夥伴",body)
            self.assertEqual(o, snap)

    def test_short_link_preview_uses_injected_fetch(self):
        o=biz(); db=db_of(o)
        def fetch(url, timeout):
            self.assertLessEqual(timeout, 8)
            return 302, "https://www.google.com/maps/@22.992,120.158,17z", b""
        res=server.apply_team_location(db,"osm-node-1","夥伴",{"input":"https://goo.gl/maps/abc","preview":True}, fetch=fetch)
        self.assertEqual((res["lat"],res["lng"]),(22.992,120.158))
        self.assertEqual(o["name"],"舊名")
        self.assertEqual(o["lat"],22.999)

    def test_admin_revert_restores_only_coordinates(self):
        o=biz(); db=db_of(o)
        server.apply_team_location(db,"osm-node-1","夥伴",{"lat":22.981,"lng":120.151,"note":"不要"})
        o["note"]="同事後來補的備註"; o["phone"]="06-999"
        res=server.revert_team_location(db,"osm-node-1","仕翰")
        self.assertEqual((res["lat"],res["lng"]),(22.999,120.16))
        self.assertEqual(o["note"],"同事後來補的備註")
        self.assertEqual(o["phone"],"06-999")
        self.assertEqual(o["name"],"舊名")
        self.assertEqual(db["visits"][0]["interest_group"], True)
        self.assertFalse(o.get("geo_locked"))
        with self.assertRaises(LookupError):
            server.revert_team_location({"businesses":[biz()],"location_history":[]},"osm-node-1","仕翰")

if __name__=="__main__":
    unittest.main()
