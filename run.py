#!/usr/bin/env python3
"""
Anesth Radar - Main Runner
Usage:
    python run.py                    # scrape all sources
    python run.py --sources TSA RAPM # scrape specific sources
    python run.py --dry-run          # print counts only, no file write
"""

import argparse
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path

from scrapers import ALL_SCRAPERS

log = logging.getLogger("run")
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = DATA_DIR / "events.json"


def dedup(events: list[dict]) -> list[dict]:
    """
    Deduplicate events by (title, date) or (url, date).
    Keeps first occurrence.
    """
    seen_url   = set()
    seen_title = set()
    unique = []

    for e in events:
        url_key   = (e["url"],   e["date"])
        title_key = (e["title"][:40], e["date"])  # first 40 chars of title

        if url_key in seen_url or title_key in seen_title:
            continue

        if e["url"] and "javascript:" not in e["url"]:
            seen_url.add(url_key)
        seen_title.add(title_key)
        unique.append(e)

    return unique


def filter_future(events: list[dict], include_past_days: int = 0) -> list[dict]:
    """
    Optionally filter to only upcoming events.
    include_past_days=0: only today onwards
    include_past_days=30: include events up to 30 days in the past
    """
    today = date.today()
    result = []
    for e in events:
        if not e["date"]:
            result.append(e)  # keep undated events
            continue
        try:
            ev_date = date.fromisoformat(e["date"])
            delta = (today - ev_date).days
            if delta <= include_past_days:
                result.append(e)
        except ValueError:
            result.append(e)
    return result


def sort_events(events: list[dict]) -> list[dict]:
    """Sort by event date ascending (undated events last)."""
    def sort_key(e):
        d = e.get("date", "")
        return d if d else "9999-99-99"
    return sorted(events, key=sort_key)


def run(sources: list[str] = None, dry_run: bool = False,
        include_past_days: int = 7) -> list[dict]:

    targets = sources or list(ALL_SCRAPERS.keys())
    all_events = []
    stats = {}

    for name in targets:
        if name not in ALL_SCRAPERS:
            log.warning("Unknown source: %s (valid: %s)", name, list(ALL_SCRAPERS))
            continue
        log.info("━━━ Scraping: %s ━━━", name)
        try:
            events = ALL_SCRAPERS[name]()
            stats[name] = len(events)
            all_events.extend(events)
            log.info("  → %d events from %s", len(events), name)
        except Exception as exc:
            log.error("  ✗ %s scraper failed: %s", name, exc, exc_info=True)
            stats[name] = 0

    log.info("Total raw: %d events", len(all_events))
    unique = dedup(all_events)
    log.info("After dedup: %d events", len(unique))
    upcoming = filter_future(unique, include_past_days=include_past_days)
    log.info("After date filter (past %d days): %d events", include_past_days, len(upcoming))
    sorted_events = sort_events(upcoming)

    # Print summary table
    print("\n" + "="*60)
    print("  ANESTH RADAR — Scrape Summary")
    print("="*60)
    for name, count in stats.items():
        print(f"  {name:<10} {count:>4} events")
    print(f"  {'TOTAL':<10} {len(unique):>4} unique  |  {len(sorted_events):>4} upcoming")
    print("="*60 + "\n")

    if not dry_run:
        output = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "total": len(sorted_events),
            "sources": stats,
            "events": sorted_events,
        }
        OUTPUT_FILE.write_text(
            json.dumps(output, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        log.info("Saved %d events → %s", len(sorted_events), OUTPUT_FILE)

    return sorted_events


def main():
    parser = argparse.ArgumentParser(description="Anesth Radar scraper")
    parser.add_argument(
        "--sources", nargs="+", metavar="SRC",
        help=f"Sources to scrape (default: all). Options: {list(ALL_SCRAPERS)}"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print stats only, do not write output file"
    )
    parser.add_argument(
        "--past-days", type=int, default=7,
        help="Include events up to N days in the past (default: 7)"
    )
    parser.add_argument(
        "--all-history", action="store_true",
        help="Do not filter by date (include all historical events)"
    )
    args = parser.parse_args()

    past = 99999 if args.all_history else args.past_days
    run(sources=args.sources, dry_run=args.dry_run, include_past_days=past)


if __name__ == "__main__":
    main()
