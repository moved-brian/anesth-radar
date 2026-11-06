"""
Anesth Radar - 活動興趣評分

移植自 pulm-radar / drpwchen/paper-radar（MIT）的 score_paper()，
把評分對象從「論文 title + abstract」換成「活動標題」。
（不比對 category：那是各學會爬蟲固定貼的分類，會讓整個來源的每一筆都命中同一組。）

評分規則（interest_model.json）：
  1. positive：每組任一 keyword 命中就加 weight 一次，並貼上該組 tag
  2. negative：每組任一 keyword 命中就加負分——除非該 tag 的 exception 有命中
  3. bonus：第一個命中的加對應分數（命中即停）
  4. dated_bonus：有明確活動日期的加分（公告通常沒有日期）
  5. stale_year_penalty：沒有日期、且標題只提到「今年以前」的年份，
     或公告日（posted）已超過 stale_posted_days 天 → 視為過期資訊
"""

import json
import re
from datetime import date
from pathlib import Path

MODEL_FILE = Path(__file__).parent / "interest_model.json"

# 零寬字元（學會網站標題偶爾夾帶，會讓「名​單」比對不到「名單」）
_ZERO_WIDTH = re.compile(r"[​‌‍⁠﻿]")
# 民國年：115年、114.04.19、115/11/15
_ROC_YEAR = re.compile(r"(?<!\d)(1[0-2]\d)(?=\s*年|[./．]\d{1,2}[./．]\d{1,2})")
# 西元年：2026、20260913（後面接 4 碼月日）
_AD_YEAR = re.compile(r"(?<!\d)(20[1-3]\d)(?:\d{4})?(?!\d)")


def load_model(path: Path = MODEL_FILE) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalize(text: str) -> str:
    return _ZERO_WIDTH.sub("", text or "")


def kw_hit(kw: str, text: str) -> bool:
    """
    關鍵字比對（text 需已轉小寫）。
    短英文縮寫（<=5 字、無空白、含大寫）用字界比對，避免 AI∈GAI/pain、
    TEE∈committee、ICU∈difficult、ERAS∈erase 這類子字串誤命中；
    其餘（含所有中文關鍵字）為單純子字串比對。
    """
    k = kw.lower()
    if len(kw) <= 5 and " " not in kw and kw.isascii() and any(c.isupper() for c in kw):
        return re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", text) is not None
    return k in text


def mentioned_years(title: str) -> list[int]:
    """標題裡提到的年份（民國年轉西元）。"""
    years = [int(m.group(1)) + 1911 for m in _ROC_YEAR.finditer(title)]
    years += [int(m.group(1)) for m in _AD_YEAR.finditer(title)]
    return years


def score_event(event: dict, model: dict, today: date | None = None):
    """
    回傳 (score, tags, why)。
      tags：命中的 tag；負向為 "neg:<tag>"、加分為 "bonus:<詞>"
      why ：[[說明, 分數], ...]，給前端顯示分數分解
    """
    today = today or date.today()
    title = normalize(event.get("title", ""))
    text = title.lower()
    score, tags, why = 0, [], []

    for group in model.get("positive", []):
        for kw in group["keywords"]:
            if kw_hit(kw, text):
                score += group["weight"]
                tags.append(group["tag"])
                why.append([group["tag"], group["weight"]])
                break

    exceptions = model.get("negative_exceptions", {})
    for group in model.get("negative", []):
        for kw in group["keywords"]:
            if kw_hit(kw, text):
                if any(kw_hit(ek, text) for ek in exceptions.get(group["tag"], [])):
                    break
                score += group["weight"]
                tags.append(f"neg:{group['tag']}")
                why.append([group["tag"], group["weight"]])
                break

    for word, bonus in model.get("bonus", {}).items():
        if kw_hit(word, text):
            score += bonus
            tags.append(f"bonus:{word}")
            why.append([word, bonus])
            break

    if event.get("date"):
        dated = model.get("dated_bonus", 0)
        if dated:
            score += dated
            why.append(["有明確活動日期", dated])
    else:
        stale = model.get("stale_year_penalty", 0)
        years = mentioned_years(title)
        posted = event.get("posted") or ""
        if stale and years and max(years) < today.year:
            score += stale
            tags.append("neg:過期資訊")
            why.append([f"只提到 {max(years)} 年以前", stale])
        elif (stale and posted and (today - date.fromisoformat(posted)).days
                > model.get("stale_posted_days", 180)):
            score += stale
            tags.append("neg:過期資訊")
            why.append([f"公告日 {posted}，已超過半年", stale])

    return score, tags, why


def tier_of(score: int, model: dict) -> str:
    th = model.get("thresholds", {})
    if score >= th.get("recommend", 3):
        return "recommended"
    if score >= th.get("candidate", 1):
        return "candidate"
    return "skipped"
