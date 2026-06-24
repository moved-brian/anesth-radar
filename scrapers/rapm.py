"""
Scraper: 台灣區域麻醉暨止痛醫學會 (RAPM)
URL: https://rapm.org.tw/news-list/2   (學會活動)
Structure: list of <a> links. Individual pages contain date info.
"""

import re
import logging
from .base import get_soup, parse_date, make_event

log = logging.getLogger(__name__)

BASE_URL    = "https://rapm.org.tw"
LIST_URL    = f"{BASE_URL}/news-list/2"
SOURCE      = "RAPM"
CATEGORY    = "區域麻醉・疼痛介入"

_DATE_IN_TITLE_RE = re.compile(r"@\s*(\w+ \d+|\w+\s+\d{1,2})", re.I)  # "@June 28"


def _fetch_event_date(url: str) -> str | None:
    """Fetch individual event page to extract the date."""
    soup = get_soup(url)
    if soup is None:
        return None
    # Look for patterns like "2026-06-28" or "2026年" or "June 28"
    text = soup.get_text(" ")
    return parse_date(text)


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

        # Try to extract date from title first (e.g. "疼痛擂台 6 ＠June 28")
        date_str = None

        # Check title for a date string
        date_str = parse_date(title)

        # If no date in title, fetch the event page
        if not date_str:
            log.info("RAPM: fetching event page for date: %s", url)
            date_str = _fetch_event_date(url)

        events.append(make_event(title, date_str, SOURCE, CATEGORY, url))

    # Deduplicate by URL
    seen = set()
    unique = []
    for e in events:
        if e["url"] not in seen:
            seen.add(e["url"])
            unique.append(e)

    log.info("RAPM: %d events scraped", len(unique))
    return unique
