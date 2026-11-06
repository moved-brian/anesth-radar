# 麻醉科進修雷達 — Anesth Radar

自動彙整台灣麻醉相關學會的課程與公告 → 依興趣關鍵字評分、貼主題標籤 → 輸出 `data/events.json`
→ 純前端網站（`index.html`）分「課程列表 / 活動行事曆」瀏覽。

線上版：<https://moved-brian.github.io/anesth-radar/>（GitHub Actions 每 3 小時自動更新）

> 評分、NEW 標籤、已看／收藏的做法移植自 pulm-radar（改寫自
> [drpwchen/paper-radar](https://github.com/drpwchen/paper-radar)，MIT），
> 把對象從「論文」換成「學會活動消息」。

## 支援來源

| 代號    | 學會                           | 分類         |
|---------|--------------------------------|--------------|
| TSA     | 台灣麻醉醫學會                 | 月會/年會/繼教 |
| PAIN    | 台灣疼痛醫學會                 | 疼痛/介入    |
| RAPM    | 台灣區域麻醉暨止痛醫學會       | 區域麻醉     |
| TSCVA   | 臺灣心臟胸腔暨血管麻醉醫學會   | 心臟麻醉/TEE |
| TWERAS  | 台灣術後加速康復學會           | ERAS/周術期  |
| TSCCM   | 中華民國重症醫學會             | 重症/ACLS    |

## 資料流

```
scrapers/*.py ── 爬 6 個學會的公開公告頁
      │
run.py ── dedup
      → enrich.fill_missing_dates()   沒日期的，從標題裡「帶年份的完整日期」推定
      → 過濾過期（預設保留過去 7 天）
      → scoring.score_event()         interest_model.json 評分 + 主題標籤
      → enrich.FirstSeenStore         first_seen 生命週期（NEW 標籤用）
      → data/events.json  +  data/first_seen.json
      │
index.html ── fetch('data/events.json') 渲染；收藏／已看存瀏覽器 localStorage
```

## 檔案地圖

| 檔案 | 角色 | 常改嗎 |
|---|---|---|
| **`interest_model.json`** | 興趣關鍵字權重、負向關鍵字、門檻 | ✅ 想調排序就改這個 |
| `scoring.py` | 評分核心（讀 `interest_model.json`） | ⚠ 改評分邏輯才動 |
| `enrich.py` | 標題補日期、活動 ID、first_seen | ⚠ 少動 |
| `run.py` | 主流程 | ⚠ 少動 |
| `scrapers/` | 各學會爬蟲 | 🔧 學會改版時才修 |
| `index.html` | 前端（單檔，無框架） | 改 UI 才動 |
| `data/events.json`、`data/first_seen.json` | 產物，由 GitHub Actions 自動 commit | 🤖 別手改 |

## 安裝

```bash
pip install requests beautifulsoup4 lxml
```

## 使用

```bash
# 爬所有來源，輸出到 data/events.json
python run.py

# 只爬特定來源
python run.py --sources TSA RAPM PAIN

# 包含過去 30 天的活動
python run.py --past-days 30

# 所有歷史資料（不過濾日期）
python run.py --all-history

# 只印統計，不寫檔案
python run.py --dry-run

# 改完 interest_model.json 後，不重爬、只重算分數
python run.py --rescore
```

本機看網站（一定要用 http server，直接雙擊 `index.html` 會被瀏覽器擋掉 `fetch`）：

```bash
python -m http.server 8898
```

然後開 <http://127.0.0.1:8898>。

## 網站功能

- 🔍 搜尋標題／來源／主題；排序可選「依活動日期／依推薦分數／最新上架優先」
- 🎯 推薦、✨ NEW（7 天內第一次被爬到）、⭐ 已收藏 三個快速檢視
- 來源／分類／主題標籤篩選；篩選條件會記住
- 每張卡片：主題標籤、⚠ 警示（報名截止、取消…）、倒數天數、右側推薦分數（點一下看分數怎麼算的）
- ⭐ 收藏、✅ 已看（已看的下次開啟預設隱藏）、📅 加入 Google 日曆
- 「自上次造訪以來新增 N 筆」提示條，點一下只看新增的
- 低相關公告（名單、人事、過期資訊）預設隱藏，勾「顯示低相關公告」才出現
- 收藏／已看只存在該裝置瀏覽器的 localStorage，換裝置不同步

## 調整成自己的口味：`interest_model.json`

只比對**活動標題**（大小寫不拘）。

```jsonc
{
  "thresholds": { "recommend": 3, "candidate": 1 },  // >= recommend → 推薦；>= candidate → 一般；其餘 → 低相關（預設隱藏）
  "positive": [                                       // 每組任一 keyword 命中就加 weight 一次，並貼上 tag
    { "weight": 3, "tag": "區域麻醉 / 神經阻斷", "keywords": ["區域麻醉", "神經阻斷", "nerve block", "ESRA"] }
  ],
  "negative": [                                       // 命中就扣分，除非該 tag 的 exception 有命中
    { "weight": -4, "tag": "名單 / 人事公告", "keywords": ["名單", "得獎", "當選"] }
  ],
  "negative_exceptions": { "名單 / 人事公告": ["報名名單"] },
  "bonus": { "開放報名": 1, "早鳥": 1 },              // 第一個命中的加分
  "dated_bonus": 1,                                   // 有明確活動日期 +1（純公告通常沒有日期）
  "stale_year_penalty": -10,                          // 沒日期、且標題只提到今年以前的年份（或公告已超過半年）
  "stale_posted_days": 180
}
```

眉角：

- **短英文縮寫用字界比對**：≤5 字、全 ASCII、含大寫的關鍵字（`AI`、`TEE`、`ICU`、`ERAS`…）
  不會命中 `pain`、`committee` 這類子字串；其餘（含所有中文）是單純子字串比對。
- **exception 也是子字串比對**，要寫具體片語（`報名名單`），別放太通用的字。
- 改完跑 `python run.py --rescore` 立刻看到新排序；`data/events.json` 每筆的 `why` 欄位是分數分解。

## 輸出格式 (data/events.json)

```json
{
  "generated_at": "2026-11-06T14:41:08Z",
  "total": 83,
  "sources": { "TSA": 60, "PAIN": 17, "RAPM": 17 },
  "new_days": 7,
  "tiers": { "recommended": 37, "candidate": 6, "skipped": 40 },
  "events": [
    {
      "id":         "8aacc179ea06",
      "title":      "神經阻斷術工作坊",
      "date":       "2026-11-21",
      "source":     "TSA",
      "category":   "學術活動",
      "url":        "https://www.anesth.org.tw/events/content.asp?ID=...",
      "scraped_at": "2026-11-06T14:40:35Z",
      "score":      7,
      "tags":       ["工作坊 / 實作", "區域麻醉 / 神經阻斷"],
      "why":        [["工作坊 / 實作", 3], ["區域麻醉 / 神經阻斷", 3], ["有明確活動日期", 1]],
      "tier":       "recommended",
      "first_seen": "2026-11-06"
    }
  ]
}
```

- `tier`：`recommended` / `candidate` / `skipped`（低相關，網站預設隱藏，但資料仍保留）
- `date_inferred: true`：日期是從標題推定的（網站上日期前面會有「≈」）
- `first_seen`：第一次被爬到的日期（台灣時間）。空字串 = 建立 `first_seen.json` 之前就存在的舊資料，不標 NEW

## 自動排程

GitHub Actions（`.github/workflows/scrape.yml`）每 3 小時跑一次 `python run.py --past-days 7`，
把 `data/events.json` 和 `data/first_seen.json` commit 回 repo，GitHub Pages 直接提供靜態網站。

自己的主機要跑的話：

```cron
0 */3 * * * cd /path/to/anesth_radar && python run.py >> logs/cron.log 2>&1
```

## 加入新來源

1. 在 `scrapers/` 建立新的 `xxx.py`，實作 `scrape() -> list[dict]`
2. 在 `scrapers/__init__.py` 的 `ALL_SCRAPERS` dict 中加入
3. 跑 `python run.py --sources XXX --dry-run` 測試

## 注意事項

- 本工具僅抓取**公開公告頁**的標題與連結，導回原站，非官方彙整
- 推薦分數只是標題關鍵字比對的結果，僅供排序參考，實際資訊以原公告為準
- TSA 活動列表使用 JavaScript POST 分頁，預設只爬前 5 頁（最近活動）
- TSCCM 結果會過濾麻醉相關關鍵字（麻醉、插管、ACLS 等）
- RAPM 標題的活動日沒有年份（`＠December 4-6`），用活動頁的公告日推定年份
- 沒有年份的日期（`11/8`、`10月14日`）不會猜，該筆維持「日期未定」
- TSAM（呼吸道處理醫學會）為 Wix 建站，課程以圖片形式發布，暫不支援

## 待新增來源

- [ ] 台灣呼吸道處理醫學會 TSAM（需 OCR 或手動更新）
- [ ] 台灣急救加護醫學會 SECCM（`seccm.org.tw`）
- [ ] 台灣麻醉專科護理學會 TANA（`tana.org.tw`）
