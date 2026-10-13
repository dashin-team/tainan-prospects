"""排除名單：連鎖便利商店、加油站（更新名單時也會套用）。"""
import re
CVS=re.compile(r"7-?ELEVEN|7-11|セブン|統一超商|全家|family ?mart|萊爾富|hi-?life|OK ?(超商|mart)|OK便利|來來超商|美廉社",re.I)
FUEL=re.compile(r"加油站|中油|台塑石油|台亞|全國加油|福懋加油|西歐加油|山隆|統一精工",re.I)
OTHER=re.compile(r"蝦皮|shopee|全聯|px ?mart|台灣菸酒|臺灣菸酒",re.I)
def OTHER_LABEL(n):
    return "蝦皮店到店" if re.search(r"蝦皮|shopee",n,re.I) else "全聯" if re.search(r"全聯|px ?mart",n,re.I) else "台灣菸酒"
def excluded(b):
    n=b.get("name","");st=b.get("subtype","")
    if st=="fuel" or FUEL.search(n): return "加油站"
    if OTHER.search(n): return OTHER_LABEL(n)
    if CVS.search(n) or (st=="convenience" and CVS.search(n+b.get("brand",""))): return "連鎖便利商店"
    return None
