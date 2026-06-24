"""
Scraper: 台灣麻醉醫學會 (TSA)
URL: https://www.anesth.org.tw/events/index.asp
Note: Old ASP site, likely Big5 encoded. Pagination uses POST with `sub` field.
      href on event links is RELATIVE: content.asp?ID=X&EduType=Y
"""

import re
import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import parse_date, make_event, now_iso, HEADERS

log = logging.getLogger(__name__)

BASE_URL   = "https://www.anesth.org.tw"
EVENTS_URL = f"{BASE_URL}/events/index.asp"
NEWS_URL   = f"{BASE_URL}/news/"

EDUTYPE_MAP = {
    "A": "月會", "B": "繼教課程", "C": "學術活動",
    "E": "國際",  "1": "年會",    "245": "年會工作坊",
    "4": "鎮靜課程", "5": "學術活動", "D": "報名",
}
NEWS_TYPE_MAP = {
    "1": "學會公告", "2": "求才求職", "3": "政府公告",
    "4": "月會資訊", "5": "其他學術資訊", "6": "麻醉學雜誌", "9": "年會公告",
}

_PAGE_RE    = re.compile(r"sub\.value=(\d+)")
_EDUTYPE_RE = re.compile(r"[Ee]du[Tt]ype=(\w+)")


def _get_soup(url, method="GET", data=None):
    """Fetch with Big5 fallback and loose SSL."""
    try:
        if method == "POST":
            r = requests.post(url, data=data, headers=HEADERS, timeout=15, verify=False)
        else:
            r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        r.raise_for_status()
        # ASP classic sites often use Big5
        for enc in [r.apparent_encoding, "big5", "utf-8", "cp950"]:
            try:
                r.encoding = enc
                _ = r.text  # force decode test
                break
            except Exception:
                continue
        return BeautifulSoup(r.text, "lxml")
    except Exception as e:
        log.error("TSA fetch %s failed: %s", url, e)
        return None


def _get_total_pages(soup) -> int:
    if soup is None:
        return 1
    max_page = 1
    for tag in soup.find_all(onclick=True):
        m = _PAGE_RE.search(tag["onclick"])
        if m:
            max_page = max(max_page, int(m.group(1)))
    # Also look for text like "共 N 頁"
    m2 = re.search(r"共\s*(\d+)\s*頁", soup.get_text())
    if m2:
        max_page = max(max_page, int(m2.group(1)))
    return max_page


def _parse_events_page(soup) -> list[dict]:
    if soup is None:
        return []
    events = []

    # TSA uses relative href: content.asp?ID=X&EduType=Y
    # Match any <a> whose href contains content.asp OR ID= (covers both formats)
    selectors = [
        "a[href*='content.asp']",
        "a[href*='ID=']",
        "a[href*='id=']",
    ]
    links = []
    for sel in selectors:
        links = soup.select(sel)
        if links:
            break

    # Fallback: all links in the main content area
    if not links:
        content = soup.find("div", id=re.compile("content|main|list", re.I)) or soup.body
        if content:
            links = content.find_all("a", href=True)

    log.debug("TSA page: found %d candidate links", len(links))

    for a in links:
        href  = a.get("href", "")
        text  = a.get_text(" ", strip=True)
        if not text or len(text) < 4:
            continue
        # Skip nav/header links
        if any(w in href.lower() for w in ["index", "javascript", "mailto", "#"]):
            if "content" not in href.lower() and "ID=" not in href:
                continue

        date_str = parse_date(text)

        m_type   = _EDUTYPE_RE.search(href)
        raw_type = m_type.group(1) if m_type else ""
        category = EDUTYPE_MAP.get(raw_type, "學術活動")

        # Clean title: remove leading date, category keyword, trailing metadata
        title = re.sub(r"^\d{2,3}/\d{1,2}/\d{1,2}", "", text).strip()
        title = re.sub(
            r"^(月會活動|麻醉活動|繼續教育課程|年會活動|鎮靜活動|年會工作坊|學術活動)\s*", "",
            title
        )
        for stop in ["活動地點：", "主辦單位：", "麻醉積分：", "麻醉重症積分：", "積分："]:
            if stop in title:
                title = title[:title.index(stop)].strip()

        if not title:
            continue

        url = href if href.startswith("http") else BASE_URL + "/events/" + href.lstrip("/")
        events.append(make_event(title, date_str, "TSA", category, url))

    return events


def scrape_tsa_events(max_pages: int = 5) -> list[dict]:
    import urllib3; urllib3.disable_warnings()
    log.info("TSA events: fetching page 1")
    soup = _get_soup(EVENTS_URL, method="POST", data={"sub": "1"})
    if soup is None:
        return []

    total = _get_total_pages(soup)
    limit = min(total, max_pages) if max_pages else total
    log.info("TSA events: %d pages total, fetching up to %d", total, limit)

    all_events = _parse_events_page(soup)
    for page in range(2, limit + 1):
        log.info("TSA events: page %d/%d", page, limit)
        s = _get_soup(EVENTS_URL, method="POST", data={"sub": str(page)})
        all_events.extend(_parse_events_page(s))

    log.info("TSA events: %d events scraped", len(all_events))
    return all_events


def _parse_news_page(soup, news_type: str) -> list[dict]:
    if soup is None:
        return []
    category = NEWS_TYPE_MAP.get(news_type, "公告")
    items = []
    # News links: href contains news/content.asp or content.asp
    for a in soup.select("a[href*='content.asp'], a[href*='ID=']"):
        href  = a.get("href", "")
        if "news" not in href.lower() and "news" not in a.find_parent(href=False, class_=False, id=False).__class__.__name__.lower() if a.find_parent() else True:
            pass  # allow all content links on news pages
        text = a.get_text(" ", strip=True)
        if not text or len(text) < 4:
            continue
        date_str = parse_date(text)
        title    = re.sub(r"^\d{2,3}/\d{1,2}/\d{1,2}\s*", "", text).strip()
        url      = href if href.startswith("http") else BASE_URL + "/news/" + href.lstrip("/")
        if title:
            items.append(make_event(title, date_str, "TSA", category, url))
    return items


def scrape_tsa_news(types: list = None) -> list[dict]:
    import urllib3; urllib3.disable_warnings()
    if types is None:
        types = ["1", "4", "5", "9"]
    all_news = []
    for t in types:
        url  = f"{NEWS_URL}index.asp?type={t}"
        log.info("TSA news type=%s", t)
        soup = _get_soup(url)
        all_news.extend(_parse_news_page(soup, t))
    log.info("TSA news: %d items", len(all_news))
    return all_news


def scrape() -> list[dict]:
    return scrape_tsa_events(max_pages=5) + scrape_tsa_news()
