"""食品業者登錄（非登不可）來源：下載 FDA 開放資料、篩台南八區、排除連鎖、去重、地理編碼。"""
import csv,io,json,os,re,random,zipfile,urllib.request,collections,sys
D=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(D,'fda'))
from exclude import excluded
from chains import chain
URL="https://data.fda.gov.tw/data/opendata/export/97/csv"
DIST=['南區','北區','東區','中西區','安南區','永康區','安定區','安平區']
P=re.compile(r'^\s*(?:\d{3,6})?\s*(?:臺|台)南市\s*('+'|'.join(DIST)+')')
NONTARGET=re.compile(r'藥局|藥房|眼鏡|通訊|電信')
def norm(s): return re.sub(r'[\s()（）股份有限公司企業社工廠行號]','',s or '')
def na(a): return re.sub(r'^\d+|[臺台]南市|\s','',a or '').replace('之','-')
def parse(raw):
    by={}
    for x in csv.reader(io.StringIO(raw)):
        if len(x)<5: continue
        m=P.match(x[2])
        if not m: continue
        e=by.setdefault(x[3],{'reg':x[3],'name':x[0].strip(),'tax_id':x[1].strip(),'address':x[2].strip(),'district':m.group(1),'items':set()}); e['items'].add(x[4])
    return list(by.values())
def download():
    z=zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(urllib.request.Request(URL,headers={'User-Agent':'tainan-prospects/1.0'}),timeout=600).read()))
    return z.read(z.namelist()[0]).decode('utf-8-sig')
def filt(rows):
    keep=[];rm=collections.Counter()
    for e in rows:
        if not set(e['items'])-{'公司/商業登記'}: continue
        x=excluded({'name':e['name']}) or chain(e['name']) or ('藥局/眼鏡/通訊' if NONTARGET.search(e['name']) else None)
        if x: rm[x]+=1
        else: keep.append(e)
    return keep,rm
def cat(items):
    return ('食品製造','food_factory') if '工廠/製造場所' in items else ('餐飲','restaurant') if '餐飲場所' in items else ('食品零售','food_shop')
def dedupe(rows,businesses):
    ids={b['id'] for b in businesses}; names={(norm(b.get('name')),b.get('district')) for b in businesses}
    addrs={na(b.get('address')) for b in businesses if b.get('address')}; tax={b.get('tax_id') for b in businesses if b.get('tax_id')}
    out=[];dup=0
    for e in rows:
        if 'fda-'+e['reg'] in ids: continue
        if (norm(e['name']),e['district']) in names or na(e['address']) in addrs or (e['tax_id'] and e['tax_id'] in tax): dup+=1; continue
        out.append(e)
    return out,dup
def to_biz(e):
    ll=e.get('_ll') or None; g=e.get('_geo','district')
    jit=0.0006 if g=='road' else 0.002 if g=='village' else 0.006
    c,st=cat(e['items'])
    return {'id':'fda-'+e['reg'],'name':e['name'],'category':c,'subtype':st,'district':e['district'],'address':e['address'],
     'lat':round(ll[0]+random.uniform(-jit,jit),6) if ll else '','lng':round(ll[1]+random.uniform(-jit,jit),6) if ll else '',
     'status':'未拜訪','source':'非登不可','tax_id':e['tax_id'],'products':'、'.join(sorted(set(e['items'])-{'公司/商業登記'})),
     'note':'食品業者登錄字號 '+e['reg'],'geo_precision':g,'pl_target':True}
def fetch(businesses,max_new_geo=400,log=print):
    """回傳 (新店家清單, 排除統計, 重複數)。只對新資料做地理編碼；超過上限的未快取路段放行政區概略座標。"""
    import geo_util
    rows,rm=filt(parse(download())); new,dup=dedupe(rows,businesses)
    geo_util.geocode(new,max_new=max_new_geo,log=log)
    return [to_biz(e) for e in new],rm,dup
