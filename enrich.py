"""
Anesth Radar - 加值層（爬完之後、輸出之前）

  1. infer_date_from_title()：爬蟲沒抓到日期時，從標題裡「帶年份的完整日期」推定活動日
  2. event_id()             ：每則活動的穩定 ID（前端 localStorage 標記、first_seen 都靠它）
  3. FirstSeenStore         ：生命週期去重。first_seen 永久保留，重抓只更新 last_seen
                              （同 pulm-radar 的 SQLite 設計，這裡改用 data/first_seen.json，
                               讓 GitHub Actions 可以直接 commit）
"""

import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from scoring import normalize

TAIPEI = timezone(timedelta(hours=8))


def today_taipei() -> date:
    """GitHub Actions 跑在 UTC；活動日期一律以台灣時間判斷。"""
    return datetime.now(TAIPEI).date()


# ── 1. 從標題推定日期 ────────────────────────────────────────────────────────

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
_SEP = r"[./．\-]"
# 「115.09.29更新」這種是公告更新日，不是活動日
_NOT_EVENT = re.compile(r"\s*(更新|修訂|修正|公告)")

# 全部都要求「有年份」，沒有年份的（11/8、＠December 4-6）不猜，避免把去年的活動標成今年
_PATTERNS = [
    # 115年1月17日（民國）
    (re.compile(r"(?<!\d)(1[0-2]\d)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
     lambda m: (int(m.group(1)) + 1911, int(m.group(2)), int(m.group(3)))),
    # 2026年10月4日
    (re.compile(r"(?<!\d)(20[1-3]\d)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
     lambda m: (int(m.group(1)), int(m.group(2)), int(m.group(3)))),
    # 2026．10．04 / 2026.10.04 / 2026/10/04 / 2026-10-04
    (re.compile(rf"(?<!\d)(20[1-3]\d){_SEP}(\d{{1,2}}){_SEP}(\d{{1,2}})(?!\d)"),
     lambda m: (int(m.group(1)), int(m.group(2)), int(m.group(3)))),
    # 114.04.19 / 115/11/15（民國）
    (re.compile(r"(?<!\d)(1[0-2]\d)[./．](\d{1,2})[./．](\d{1,2})(?!\d)"),
     lambda m: (int(m.group(1)) + 1911, int(m.group(2)), int(m.group(3)))),
    # 20240913（前面不能是「-」，避免把 02-20261231 這種電話號碼當成日期）
    (re.compile(r"(?<![\d\-])(20[1-3]\d)(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)"),
     lambda m: (int(m.group(1)), int(m.group(2)), int(m.group(3)))),
    # 9–10 December 2025 / 16 October 2025
    (re.compile(rf"(?<!\d)(\d{{1,2}})(?:\s*[–\-]\s*\d{{1,2}})?\s+{_MON},?\s+(20[1-3]\d)", re.I),
     lambda m: (int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))),
    # August 28th 2025 / December 4-6, 2026
    (re.compile(rf"{_MON}\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:\s*[–\-]\s*\d{{1,2}})?,?\s+(20[1-3]\d)", re.I),
     lambda m: (int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))),
]


def infer_date_from_title(title: str) -> Optional[str]:
    """標題裡第一個「帶年份的完整日期」→ "YYYY-MM-DD"；找不到回 None。"""
    title = normalize(title)
    best = None
    for pattern, to_ymd in _PATTERNS:
        for m in pattern.finditer(title):
            if _NOT_EVENT.match(title, m.end()):
                continue
            try:
                d = date(*to_ymd(m))
            except ValueError:
                continue
            if best is None or m.start() < best[0]:
                best = (m.start(), d)
            break
    return best[1].isoformat() if best else None


def fill_missing_dates(events: list[dict]) -> int:
    """沒有日期的活動嘗試從標題推定；推定的會標 date_inferred=True。回傳補上的筆數。"""
    n = 0
    for e in events:
        if e.get("date"):
            continue
        inferred = infer_date_from_title(e.get("title", ""))
        if inferred:
            e["date"] = inferred
            e["date_inferred"] = True
            n += 1
    return n


# ── 2. 穩定 ID ───────────────────────────────────────────────────────────────

def event_id(e: dict) -> str:
    """來源 + 標題 + 日期。不用 URL：疼痛醫學會所有活動共用同一個列表頁網址。"""
    raw = "|".join([e.get("source", ""), normalize(e.get("title", "")).strip(), e.get("date", "")])
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


# ── 3. first_seen 生命週期 ───────────────────────────────────────────────────

class FirstSeenStore:
    """
    data/first_seen.json：{ event_id: [first_seen, last_seen] }
    - 第一次建立（檔案不存在）時，當下所有活動的 first_seen 留空 → 不會整批被標成 NEW
    - 之後新出現的 ID 才記今天；某來源暫時爬失敗再回來，first_seen 不會被重置
    - 超過 keep_days 沒再出現的 ID 會被清掉，檔案不會無限長大
    """

    def __init__(self, path: Path, keep_days: int = 180):
        self.path = Path(path)
        self.keep_days = keep_days
        self.bootstrap = not self.path.exists()
        self.data: dict[str, list[str]] = {}
        if not self.bootstrap:
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.data = {}

    def stamp(self, events: list[dict], today: date) -> int:
        """替每則活動填上 id / first_seen，回傳這次新出現的筆數。"""
        today_s = today.isoformat()
        n_new = 0
        for e in events:
            eid = event_id(e)
            e["id"] = eid
            if eid in self.data:
                self.data[eid][1] = today_s
            else:
                self.data[eid] = ["" if self.bootstrap else today_s, today_s]
                n_new += 0 if self.bootstrap else 1
            e["first_seen"] = self.data[eid][0]
        return n_new

    def save(self, today: date):
        cutoff = (today - timedelta(days=self.keep_days)).isoformat()
        kept = {k: v for k, v in self.data.items() if v[1] >= cutoff}
        self.path.write_text(
            json.dumps(kept, ensure_ascii=False, indent=0, sort_keys=True),
            encoding="utf-8",
        )
