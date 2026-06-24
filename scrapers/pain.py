"""
Scraper: 台灣疼痛醫學會 (PAIN)
URL: https://pain.org.tw/index.php/news_page/news_page2_content
Note: SSL cert has missing Subject Key Identifier — use verify=False
"""

import logging
import requests
import urllib3
from bs4 import BeautifulSoup

from .base import parse_date, make_event, HEADERS

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log      = logging.getLogger(__name__)
BASE_URL = "https://pain.org.tw"
LIST_URL = f"{BASE_URL}/index.php/news_page/news_page2_content"
SOURCE   = "疼痛醫學會"


def _get_soup(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        r.raise_for_status()
        for enc in [r.apparent_encoding, "utf-8", "big5"]:
            try:
                r.encoding = enc
                _ = r.text
                break
            except Exception:
                continue
        return BeautifulSoup(r.text, "lxml")
    except Exception as e:
        log.error("PAIN fetch %s failed: %s", url, e)
        return None


def scrape() -> list[dict]:
    log.info("PAIN: fetching %s", LIST_URL)
    soup = _get_soup(LIST_URL)
    if soup is None:
        return []

    events = []

    # Strategy 1: HTML table (original approach)
    table = soup.find("table")
    if table:
        for row in table.select("tr"):
            cols = row.select("td")
            if len(cols) < 4:
                continue
            category = cols[1].get_text(strip=True) or "學術活動"
            date_raw = cols[2].get_text(strip=True)
            title_td = cols[3]
            date_str = parse_date(date_raw)
            title    = title_td.get_text(strip=True)
            if not title:
                continue
            a   = title_td.find("a")
            url = (BASE_URL + a["href"] if a and a.get("href") and not a["href"].startswith("http")
                   else (a["href"] if a and a.get("href") else LIST_URL))
            events.append(make_event(title, date_str, SOURCE, category, url))
        if events:
            log.info("PAIN table: %d events", len(events))
            return events

    # Strategy 2: list / article items
    for item in soup.select("li, article, .item, .news-item, tr"):
        a = item.find("a", href=True)
        if not a:
            continue
        title    = a.get_text(strip=True)
        href     = a["href"]
        url      = href if href.startswith("http") else BASE_URL + href
        date_str = parse_date(item.get_text(" "))
        if title:
            events.append(make_event(title, date_str, SOURCE, "學術活動", url))

    # Deduplicate
    seen, unique = set(), []
    for e in events:
        if e["title"] not in seen:
            seen.add(e["title"])
            unique.append(e)

    log.info("PAIN: %d events", len(unique))
    return unique
