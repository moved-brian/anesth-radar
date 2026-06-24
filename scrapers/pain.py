"""
Scraper: 台灣疼痛醫學會 (PAIN)
URL: https://pain.org.tw/index.php/news_page/news_page2_content
Structure: HTML table with columns: ID | 類型 | 活動日期 | 標題
Note: NO individual event pages — each row IS the full listing.
      URL points to the listing page itself.
      SSL cert broken: use verify=False
"""

import re
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
        log.error("PAIN fetch failed: %s", e)
        return None


def scrape() -> list[dict]:
    log.info("PAIN: fetching %s", LIST_URL)
    soup = _get_soup(LIST_URL)
    if soup is None:
        return []

    events = []
    table = soup.find("table")
    if not table:
        log.warning("PAIN: no table found")
        return []

    for row in table.select("tr"):
        cols = row.select("td")
        if len(cols) < 4:
            continue

        # Columns: ID | 類型 | 活動日期 | 標題
        category = cols[1].get_text(strip=True) or "學術活動"
        date_raw = cols[2].get_text(strip=True)
        title    = cols[3].get_text(strip=True)
        date_str = parse_date(date_raw)

        if not title:
            continue

        # No individual pages — link directly to listing page
        # Add anchor with row ID if available (col[0])
        row_id = cols[0].get_text(strip=True)
        url = f"{LIST_URL}#{row_id}" if row_id.isdigit() else LIST_URL

        events.append(make_event(title, date_str, SOURCE, category, url))

    log.info("PAIN: %d events", len(events))
    return events
