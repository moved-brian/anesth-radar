"""
Scraper: 台灣疼痛醫學會 (PAIN)
URL: https://pain.org.tw/index.php/news_page/news_page2_content
Structure: Two tables on page — Table[0] is search form, Table[1] is course list.
           Columns: ID | 類型 | 活動日期 | 標題 | 瀏覽
Note: NO individual event pages exist on this site.
      All events link back to the listing page.
      SSL cert broken: use verify=False
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


def scrape() -> list[dict]:
    log.info("PAIN: fetching %s", LIST_URL)
    try:
        r = requests.get(LIST_URL, headers=HEADERS, timeout=15, verify=False)
        r.raise_for_status()
        for enc in [r.apparent_encoding, "utf-8", "big5"]:
            try:
                r.encoding = enc
                _ = r.text
                break
            except Exception:
                continue
    except Exception as e:
        log.error("PAIN fetch failed: %s", e)
        return []

    soup = BeautifulSoup(r.text, "lxml")

    # Page has TWO tables: [0] = search form, [1] = course list
    tables = soup.find_all("table")
    if len(tables) < 2:
        log.warning("PAIN: expected 2 tables, got %d", len(tables))
        return []

    course_table = tables[1]
    events = []

    for row in course_table.select("tr"):
        cols = row.select("td")
        if len(cols) < 4:
            continue

        row_id   = cols[0].get_text(strip=True)
        category = cols[1].get_text(strip=True) or "學術活動"
        date_raw = cols[2].get_text(strip=True)
        title    = cols[3].get_text(strip=True)
        date_str = parse_date(date_raw)

        if not title or not row_id.isdigit():
            continue

        # No individual pages — link to listing page
        url = LIST_URL

        events.append(make_event(title, date_str, SOURCE, category, url))

    log.info("PAIN: %d events", len(events))
    return events
