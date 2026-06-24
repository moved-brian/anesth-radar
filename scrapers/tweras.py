"""
Scraper: 台灣術後加速康復學會 (TWERAS)
URL: https://tweras.org/category/event/
Structure: Elementor WordPress theme.
  - Each article has: a.elementor-post__thumbnail__link (URL)
  - Title in: .elementor-post__title a  or  h3 a
  - Date in title text (e.g. "2026/06/28 Asia Partnerships...")
"""

import re
import logging
import requests
from bs4 import BeautifulSoup
from .base import parse_date, make_event, HEADERS

log      = logging.getLogger(__name__)
BASE_URL = "https://tweras.org"
LIST_URL = f"{BASE_URL}/category/event/"
SOURCE   = "TWERAS"
CATEGORY = "ERAS・周術期"


def scrape() -> list[dict]:
    log.info("TWERAS: fetching %s", LIST_URL)
    try:
        r = requests.get(LIST_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
    except Exception as e:
        log.error("TWERAS fetch failed: %s", e)
        return []

    soup = BeautifulSoup(r.text, "lxml")
    events = []

    for art in soup.select("article"):
        # URL: thumbnail link is the most reliable
        link_tag = (
            art.select_one("a.elementor-post__thumbnail__link") or
            art.select_one(".elementor-post__title a") or
            art.select_one("h2 a, h3 a, h1 a")
        )
        if not link_tag:
            continue
        url = link_tag.get("href", "")
        if not url or url == "#":
            continue

        # Title: try dedicated title element first
        title_tag = (
            art.select_one(".elementor-post__title a") or
            art.select_one(".elementor-post__title") or
            art.select_one("h2, h3, h1")
        )
        title = title_tag.get_text(strip=True) if title_tag else ""

        # If no separate title, extract from URL slug
        if not title:
            slug = url.rstrip("/").split("/")[-1]
            title = slug.replace("-", " ").replace("_", " ").title()

        # Date: try from title first, then page text
        date_str = parse_date(title)
        if not date_str:
            date_str = parse_date(art.get_text(" "))

        # Clean date prefix from title (e.g. "2026/06/28 Asia...")
        title = re.sub(r"^\d{4}/\d{2}/\d{2}\s*", "", title).strip()
        title = re.sub(r"^\d{4}-\d{2}-\d{2}\s*", "", title).strip()

        if title:
            events.append(make_event(title, date_str, SOURCE, CATEGORY, url))

    # Deduplicate by URL
    seen, unique = set(), []
    for e in events:
        if e["url"] not in seen:
            seen.add(e["url"])
            unique.append(e)

    log.info("TWERAS: %d events", len(unique))
    return unique
