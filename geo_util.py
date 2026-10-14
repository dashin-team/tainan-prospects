"""Nominatim 路段/里/行政區地理編碼（快取在 factory/cache.json）。"""
import json,re,time,os,urllib.request,urllib.parse
D=os.path.dirname(os.path.abspath(__file__)); C=os.path.join(D,'factory','cache.json')
UA={'User-Agent':'tainan-prospects/1.0 (hank87327@kimo.com)'}
def road(a,d):
    a=a.split(d,1)[-1]; a=re.sub(r'^.*?里','',a); a=re.sub(r'^\d+鄰','',a)
    m=re.match(r'(.+?(?:路|街|大道)(?:[一二三四五六七八九十\d]+段)?)',a); return m.group(1) if m else None
def village(a,d):
    m=re.search(d+r'(.{1,4}?里)',a); return m.group(1) if m else None
def geocode(rows,max_new=10**9,log=print):
    cache=json.load(open(C)) if os.path.exists(C) else {}; n=[0]
    def nom(q):
        if q in cache: return cache[q]
        if n[0]>=max_new: return None
        n[0]+=1; r=None
        u='https://nominatim.openstreetmap.org/search?'+urllib.parse.urlencode({'q':q,'format':'json','limit':1,'countrycodes':'tw'})
        for t in range(3):
            try: r=json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30)); break
            except Exception: time.sleep(5)
        time.sleep(1.1)
        if r is None: return None
        cache[q]=[float(r[0]['lat']),float(r[0]['lon'])] if r else []; return cache[q]
    for i,r in enumerate(rows):
        d=r['district']; res=None; rd=road(r['address'],d); v=village(r['address'],d)
        if rd: res=nom(f'{rd}, {d}, 臺南市'); r['_geo']='road'
        if not res and v: res=nom(f'{v}, {d}, 臺南市'); r['_geo']='village'
        if not res: res=nom(f'{d}, 臺南市'); r['_geo']='district'
        r['_ll']=res
        if i%200==0: log('geo',i,len(rows))
    try: json.dump(cache,open(C,'w'),ensure_ascii=False)
    except Exception: pass
    return rows
