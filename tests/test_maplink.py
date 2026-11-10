"""Google 地圖連結與座標文字解析。不連線。"""
import unittest
import maplink

PIN="https://www.google.com/maps/place/Anping/@23.010000,120.200000,17z/data=!3m1!4b1!4m6!3m5!1s0x0!8m2!3d22.999111!4d120.161222"

class Parse(unittest.TestCase):
    def test_place_pin_wins_over_map_center(self):
        self.assertEqual(maplink.extract_point(PIN),(22.999111,120.161222))

    def test_at_query_ll_and_raw_text(self):
        self.assertEqual(maplink.extract_point("https://www.google.com/maps/@22.99321,120.16543,17z"),(22.99321,120.16543))
        self.assertEqual(maplink.extract_point("https://www.google.com/maps/search/?api=1&query=22.98,120.15"),(22.98,120.15))
        self.assertEqual(maplink.extract_point("https://maps.google.com/?q=22.97,120.14"),(22.97,120.14))
        self.assertEqual(maplink.extract_point("https://www.google.com/maps?ll=22.96,120.13&z=16"),(22.96,120.13))
        self.assertEqual(maplink.extract_point("https://maps.google.com/?q=loc:22.95,120.12"),(22.95,120.12))
        self.assertEqual(maplink.extract_point("22.94, 120.11"),(22.94,120.11))
        self.assertEqual(maplink.extract_point("22.93，120.10"),(22.93,120.10))

    def test_place_name_is_not_a_coordinate(self):
        with self.assertRaises(ValueError):
            maplink.extract_point("https://www.google.com/maps/search/?api=1&query=安平老街")

    def test_short_link_follows_redirect_then_stops(self):
        seen=[]
        def fetch(url, timeout):
            seen.append((url, timeout))
            if "maps.app.goo.gl" in url:
                return 302, "https://www.google.com/maps/@22.999,120.16,17z", b""
            raise AssertionError(url)
        self.assertEqual(maplink.extract_point("https://maps.app.goo.gl/abc", timeout=3, fetch=fetch),(22.999,120.16))
        self.assertEqual(seen,[("https://maps.app.goo.gl/abc",3)])

    def test_goo_gl_meta_refresh(self):
        html=b'<html><meta http-equiv="refresh" content="0;url=https://www.google.com/maps/@22.991,120.162,16z"></html>'
        def fetch(url, timeout):
            return 200, None, html
        self.assertEqual(maplink.extract_point("https://goo.gl/maps/abc", fetch=fetch),(22.991,120.162))

    def test_redirect_off_google_is_not_fetched(self):
        seen=[]
        def fetch(url, timeout):
            seen.append(url)
            return 302, "https://169.254.169.254/latest/meta-data", b""
        with self.assertRaises(ValueError):
            maplink.extract_point("https://maps.app.goo.gl/evil", fetch=fetch)
        self.assertEqual(seen,["https://maps.app.goo.gl/evil"])

    def test_rejects_non_https_and_other_hosts(self):
        with self.assertRaises(ValueError):
            maplink.extract_point("http://maps.app.goo.gl/abc", fetch=lambda *a: (_ for _ in ()).throw(AssertionError("fetched")))
        with self.assertRaises(ValueError):
            maplink.extract_point("https://example.com/@22.99,120.16")

if __name__=="__main__":
    unittest.main()
