"""
Scraper: 中華民國重症醫學會 (TSCCM)
URL: https://www.tsccm.org.tw/Academic/index_other.asp   (其他學會課程，含重症積分)
     https://www.tsccm.org.tw/od/Academic/index.asp?act_kindid=1  (重症課程)
Structure: ASP classic site with a <dl>/<dd> or table-like block per event.
Fields: 日期 | 主辦單位 | 課程 | 學分 | 地點 | 聯絡人

FILTER: Only keep items where title/organizer contains anesthesia-related keywords
        (麻醉, 插管, 呼吸道, 重症, ACLS, 疼痛, 鎮靜, 超音波, ICU, sedation).
"""

import re
import logging
from .base import get_soup, parse_date, make_event

log = logging.getLogger(__name__)

BASE_URL = "https://www.tsccm.org.tw"
SOURCE   = "TSCCM"
CATEGORY = "重症・ACLS"

PAGES = [
    f"{BASE_URL}/Academic/index_other.asp",
    f"{BASE_URL}/od/Academic/index.asp?act_kindid=1",
    f"{BASE_URL}/od/Academic/index.asp?act_kindid=2",  # 聯甄課程
]

# Keywords to keep (anesthesia-relevant filter)
KEEP_KEYWORDS = re.compile(
    r"麻醉|插管|呼吸道|ACLS|氣道|鎮靜|超音波|疼痛|重症|ICU|CPR|急救|"
    r"sedation|intub|airway|ultrasound",
    re.I
)


def _parse_other_page(soup, url: str) -> list[dict]:
    """Parse the 'other societies' listing (index_other.asp) format."""
    events = []
    if soup is None:
        return events

    # Each event block: contains 日期:, 主辦單位:, 課程:, 地點:, 學分:
    # Find all "課程：" labels and work outward
    text_blocks = []

    # Strategy: find <li> or <div> blocks that contain "課程：" and "日期："
    content = soup.find("div", id=re.compile("content|main", re.I)) or soup.body

    # Split the page text into event blocks using "日期：" as delimiter
    full_text = content.get_text("\n") if content else soup.get_text("\n")
    blocks = re.split(r"(?=日期：)", full_text)

    for block in blocks:
        if "課程：" not in block:
            continue

        date_m = re.search(r"日期：\s*(.+?)(?:\n|～|~|$)", block)
        course_m = re.search(r"課程：\s*(.+?)(?:\n|$)", block)
        org_m = re.search(r"主辦單位：\s*(.+?)(?:\n|$)", block)
        place_m = re.search(r"地點：\s*(.+?)(?:\n|$)", block)

        if not course_m:
            continue

        title = course_m.group(1).strip()
        date_raw = date_m.group(1).strip() if date_m else ""
        organizer = org_m.group(1).strip() if org_m else ""

        # Apply keyword filter
        combined = title + " " + organizer
        if not KEEP_KEYWORDS.search(combined):
            continue

        date_str = parse_date(date_raw)
        events.append(make_event(title, date_str, SOURCE, CATEGORY, url))

    return events


def _parse_kindid_page(soup, url: str) -> list[dict]:
    """Parse act_kindid listing (od/Academic/index.asp) format."""
    events = []
    if soup is None:
        return events

    # Look for table rows or list items with course info
    for row in soup.select("tr"):
        tds = row.select("td")
        if len(tds) < 3:
            continue
        text = row.get_text(" ", strip=True)
        if "課程" not in text and "活動" not in text:
            continue

        # Try to find a link or title
        a = row.find("a")
        title = a.get_text(strip=True) if a else tds[-1].get_text(strip=True)
        date_str = parse_date(text)

        if not title or not KEEP_KEYWORDS.search(title + " " + text):
            continue

        href = a["href"] if a and a.get("href") else url
        full_url = href if href.startswith("http") else BASE_URL + "/" + href.lstrip("/")
        events.append(make_event(title, date_str, SOURCE, CATEGORY, full_url))

    return events


def _get_page_count(soup) -> int:
    if soup is None:
        return 1
    # Look for pagination pattern like "頁次：1 / N"
    m = re.search(r"頁次[：:]\s*\d+\s*/\s*(\d+)", soup.get_text())
    if m:
        return int(m.group(1))
    return 1


def scrape() -> list[dict]:
    all_events = []

    # Page 1: other-societies listing (index_other.asp) — paginated with ?/N.html
    url = PAGES[0]
    log.info("TSCCM: fetching %s", url)
    soup = get_soup(url)
    total = _get_page_count(soup)
    log.info("TSCCM: %d pages in other-listing", total)
    all_events.extend(_parse_other_page(soup, url))

    for pg in range(2, min(total, 5) + 1):  # cap at 5 pages
        pg_url = f"{url}?/{pg}.html"
        log.info("TSCCM: fetching page %d: %s", pg, pg_url)
        s = get_soup(pg_url)
        all_events.extend(_parse_other_page(s, pg_url))

    # act_kindid pages
    for page_url in PAGES[1:]:
        log.info("TSCCM: fetching %s", page_url)
        s = get_soup(page_url)
        all_events.extend(_parse_kindid_page(s, page_url))

    # Deduplicate by title+date
    seen = set()
    unique = []
    for e in all_events:
        key = (e["title"], e["date"])
        if key not in seen:
            seen.add(key)
            unique.append(e)

    log.info("TSCCM: %d events after filter+dedup", len(unique))
    return unique
