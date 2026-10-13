"""從 OpenStreetMap Overpass 抓取台南七區店家/工廠，輸出 businesses 清單。"""
import json, urllib.request, urllib.parse
SERVERS=["https://overpass.openstreetmap.fr/api/interpreter","https://overpass-api.de/api/interpreter","https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
BBOX="22.93,120.05,23.13,120.34"
DISTS="南區|北區|東區|中西區|安南區|永康區|安定區"
Q_POI=f'[out:json][timeout:170][bbox:{BBOX}];(nwr["name"][~"^(shop|craft|industrial|amenity|office)$"~"."];nwr["name"]["man_made"="works"];nwr["name"]["landuse"="industrial"];nwr["name"]["building"~"^(industrial|factory|warehouse)$"];);out center tags;'
Q_BND=f'[out:json][timeout:120][bbox:{BBOX}];rel["boundary"="administrative"]["admin_level"="7"]["name"~"^({DISTS})$"];out geom;'
FOOD_AMEN={"restaurant","cafe","fast_food","bar","pub","food_court","ice_cream","biergarten"}
SVC_AMEN={"clinic","dentist","doctors","pharmacy","veterinary","car_wash","fuel","kindergarten","childcare","bank","marketplace","nursing_home","car_rental"}
FOOD_SHOP={"bakery","confectionery","butcher","seafood","deli","beverages","tea","coffee","pastry","greengrocer","dairy","alcohol","frozen_food","food","cheese","chocolate","spices","farm","rice","noodle","health_food","supermarket","convenience"}
def overpass(q):
    err=None
    for s in SERVERS:
        try:
            req=urllib.request.Request(s,data=urllib.parse.urlencode({"data":q}).encode(),headers={"User-Agent":"tainan-prospects/1.0"})
            d=json.load(urllib.request.urlopen(req,timeout=200))
            if d.get("elements"): return d
            err=d.get("remark")
        except Exception as e: err=e
    raise RuntimeError(f"Overpass 失敗: {err}")
def category(t):
    a=t.get("amenity");s=t.get("shop");c=t.get("craft");i=t.get("industrial");o=t.get("office")
    nm=t.get("name","")
    if i or t.get("landuse")=="industrial" or t.get("man_made")=="works" or t.get("building") in("industrial","factory","warehouse"):
        return "食品製造" if any(k in nm for k in("食品","飲料","醬","烘焙","製麵","乳品","茶")) or i in("food","brewery") else "工廠/製造"
    if c: return "食品製造" if c in("bakery","brewery","confectionery","winery","distillery","caterer") else "工廠/製造"
    if a in FOOD_AMEN: return "餐飲"
    if s in FOOD_SHOP: return "食品零售"
    if s: return "零售/店家"
    if a in SVC_AMEN: return "服務業"
    if o in ("company","it","estate_agent","insurance","accountant","lawyer","logistics","construction_company","architect","employment_agency","telecommunication","advertising_agency","financial") or (o and o not in("government","political_party","religion","ngo","association")): return "公司/辦公室"
    return None
def segs(rel):
    out=[]
    for m in rel["members"]:
        if m["type"]=="way" and m.get("role") in("outer","inner","") and "geometry" in m:
            g=m["geometry"]
            out+= [(g[k]["lon"],g[k]["lat"],g[k+1]["lon"],g[k+1]["lat"]) for k in range(len(g)-1)]
    return out
def inside(x,y,S):
    c=False
    for x1,y1,x2,y2 in S:
        if (y1>y)!=(y2>y) and x < x1+(y-y1)*(x2-x1)/(y2-y1): c=not c
    return c
def addr(t):
    if t.get("addr:full"): return t["addr:full"]
    p=[t.get(k,"") for k in("addr:city","addr:district","addr:street")]
    hn=t.get("addr:housenumber","")
    s="".join(p)+(hn+("" if hn.endswith("號") else "號") if hn else "")
    return s
def fetch():
    bnd={r["tags"]["name"]:segs(r) for r in overpass(Q_BND)["elements"]}
    res=[]
    for e in overpass(Q_POI)["elements"]:
        t=e.get("tags",{}); cat=category(t)
        if not cat: continue
        lat=e.get("lat") or e.get("center",{}).get("lat"); lon=e.get("lon") or e.get("center",{}).get("lon")
        if lat is None: continue
        d=next((n for n,S in bnd.items() if inside(lon,lat,S)),None)
        if not d: continue
        sub=t.get("shop") or t.get("amenity") or t.get("craft") or t.get("industrial") or t.get("office") or t.get("man_made") or t.get("landuse") or t.get("building") or ""
        res.append({"id":f"osm-{e['type']}-{e['id']}","name":t["name"],"category":cat,"subtype":sub,"district":d,
          "address":addr(t),"phone":t.get("phone") or t.get("contact:phone") or "","website":t.get("website") or t.get("contact:website") or "",
          "lat":round(lat,6),"lng":round(lon,6),"source":f"OpenStreetMap {e['type']}/{e['id']}"})
    from exclude import excluded
    return [b for b in res if not excluded(b)]
if __name__=="__main__":
    r=fetch(); print(len(r))
