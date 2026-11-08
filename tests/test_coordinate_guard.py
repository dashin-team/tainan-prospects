"""座標對齊與 OSM 更新保護。不連線、不寫資料庫。"""
import copy, unittest
import server

def biz(**kw):
    b={"id":"osm-node-1","name":"舊名","category":"餐飲","subtype":"cafe","district":"安平區",
       "address":"台南市安平區古堡街1號","phone":"06-1234567","website":"https://example.test",
       "note":"同事備註","lat":22.999,"lng":120.16,"status":"已聯絡","source":"OpenStreetMap node/1",
       "created_by":"仕翰","pl":"Y","employees":"8"}
    b.update(kw)
    return b

class CoordinateGuard(unittest.TestCase):
    def test_preserve_keeps_text_visits_and_google_pin(self):
        o=biz(geo_precision="google",geo_locked=True)
        visit={"id":"v1","business_id":o["id"],"interest_group":True,"interest_pl":False,"notes":"有興趣","created_by":"仕翰"}
        db={"businesses":[o],"visits":[visit],"meta":{}}
        new=biz(name="OSM新名",category="零售/店家",subtype="convenience",district="中西區",
                address="別的地址",phone="0900",website="https://osm",note="洗掉",
                lat=23.01,lng=120.2,source="OpenStreetMap node/9",employees="")
        added,updated=server.merge_businesses(db,[new],strict=True,preserve=True)
        self.assertEqual((added,updated),(0,0))
        self.assertEqual(o["name"],"舊名")
        self.assertEqual(o["category"],"餐飲")
        self.assertEqual(o["subtype"],"cafe")
        self.assertEqual(o["district"],"安平區")
        self.assertEqual(o["address"],"台南市安平區古堡街1號")
        self.assertEqual(o["phone"],"06-1234567")
        self.assertEqual(o["website"],"https://example.test")
        self.assertEqual(o["note"],"同事備註")
        self.assertEqual(o["lat"],22.999)
        self.assertEqual(o["lng"],120.16)
        self.assertEqual(o["source"],"OpenStreetMap node/1")
        self.assertEqual(o["created_by"],"仕翰")
        self.assertEqual(o["status"],"已聯絡")
        self.assertEqual(o["pl"],"Y")
        self.assertEqual(o["employees"],"8")
        self.assertEqual(db["visits"],[visit])

    def test_google_precision_alone_blocks_osm_move(self):
        o=biz(geo_precision="google")
        db={"businesses":[o],"visits":[],"meta":{}}
        added,updated=server.merge_businesses(db,[biz(lat=23.02,lng=120.21)],strict=True,preserve=True)
        self.assertEqual((added,updated),(0,0))
        self.assertEqual((o["lat"],o["lng"]),(22.999,120.16))

    def test_unlocked_pin_can_follow_osm_without_touching_text(self):
        o=biz(geo_precision="district")
        db={"businesses":[o],"visits":[{"id":"v","business_id":o["id"],"interest_pl":True}],"meta":{}}
        added,updated=server.merge_businesses(db,[biz(name="不該改",lat=23.001,lng=120.161)],strict=True,preserve=True)
        self.assertEqual((added,updated),(0,1))
        self.assertEqual((o["lat"],o["lng"]),(23.001,120.161))
        self.assertEqual(o["name"],"舊名")
        self.assertEqual(o["district"],"安平區")
        self.assertEqual(db["visits"][0]["interest_pl"],True)

    def test_fills_blank_contact_only(self):
        o=biz(phone="",website="",address="  ")
        db={"businesses":[o],"visits":[],"meta":{}}
        server.merge_businesses(db,[biz(phone="06-999",website="https://x",address="新地址",name="別的")],strict=True,preserve=True)
        self.assertEqual(o["phone"],"06-999")
        self.assertEqual(o["website"],"https://x")
        self.assertEqual(o["address"],"新地址")
        self.assertEqual(o["name"],"舊名")

    def test_cleared_phone_stays_cleared(self):
        o=biz(phone="",locked_fields=["phone"])
        db={"businesses":[o],"visits":[],"meta":{}}
        server.merge_businesses(db,[biz(phone="06-1")],strict=True,preserve=True)
        self.assertEqual(o["phone"],"")

    def test_refresh_does_not_delete_or_readd_blocked_or_phoneless(self):
        keep=biz(id="osm-node-9",name="留著")
        db={"businesses":[keep],"visits":[],"meta":{"deleted_ids":["osm-node-2"]}}
        added,updated=server.merge_businesses(db,[
            {"id":"osm-node-2","name":"已刪","phone":"06-1","lat":23,"lng":120.2,"category":"餐飲","district":"安平區"},
            {"id":"osm-node-3","name":"沒電話","phone":"  ","lat":23,"lng":120.2,"category":"餐飲","district":"安平區"},
            {"id":"osm-node-4","name":"有電話","phone":"06-2","lat":23,"lng":120.2,"category":"餐飲","district":"安平區","source":"OpenStreetMap node/4"},
        ],strict=True,preserve=True)
        self.assertEqual((added,updated),(1,0))
        self.assertEqual([b["id"] for b in db["businesses"]],["osm-node-9","osm-node-4"])
        self.assertEqual(db["businesses"][0]["name"],"留著")
        self.assertEqual(db["businesses"][1]["status"],"未拜訪")

    def test_same_values_are_not_counted_as_updated(self):
        o=biz()
        db={"businesses":[copy.deepcopy(o)],"visits":[],"meta":{}}
        self.assertEqual(server.merge_businesses(db,[o],strict=True,preserve=True),(0,0))

    def test_coordinate_update_is_coordinate_only(self):
        o=biz()
        other=biz(id="fac-1",name="安平工廠",category="工廠",source="工廠登記",phone="",
                  lat=23.0,lng=120.2,geo_precision="village",note="登記備註",owner="原負責人",products="醬油")
        visit={"id":"v","business_id":"osm-node-1","notes":"勿動","interest_group":True,"interest_pl":True,"created_by":"仕翰"}
        db={"businesses":[o,other],"visits":[visit]}
        res=server.apply_coordinates(db,[{
            "id":"osm-node-1","lat":22.9876543,"lng":120.1555555,
            "confidence":"high","confirm_same_place":True,
            "name":"被改名","phone":"000","note":"被改備註","address":"被改地址","owner":"別人"
        }])
        self.assertEqual(res["updated"],1)
        self.assertEqual(res["total"],2)
        self.assertEqual(o["name"],"舊名")
        self.assertEqual(o["phone"],"06-1234567")
        self.assertEqual(o["note"],"同事備註")
        self.assertEqual(o["address"],"台南市安平區古堡街1號")
        self.assertEqual(o["created_by"],"仕翰")
        self.assertEqual((o["lat"],o["lng"]),(22.987654,120.155556))
        self.assertEqual(o["geo_precision"],"google")
        self.assertTrue(o["geo_locked"])
        self.assertRegex(o["geo_updated"],r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
        self.assertEqual(other["name"],"安平工廠")
        self.assertEqual(other["owner"],"原負責人")
        self.assertEqual(other["products"],"醬油")
        self.assertEqual(db["visits"],[visit])
        self.assertEqual([b["id"] for b in db["businesses"]],["osm-node-1","fac-1"])

    def test_low_confidence_and_unknown_id_stay_untouched(self):
        o=biz()
        before=copy.deepcopy(o)
        db={"businesses":[o],"visits":[{"id":"v","notes":"x","interest_group":True}]}
        res=server.apply_coordinates(db,[
            {"id":"osm-node-1","lat":23.0,"lng":120.2,"confidence":"low","confirm_same_place":True,"name":"X"},
            {"id":"osm-node-1","lat":23.0,"lng":120.2,"confirm_same_place":True},
            {"id":"osm-node-1","lat":23.0,"lng":120.2,"confidence":"high","confirm_same_place":"true"},
            {"id":"nope","lat":23.0,"lng":120.2,"confidence":"high","confirm_same_place":True},
            {"id":"osm-node-1","lat":25,"lng":121,"confidence":"high","confirm_same_place":True},
            {"id":"osm-node-1","confidence":"high","confirm_same_place":True},
        ])
        self.assertEqual(res["updated"],0)
        self.assertEqual(o,before)
        self.assertEqual(len(db["businesses"]),1)
        self.assertEqual([s["reason"] for s in res["skipped"]],
                         ["not_high_confidence","not_high_confidence","not_high_confidence","not_found","out_of_bounds","bad_coord"])
        self.assertTrue(db["visits"][0]["interest_group"])

    def test_same_google_pin_is_not_rewritten(self):
        o=biz(lat=22.987654,lng=120.155556,geo_precision="google",geo_locked=True,geo_updated="2026-01-01 00:00")
        db={"businesses":[o],"visits":[]}
        res=server.apply_coordinates(db,[{"id":o["id"],"lat":22.987654,"lng":120.155556,"confidence":"high","confirm_same_place":True}])
        self.assertEqual(res["updated"],0)
        self.assertEqual(res["skipped"][0]["reason"],"unchanged")
        self.assertEqual(o["geo_updated"],"2026-01-01 00:00")
        self.assertEqual(o["name"],"舊名")

    def test_factory_low_confidence_does_not_move_approximate_pin(self):
        fac=biz(id="fac-9",name="安平工廠",category="工廠",source="工廠登記",phone="",
                geo_precision="road",lat=22.99,lng=120.15,note="登記備註",owner="原負責人")
        db={"businesses":[fac],"visits":[]}
        res=server.apply_coordinates(db,[{"id":"fac-9","lat":22.992,"lng":120.152,"confidence":"medium","confirm_same_place":True}])
        self.assertEqual(res["updated"],0)
        self.assertEqual((fac["lat"],fac["lng"]),(22.99,120.15))
        self.assertEqual(fac["geo_precision"],"road")
        self.assertEqual(fac["note"],"登記備註")
        res=server.apply_coordinates(db,[{"id":"fac-9","lat":22.992,"lng":120.152,"confidence":"high","confirm_same_place":True,"industry":"改產業","owner":"改負責人"}])
        self.assertEqual(res["updated"],1)
        self.assertEqual((fac["lat"],fac["lng"]),(22.992,120.152))
        self.assertEqual(fac["owner"],"原負責人")
        self.assertEqual(fac["note"],"登記備註")
        self.assertNotIn("industry",fac)
        self.assertEqual(fac["geo_precision"],"google")

    def test_edit_locks_text_and_only_moved_pin(self):
        o=biz(geo_precision="google",geo_locked=True)
        server.apply_business_edit(o,{"name":"夥伴改名","note":"新備註","phone":"","lat":22.999,"lng":120.16,
                                      "geo_locked":False,"geo_precision":"district","source":"被改來源"})
        self.assertEqual(o["name"],"夥伴改名")
        self.assertEqual(o["phone"],"")
        self.assertEqual(o["source"],"OpenStreetMap node/1")
        self.assertEqual(o["geo_precision"],"google")
        self.assertTrue(o["geo_locked"])
        self.assertIn("phone",o["locked_fields"])
        db={"businesses":[o],"visits":[],"meta":{}}
        server.merge_businesses(db,[biz(name="OSM",phone="06-000",note="OSM",lat=23.05,lng=120.3)],strict=True,preserve=True)
        self.assertEqual(o["name"],"夥伴改名")
        self.assertEqual(o["phone"],"")
        self.assertEqual(o["note"],"新備註")
        self.assertEqual((o["lat"],o["lng"]),(22.999,120.16))
        server.apply_business_edit(o,{"name":"夥伴改名","lat":22.981,"lng":120.15})
        self.assertEqual(o["geo_precision"],"manual")
        self.assertEqual(o["lat"],22.981)
        self.assertEqual(o["name"],"夥伴改名")
        server.merge_businesses(db,[biz(lat=23.08,lng=120.33,name="又要改")],strict=True,preserve=True)
        self.assertEqual(o["lat"],22.981)
        self.assertEqual(o["geo_precision"],"manual")

if __name__=="__main__":
    unittest.main()
