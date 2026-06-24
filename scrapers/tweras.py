"""
Scraper: 台灣術後加速康復學會 (TWERAS)
URL: https://tweras.org/category/event/
Structure: WordPress category page. Standard post grid with titles, dates, links.
Also tries RSS feed as a more reliable alternative.
"""

import logging
from .base import get_soup, parse_date, make_event
import xml.etree.ElementTree as ET
import requests

log = logging.getLogger(__name__)

BASE_URL  = "https://tweras.org"
LIST_URL  = f"{BASE_URL}/category/event/"
RSS_URL   = f"{BASE_URL}/feed/?cat=event"
SOURCE    = "TWERAS"
CATEGORY  = "ERAS・周術期"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AnesthRadar/1.0)",
    "Accept-Language": "zh-TW,zh;q=0.9",
}


def _scrape_rss() -> list[dict]:
    """Try RSS feed first — most reliable for WordPress sites."""
    try:
        resp = requests.get(RSS_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        items = []
        for item in root.iter("item"):
            title = item.findtext("title", "").strip()
            link  = item.findtext("link", "").strip()
            pub   = item.findtext("pubDate", "")
            date_str = parse_date(pub)
            if title and link:
                items.append(make_event(title, date_str, SOURCE, CATEGORY, link))
        log.info("TWERAS RSS: %d items", len(items))
        return items
    except Exception as e:
        log.warning("TWERAS RSS failed: %s, falling back to HTML", e)
        return []


def _scrape_html() -> list[dict]:
    log.info("TWERAS HTML: fetching %s", LIST_URL)
    soup = get_soup(LIST_URL)
    if soup is None:
        return []

    events = []
    # WordPress article cards
    for art in soup.select("article"):
        title_tag = art.select_one("h2 a, h3 a, h1 a")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        href  = title_tag.get("href", "")
        url   = href if href.startswith("http") else BASE_URL + href

        time_tag = art.select_one("time")
        if time_tag:
            date_str = parse_date(time_tag.get("datetime") or time_tag.get_text())
        else:
            date_str = parse_date(art.get_text(" "))

        events.append(make_event(title, date_str, SOURCE, CATEGORY, url))

    log.info("TWERAS HTML: %d events", len(events))
    return events


def scrape() -> list[dict]:
    result = _scrape_rss()
    if not result:
        result = _scrape_html()
    return result
