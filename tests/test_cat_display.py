import unittest
from cat_display import display_category, DISPLAY, FACTORY, FOOD
import fetch_osm, server

class TestCatDisplay(unittest.TestCase):
    def test_factory_and_food(self):
        for c in FACTORY:
            self.assertEqual(display_category(c),"工廠")
        for c in FOOD:
            self.assertEqual(display_category(c),"餐飲業")
        for c in ("食品零售","零售/店家","服務業","公司/辦公室","銀行",""):
            self.assertEqual(display_category(c),"其他")
        self.assertEqual(DISPLAY,("工廠","餐飲業","其他"))
    def test_export_includes_display_column(self):
        self.assertIn("category_display", server.BF)
        self.assertEqual(server.BF[server.BF.index("category")], "category")
        self.assertEqual(server.BF[server.BF.index("category")+1], "category_display")
        self.assertIn("顯示類別", server.BH)
        self.assertIn("餐飲業", server.PLC)

class TestFetchOsmTerritory(unittest.TestCase):
    def test_ten_districts_and_bbox(self):
        for d in ("仁德區","歸仁區","南區","安定區","安南區"):
            self.assertIn(d, fetch_osm.DISTS)
        s,w,n,e=map(float, fetch_osm.BBOX.split(","))
        # OSM relation extremes must sit inside the query box
        pts=[(22.8941,120.25),(22.97,120.327),(23.135,120.22),(22.912,120.18),(23.04,120.066)]
        for la,ln in pts:
            self.assertTrue(s<la<n and w<ln<e, (la,ln,fetch_osm.BBOX))
            self.assertTrue(server.in_tainan(la,ln))
    def test_closed_and_chain_filters(self):
        self.assertTrue(fetch_osm.is_closed({"shop":"vacant"}))
        self.assertTrue(fetch_osm.is_closed({"opening_hours":"closed"}))
        self.assertTrue(fetch_osm.is_closed({"disused:shop":"convenience"}))
        self.assertFalse(fetch_osm.is_closed({"shop":"bakery","name":"小麵包"}))
        self.assertTrue(fetch_osm._chain("星巴克民權店"))
        self.assertTrue(fetch_osm._chain("麥當勞仁德店"))
        self.assertFalse(fetch_osm._chain("阿婆碗粿"))
        self.assertTrue(fetch_osm._chain("85℃"))
        self.assertTrue(fetch_osm._chain("一沐日"))
        d=fetch_osm.dedupe_same_place([
            {"id":"n","name":"萬家福","phone":"06-1","district":"仁德區","address":"同址"},
            {"id":"w","name":"萬家福","phone":"06-1","district":"仁德區","address":"同址"},
            {"id":"o","name":"別家","phone":"06-1","district":"仁德區","address":"同址"},
        ])
        self.assertEqual([x["id"] for x in d],["n","o"])

if __name__=="__main__":
    unittest.main()
