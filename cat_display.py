"""顯示用類別對照：資料庫仍保存原始細類，畫面與匯出另顯示工廠／餐飲業／其他。"""
FACTORY={"工廠","工廠/製造","食品製造"}
FOOD={"餐飲","餐飲業"}
DISPLAY=("工廠","餐飲業","其他")

def display_category(cat):
    c=(cat or "").strip()
    if c in FACTORY: return "工廠"
    if c in FOOD: return "餐飲業"
    return "其他"
