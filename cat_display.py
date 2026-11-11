"""顯示用類別對照：資料庫仍保存原始細類，畫面與匯出另顯示工廠／餐飲業／其他。"""
FACTORY={"工廠","工廠/製造","食品製造"}
FOOD={"餐飲","餐飲業"}
DISPLAY=("工廠","餐飲業","其他")

def display_category(cat):
    c=(cat or "").strip()
    if c in FACTORY: return "工廠"
    if c in FOOD: return "餐飲業"
    return "其他"

def visible_on_map(cat, show_other=False, has_followup=False):
    """畫面預設隱藏「其他」；管理員開啟顯示其他，或該店有待追蹤時仍可見。不改資料庫。"""
    if display_category(cat)!="其他":
        return True
    return bool(show_other or has_followup)
