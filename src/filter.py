"""Step 2: keyword relevance, then dedupe. Pure code, no LLM."""
from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

from .config import rules
from .models import Item
from .textutil import keyword_matches, title_similarity

_TRACKING = re.compile(r"^(utm_|fbclid|gclid|ref|source|campaign)", re.I)


def normalize_url(url: str) -> str:
    """Canonical URL for dedupe: drop scheme case, www, tracking params,
    fragment and a trailing slash."""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    query = "&".join(
        q for q in parts.query.split("&")
        if q and not _TRACKING.match(q.split("=")[0])
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), host, path, query, ""))


def relevant(items: list[Item]) -> tuple[list[Item], list[dict]]:
    """Keep items matching at least min_matches keywords and not blocklisted."""
    cfg = rules()["relevance"]
    keywords = cfg["keywords"]
    min_matches = cfg.get("min_matches", 1)
    blocklist = [re.compile(p, re.I) for p in cfg.get("title_blocklist", [])]

    kept: list[Item] = []
    rejected: list[dict] = []
    for item in items:
        if any(p.search(item.title) for p in blocklist):
            rejected.append({"url": item.url, "title": item.title,
                             "reason": "title_blocklist"})
            continue
        hits = keyword_matches(f"{item.title} {item.summary}", keywords)
        if len(hits) < min_matches:
            rejected.append({"url": item.url, "title": item.title,
                             "reason": "no_keyword_match"})
            continue
        item.keywords_matched = hits
        kept.append(item)
    return kept, rejected


def dedupe(items: list[Item]) -> tuple[list[Item], list[dict]]:
    """Drop exact URL duplicates then fuzzy title duplicates.

    The fuzzy pass matters: the live detik feed carried four near-identical
    headlines about the same IKN apartment block.
    """
    threshold = rules()["dedupe"]["title_similarity_threshold"]
    kept: list[Item] = []
    dropped: list[dict] = []
    seen_urls: dict[str, str] = {}

    for item in items:
        norm = normalize_url(item.url)
        if norm in seen_urls:
            dropped.append({"url": item.url, "title": item.title,
                            "reason": "duplicate_url",
                            "duplicate_of": seen_urls[norm]})
            continue
        twin = next(
            (k for k in kept
             if title_similarity(item.title, k.title) >= threshold), None
        )
        if twin is not None:
            dropped.append({"url": item.url, "title": item.title,
                            "reason": "similar_title",
                            "duplicate_of": twin.url,
                            "similarity": round(
                                title_similarity(item.title, twin.title), 3)})
            continue
        seen_urls[norm] = item.url
        kept.append(item)
    return kept, dropped
