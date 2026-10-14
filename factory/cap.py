import json,time,urllib.request,os,ssl
from concurrent.futures import ThreadPoolExecutor
X=ssl._create_unverified_context()
rows=json.load(open('tn.json')); C='cap.json'; cap=json.load(open(C)) if os.path.exists(C) else {}
ids=sorted({r['統一編號'].strip() for r in rows if r['統一編號'].strip()} - set(cap))
def get(u):
    t=urllib.request.urlopen(u,timeout=20,context=X).read().decode(); return json.loads(t) if t.strip() else []
def one(b):
    for k in range(3):
        try:
            j=get(f"https://data.gcis.nat.gov.tw/od/data/api/5F64D864-61CB-4D0D-8AD9-492047CC1EA6?$format=json&$filter=Business_Accounting_NO%20eq%20{b}&$skip=0&$top=1")
            if j: return b,j[0].get('Capital_Stock_Amount')
            j=get(f"https://data.gcis.nat.gov.tw/od/data/api/7E6AFA72-AD6A-46D3-8681-ED77951D912D?$format=json&$filter=President_No%20eq%20{b}&$skip=0&$top=1")
            return b,(j[0].get('Business_Register_Funds') if j else None)
        except Exception as e: time.sleep(3)
    return b,'ERR'
n=0
with ThreadPoolExecutor(4) as ex:
    for b,v in ex.map(one,ids):
        if v!='ERR': cap[b]=v
        n+=1
        if n%200==0: json.dump(cap,open(C,'w')); print(n,len(ids),flush=True)
json.dump(cap,open(C,'w')); print('done',len(cap))
