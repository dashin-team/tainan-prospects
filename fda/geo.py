import json,re,time,os,sys,urllib.request,urllib.parse
UA={'User-Agent':'tainan-prospects/1.0 (hank87327@kimo.com)'}
C='../factory/cache.json'; cache=json.load(open(C))
def nom(q):
    if q in cache: return cache[q]
    u='https://nominatim.openstreetmap.org/search?'+urllib.parse.urlencode({'q':q,'format':'json','limit':1,'countrycodes':'tw'})
    r=None
    for t in range(3):
        try: r=json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30)); break
        except Exception: time.sleep(5)
    time.sleep(1.1)
    if r is None: return None
    cache[q]=[float(r[0]['lat']),float(r[0]['lon'])] if r else []; return cache[q]
def road(a,d):
    a=a.split(d,1)[-1]; a=re.sub(r'^.*?里','',a); a=re.sub(r'^\d+鄰','',a)
    m=re.match(r'(.+?(?:路|街|大道)(?:[一二三四五六七八九十\d]+段)?)',a); return m.group(1) if m else None
def village(a,d):
    m=re.search(d+r'(.{1,4}?里)',a); return m.group(1) if m else None
def geocode(rows,log=print):
    for i,r in enumerate(rows):
        d=r['district']; rd=road(r['address'],d); res=None
        if rd: res=nom(f'{rd}, {d}, 臺南市'); r['_geo']='road'
        v=village(r['address'],d)
        if not res and v: res=nom(f'{v}, {d}, 臺南市'); r['_geo']='village'
        if not res: res=nom(f'{d}, 臺南市'); r['_geo']='district'
        r['_ll']=res
        if i%200==0: json.dump(cache,open(C,'w'),ensure_ascii=False); log(i,len(cache))
    json.dump(cache,open(C,'w'),ensure_ascii=False); return rows
if __name__=='__main__':
    rows=geocode(json.load(open('keep.json')),lambda *a:print(*a,flush=True))
    json.dump(rows,open('geo.json','w'),ensure_ascii=False); print('done')
