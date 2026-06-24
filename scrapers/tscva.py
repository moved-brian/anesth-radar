"""
Scraper: 臺灣心臟胸腔暨血管麻醉醫學會 (TSCVA)
URL: https://www.tscva.org.tw/continuing-education/academic-activities.html
     https://www.tscva.org.tw/continuing-education/other-academic-activities.html
Structure: Joomla CMS blog layout. Each post has a date + title + link.
Date format: "2026年05月06日"
"""

import logging
from .base import get_soup, parse_date, make_event

log = logging.getLogger(__name__)

BASE_URL = "https://www.tscva.org.tw"
SOURCE   = "TSCVA"

PAGES = [
    (f"{BASE_URL}/continuing-education/academic-activities.html",       "心臟麻醉"),
    (f"{BASE_URL}/continuing-education/other-academic-activities.html", "心臟麻醉"),
]


def _scrape_page(url: str, category: str) -> list[dict]:
    log.info("TSCVA: fetching %s", url)
    soup = get_soup(url)
    if soup is None:
        return []

    events = []

    # Joomla blog: each article wrapped in <div class="sppb-blog-item"> or similar
    # Posts: <h3>/<h4> title with <a>, date in <time> or text like "2026年05月06日"
    # Strategy: find all article blocks
    articles = (
        soup.select("div.sppb-blog-item")
        or soup.select("div.blog-item")
        or soup.select("article")
        or soup.select("div.item-page")
    )

    if not articles:
        # Fallback: grab all heading links with a date nearby
        for h in soup.select("h3 a, h4 a, h2 a"):
            href  = h.get("href", "")
            title = h.get_text(strip=True)
            if not title or not href:
                continue
            # Look for date in parent or sibling text
            parent_text = h.find_parent().get_text(" ", strip=True) if h.find_parent() else ""
            date_str = parse_date(parent_text)
            url_full = href if href.startswith("http") else BASE_URL + href
            events.append(make_event(title, date_str, SOURCE, category, url_full))
        return events

    for art in articles:
        # Title
        title_tag = art.select_one("h3 a, h4 a, h2 a")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        href  = title_tag.get("href", "")
        url_full = href if href.startswith("http") else BASE_URL + href

        # Date: look for <time> tag or text patterns
        time_tag = art.select_one("time")
        if time_tag:
            date_str = parse_date(time_tag.get("datetime", "") or time_tag.get_text())
        else:
            date_str = parse_date(art.get_text(" "))

        events.append(make_event(title, date_str, SOURCE, category, url_full))

    return events


def scrape() -> list[dict]:
    all_events = []
    for url, category in PAGES:
        all_events.extend(_scrape_page(url, category))

    # Deduplicate by URL
    seen = set()
    unique = []
    for e in all_events:
        if e["url"] not in seen:
            seen.add(e["url"])
            unique.append(e)

    log.info("TSCVA: %d events scraped", len(unique))
    return unique
