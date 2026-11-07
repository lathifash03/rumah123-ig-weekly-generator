"""Step 1: fetch configured RSS feeds and keep items from the last N days."""
from __future__ import annotations

import datetime as dt

import feedparser
import requests

from .config import sources
from .models import Item
from .textutil import normalize_ws


def _parse_date(entry) -> dt.datetime | None:
    tp = entry.get("published_parsed") or entry.get("updated_parsed")
    if not tp:
        return None
    return dt.datetime(*tp[:6], tzinfo=dt.timezone.utc)


def fetch_all(now: dt.datetime | None = None) -> tuple[list[Item], list[dict], list[dict]]:
    """Fetch every configured feed.

    Returns (items, feeds_ok, feeds_failed). Failures are returned rather than
    raised so that run_log.json can record exactly which feeds broke.
    """
    cfg = sources()
    now = now or dt.datetime.now(dt.timezone.utc)
    window = dt.timedelta(days=cfg.get("window_days", 7))
    headers = {"User-Agent": cfg["request"]["user_agent"]}
    timeout = cfg["request"].get("timeout_seconds", 25)

    items: list[Item] = []
    ok: list[dict] = []
    failed: list[dict] = []

    for feed in cfg["feeds"]:
        name, url = feed["name"], feed["url"]
        display = feed.get("display", name)
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code != 200:
                failed.append({"name": name, "url": url,
                               "error": f"HTTP {resp.status_code}"})
                continue
            parsed = feedparser.parse(resp.content)
        except Exception as exc:  # network error, DNS, TLS, malformed body
            failed.append({"name": name, "url": url,
                           "error": f"{type(exc).__name__}: {exc}"[:200]})
            continue

        if not parsed.entries:
            failed.append({"name": name, "url": url,
                           "error": "parsed but 0 entries"})
            continue

        kept = 0
        no_date = 0
        for entry in parsed.entries:
            published = _parse_date(entry)
            if published is None:
                no_date += 1
                continue
            if now - published > window:
                continue
            link = entry.get("link") or ""
            if not link:
                continue
            items.append(
                Item(
                    title=normalize_ws(entry.get("title", "")),
                    url=link,
                    published=published.isoformat(),
                    source=name,
                    source_display=display,
                    summary=normalize_ws(entry.get("summary", ""))[:1200],
                )
            )
            kept += 1

        ok.append({"name": name, "url": url, "entries": len(parsed.entries),
                   "kept_in_window": kept, "skipped_no_date": no_date})

    return items, ok, failed
