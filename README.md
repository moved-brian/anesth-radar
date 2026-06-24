# 麻醉科進修雷達 — Anesth Radar 爬蟲

自動彙整台灣麻醉相關學會的課程與公告，輸出為結構化 JSON。

## 支援來源

| 代號    | 學會                           | 分類         |
|---------|--------------------------------|--------------|
| TSA     | 台灣麻醉醫學會                 | 月會/年會/繼教 |
| PAIN    | 台灣疼痛醫學會                 | 疼痛/介入    |
| RAPM    | 台灣區域麻醉暨止痛醫學會       | 區域麻醉     |
| TSCVA   | 臺灣心臟胸腔暨血管麻醉醫學會   | 心臟麻醉/TEE |
| TWERAS  | 台灣術後加速康復學會           | ERAS/周術期  |
| TSCCM   | 中華民國重症醫學會             | 重症/ACLS    |

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
```

## 輸出格式 (data/events.json)

```json
{
  "generated_at": "2026-06-24T09:00:00Z",
  "total": 42,
  "sources": { "TSA": 15, "PAIN": 20, "RAPM": 7 },
  "events": [
    {
      "title":      "2026年VIPS介入性疼痛研討會",
      "date":       "2026-07-17",
      "source":     "PAIN",
      "category":   "學術活動",
      "url":        "https://pain.org.tw/...",
      "scraped_at": "2026-06-24T09:00:00Z"
    }
  ]
}
```

## 自動排程（cron）

每 3 小時自動更新（同原復健雷達設計）：

```cron
0 */3 * * * cd /path/to/anesth_radar && python run.py >> logs/cron.log 2>&1
```

## 加入新來源

1. 在 `scrapers/` 建立新的 `xxx.py`，實作 `scrape() -> list[dict]`
2. 在 `scrapers/__init__.py` 的 `ALL_SCRAPERS` dict 中加入
3. 跑 `python run.py --sources XXX --dry-run` 測試

## 注意事項

- 本工具僅抓取**公開公告頁**的標題與連結，導回原站，非官方彙整
- TSA 活動列表使用 JavaScript POST 分頁，預設只爬前 5 頁（最近活動）
- TSCCM 結果會過濾麻醉相關關鍵字（麻醉、插管、ACLS 等）
- TSAM（呼吸道處理醫學會）為 Wix 建站，課程以圖片形式發布，暫不支援

## 待新增來源

- [ ] 台灣呼吸道處理醫學會 TSAM（需 OCR 或手動更新）
- [ ] 台灣急救加護醫學會 SECCM（`seccm.org.tw`）
- [ ] 台灣麻醉專科護理學會 TANA（`tana.org.tw`）
