import json,re,time,os,urllib.request,urllib.parse
UA={'User-Agent':'tainan-prospects/1.0 (hank87327@kimo.com)'}
rows=json.load(open('tn.json'))
C='cache.json'; cache=json.load(open(C)) if os.path.exists(C) else {}
def nom(q):
    if q in cache: return cache[q]
    u='https://nominatim.openstreetmap.org/search?'+urllib.parse.urlencode({'q':q,'format':'json','limit':1,'countrycodes':'tw'})
    for t in range(3):
        try:
            r=json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30)); break
        except Exception as e: r=None; time.sleep(5)
    time.sleep(1.1)
    if r is None: return None
    cache[q]=[float(r[0]['lat']),float(r[0]['lon'])] if r else []
    return cache[q]
def road(a,d):
    a=a.split(d,1)[-1]; a=re.sub(r'^.*?里','',a); a=re.sub(r'^\d+鄰','',a)
    m=re.match(r'(.+?(?:路|街|大道)(?:[一二三四五六七八九十\d]+段)?)',a)
    return m.group(1) if m else None
for i,r in enumerate(rows):
    d=r['_d']; v=r['工廠市鎮鄉村里'][3:].replace(d,'')
    rd=road(r['工廠地址'],d); res=None
    if rd:
        res=nom(f'{rd}, {d}, 臺南市'); r['_geo']='road'
    if not res and v:
        res=nom(f'{v}, {d}, 臺南市'); r['_geo']='village'
    if not res:
        res=nom(f'{d}, 臺南市'); r['_geo']='district'
    r['_ll']=res
    if i%100==0:
        json.dump(cache,open(C,'w'),ensure_ascii=False); print(i,len(cache),flush=True)
json.dump(cache,open(C,'w'),ensure_ascii=False); json.dump(rows,open('geo.json','w'),ensure_ascii=False); print('done')
