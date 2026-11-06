"""
Scraper: 台灣區域麻醉暨止痛醫學會 (RAPM)
URL: https://rapm.org.tw/news-list/2   (學會活動)
Structure: list of <a> links. Individual pages contain date info.
"""

import re
import logging
from datetime import date

import requests
from bs4 import BeautifulSoup

from .base import get_soup, parse_date, make_event, HEADERS

log = logging.getLogger(__name__)

BASE_URL    = "https://rapm.org.tw"
LIST_URL    = f"{BASE_URL}/news-list/2"
SOURCE      = "RAPM"
CATEGORY    = "區域麻醉・疼痛介入"

# 標題裡的活動日沒有年份："疼痛擂台 6 ＠June 28"、"年會 ＠December 4-6"、"＠Jan 30-31"
_TITLE_MD_RE = re.compile(r"[@＠]\s*([A-Za-z]{3,9})\.?\s*(\d{1,2})")
# 公告日藏在被註解掉的 <!--<h4 class="service_date">2026-10-02</h4>-->，get_text() 讀不到
_POSTED_RE   = re.compile(r'service_date"\s*>\s*(\d{4}-\d{2}-\d{2})')
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def _fetch_detail(url: str) -> tuple[str | None, str | None]:
    """Fetch individual event page. Returns (公告日, 內文裡的日期)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
    except Exception as e:
        log.error("GET %s failed: %s", url, e)
        return None, None
    m = _POSTED_RE.search(resp.text)
    posted = m.group(1) if m else None
    body_date = parse_date(BeautifulSoup(resp.text, "lxml").get_text(" "))
    return posted, body_date


def _date_from_title(title: str, posted: str | None) -> str | None:
    """「＠December 4-6」沒有年份 → 取公告日（含）之後第一個該月該日。"""
    m = _TITLE_MD_RE.search(title)
    month = _MONTHS.get(m.group(1)[:3].lower()) if m else None
    if not month or not posted:
        return None
    base = date.fromisoformat(posted)
    for year in (base.year, base.year + 1):
        try:
            d = date(year, month, int(m.group(2)))
        except ValueError:
            continue
        if d >= base:
            return d.isoformat()
    return None


def scrape() -> list[dict]:
    log.info("RAPM: fetching %s", LIST_URL)
    soup = get_soup(LIST_URL)
    if soup is None:
        return []

    events = []

    # The page has links like /news-detail/24
    for a in soup.select("a[href*='/news-detail/']"):
        title = a.get_text(strip=True)
        if not title:
            continue

        href = a["href"]
        url  = href if href.startswith("http") else BASE_URL + href

        # 1) 標題本身有完整日期
        date_str = parse_date(title)
        posted = None

        # 2) 否則抓活動頁：公告日 + 標題的「＠月 日」推年份；再不行才用內文日期
        if not date_str:
            log.info("RAPM: fetching event page for date: %s", url)
            posted, body_date = _fetch_detail(url)
            date_str = _date_from_title(title, posted) or body_date

        event = make_event(title, date_str, SOURCE, CATEGORY, url)
        if posted:
            event["posted"] = posted   # 沒有活動日時，評分用它判斷是否為過期公告
        events.append(event)

    # Deduplicate by URL
    seen = set()
    unique = []
    for e in events:
        if e["url"] not in seen:
            seen.add(e["url"])
            unique.append(e)

    log.info("RAPM: %d events scraped", len(unique))
    return unique
