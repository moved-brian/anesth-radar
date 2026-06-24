"""
Base scraper class and shared utilities for Anesth Radar.
All scrapers return a list of dicts with the standard schema:
{
    "title":   str,
    "date":    str,          # ISO format: "YYYY-MM-DD" (event date)
    "source":  str,          # short label, e.g. "TSA", "RAPM"
    "category": str,         # tag, e.g. "月會", "工作坊", "年會", "重症"
    "url":     str,          # link to original page
    "scraped_at": str        # ISO datetime when scraped
}
"""

import re
import logging
from datetime import datetime, date
from typing import Optional

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}


def get_soup(url: str, timeout: int = 15, **kwargs) -> Optional[BeautifulSoup]:
    """GET a URL and return a BeautifulSoup object. Returns None on failure."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, **kwargs)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        logging.getLogger(__name__).error("GET %s failed: %s", url, e)
        return None


def post_soup(url: str, data: dict, timeout: int = 15) -> Optional[BeautifulSoup]:
    """POST and return BeautifulSoup. Returns None on failure."""
    try:
        resp = requests.post(url, data=data, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        logging.getLogger(__name__).error("POST %s failed: %s", url, e)
        return None


# ── Date helpers ────────────────────────────────────────────────────────────

_ISO_RE      = re.compile(r"(\d{4})-(\d{2})-(\d{2})")           # 2026-06-27
_ISO_SLASH   = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})")       # 2026/07/17
_ZH_RE       = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")   # 2026年5月6日
_ROC_RE      = re.compile(r"\b(\d{2,3})/(\d{1,2})/(\d{1,2})\b") # 115/06/27  (word-boundary)


def parse_date(text: str) -> Optional[str]:
    """
    Parse various date formats found on TW medical society sites.
    Returns "YYYY-MM-DD" string or None.

    Priority order:
      1. YYYY-MM-DD   (ISO dash)
      2. YYYY/MM/DD   (ISO slash — must come before ROC to avoid 2026→026 mishit)
      3. YYYY年MM月DD日 (Chinese)
      4. YYY/MM/DD    (ROC calendar: 115 → 2026)
    """
    text = (text or "").strip()

    m = _ISO_RE.search(text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    m = _ISO_SLASH.search(text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    m = _ZH_RE.search(text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    m = _ROC_RE.search(text)
    if m:
        year = int(m.group(1)) + 1911
        # Sanity check: ROC years in use should be 100–120 (2011–2031)
        if 100 <= int(m.group(1)) <= 130:
            return f"{year}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    return None


def now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def make_event(title: str, date_str: Optional[str], source: str,
               category: str, url: str) -> dict:
    return {
        "title":      title.strip(),
        "date":       date_str or "",
        "source":     source,
        "category":   category,
        "url":        url,
        "scraped_at": now_iso(),
    }
