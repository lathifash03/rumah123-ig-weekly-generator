"""Step 2: keyword relevance, then dedupe. Pure code, no LLM."""
from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

from .config import rules
from .models import Item
from .textutil import (
    keyword_matches,
    story_signature_scorer,
    titles_are_same_story,
)

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
    """Drop exact URL duplicates, then headlines covering the same story.

    The second pass carries the weight here. A property desk retells one story
    many times a week: the live detik feed carried nine separate headlines
    about the same subsidised apartment project in Manggarai and four about the
    same block in IKN. Without this, the ranker spends its budget choosing
    between retellings of one story.
    """
    cfg = rules()["dedupe"]
    seq_threshold = cfg["title_sequence_threshold"]
    score_threshold = cfg["story_rarity_score_threshold"]
    min_shared = cfg["min_shared_specific_words"]

    # The relevance keywords are what every candidate has in common, so they
    # carry no information about which story a headline covers.
    topic_words = {
        word
        for kw in rules()["relevance"]["keywords"]
        for word in kw.lower().split()
    }
    scorer = story_signature_scorer([i.title for i in items], topic_words)

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

        twin = None
        scores: dict = {}
        for candidate in kept:
            same, scores = titles_are_same_story(
                item.title, candidate.title, seq_threshold,
                score_threshold, min_shared, scorer)
            if same:
                twin = candidate
                break

        if twin is not None:
            dropped.append({"url": item.url, "title": item.title,
                            "reason": "same_story",
                            "duplicate_of": twin.url,
                            "duplicate_of_title": twin.title,
                            **scores})
            continue

        seen_urls[norm] = item.url
        kept.append(item)
    return kept, dropped
