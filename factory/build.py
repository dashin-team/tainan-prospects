import json,re,random,collections,os,sys
rows=json.load(open('geo.json')); cap=json.load(open('cap.json')) if os.path.exists('cap.json') else {}
db=json.load(open(sys.argv[1]))
def norm(s): return re.sub(r'[\s()（）股份有限公司企業社工廠行]','',s or '')
def na(a): return re.sub(r'[臺台]南市|\s','',a or '').replace('之','-')
names={(norm(b['name']),b['district']) for b in db['businesses']}
addrs={na(b.get('address')) for b in db['businesses'] if b.get('address')}
ids={b['id'] for b in db['businesses']}
new=[];dup=0;c=collections.Counter();g=collections.Counter()
seen=set()
for r in rows:
    fid='fac-'+r['工廠登記編號']
    if fid in ids or fid in seen: continue
    seen.add(fid)
    if (norm(r['工廠名稱']),r['_d']) in names or na(r['工廠地址']) in addrs: dup+=1; continue
    ll=r['_ll'] or [None,None]
    if not ll or ll[0] is None: continue
    jit=0.0006 if r['_geo']=='road' else 0.002 if r['_geo']=='village' else 0.006
    tid=r['統一編號'].strip(); cp=cap.get(tid)
    new.append({'id':fid,'name':r['工廠名稱'],'category':'工廠','subtype':re.sub(r'^\d+','',r['產業類別']).strip(),
     'district':r['_d'],'address':r['工廠地址'],'phone':'','website':'',
     'lat':round(ll[0]+random.uniform(-jit,jit),6),'lng':round(ll[1]+random.uniform(-jit,jit),6),
     'status':'未拜訪','source':'工廠登記','note':'',
     'industry':r['產業類別'].strip(),'products':r['主要產品'].strip(),'factory_reg_no':r['工廠登記編號'],
     'tax_id':tid,'owner':r['工廠負責人姓名'],'org_type':r['工廠組織型態'],'capital':cp or '',
     'employees':'','group5':False,'geo_precision':r['_geo']})
    c[r['_d']]+=1; g[r['_geo']]+=1
db['businesses']+=new
json.dump(db,open(sys.argv[2],'w'),ensure_ascii=False)
print('added',len(new),'dup',dup,dict(c),dict(g),'capital',sum(1 for n in new if n['capital']),'total',len(db['businesses']))
