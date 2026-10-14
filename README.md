# 台南 團險/產責險 開發追蹤地圖

Leaflet 地圖 + Python 後端（標準函式庫 + openpyxl + pg8000）。

## 雲端部署（Render 免費 Web Service + Neon 免費 Postgres）
1. Neon（https://neon.tech，用 GitHub 登入）建立免費專案，區域選 AWS US East 2 (Ohio)，複製 connection string（`postgresql://...?...sslmode=require`）。
2. Render（https://render.com，用 GitHub 登入）→ New → Blueprint → 選此 repo（會讀 render.yaml）。
3. 環境變數：
   - `DATABASE_URL`：Neon 連線字串
   - `INIT_USERS`：首次建立帳號，例如 `shihhan:密碼1,team:密碼2`（已存在的帳號不會被覆蓋）
   - `SECRET_KEY`：自動產生（登入 cookie 簽章用）
4. 部署完成後網址為 `https://tainan-prospects-xxxx.onrender.com`。
5. 搬移現有資料（在有 data.json 的電腦上）：`DATABASE_URL=... python3 server.py import-json data.json`
   一併搬帳號：`DATABASE_URL=... python3 server.py import-json data.json users.json`
   新增同事（預設密碼 1234）：`DATABASE_URL=... python3 server.py addusers 小明 小華`
   新增帳號：`DATABASE_URL=... python3 server.py adduser 名字 [密碼]`

未設定 DATABASE_URL 時改存本機 data.json / users.json（本機模式）。

## 本機執行
`pip install -r requirements.txt && python3 server.py` → http://localhost:8080

## 資料
- seed_businesses.json：OpenStreetMap（ODbL）台南七區店家/工廠，已排除便利商店、加油站、蝦皮店到店、全聯、台灣菸酒（exclude.py）
- 網頁「更新店家/工廠名單」重新從 Overpass 抓取並合併，不會覆蓋拜訪紀錄
