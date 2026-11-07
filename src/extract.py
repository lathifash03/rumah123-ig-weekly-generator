"""Step 4: fetch article text in memory and extract facts with verified quotes.

Article text is never written to disk. Only the URL, title, date, source and
the short extracted facts with their short quotes are kept.
"""
from __future__ import annotations

import requests
import trafilatura

from .config import prompt, sources
from .models import EXTRACT_SCHEMA, Fact, Item, VerifiedItem
from .textutil import normalize_ws, quote_is_grounded

MAX_QUOTE_CHARS = 300
MAX_ARTICLE_CHARS = 20000


def fetch_text(url: str) -> str:
    """Download and extract the readable article body. Held in memory only."""
    cfg = sources()["request"]
    resp = requests.get(
        url,
        headers={"User-Agent": cfg["user_agent"]},
        timeout=cfg.get("timeout_seconds", 25),
    )
    resp.raise_for_status()
    text = trafilatura.extract(resp.text, include_comments=False,
                               include_tables=False) or ""
    return normalize_ws(text)


def extract(llm, item: Item) -> tuple[VerifiedItem, dict]:
    """Extract facts for one item and verify every quote against the article.

    A fact whose quote is not a substring of the fetched article text is
    dropped and the drop is recorded. The model is never trusted to confirm
    that it copied a quote correctly.
    """
    log: dict = {"url": item.url, "title": item.title}
    try:
        article = fetch_text(item.url)
    except Exception as exc:
        log["error"] = f"fetch failed: {type(exc).__name__}: {exc}"[:200]
        return VerifiedItem(item=item, facts=[]), log

    log["article_chars"] = len(article)
    if len(article) < 400:
        log["error"] = f"article text too short ({len(article)} chars)"
        return VerifiedItem(item=item, facts=[]), log

    data = llm.json(
        prompt("extract.md"),
        f"ARTICLE TEXT\n\n{article[:MAX_ARTICLE_CHARS]}",
        EXTRACT_SCHEMA,
    )

    kept: list[Fact] = []
    dropped: list[dict] = []
    for raw in data.get("facts", []):
        claim = normalize_ws(raw.get("claim", ""))
        quote = normalize_ws(raw.get("quote", ""))
        if not claim or not quote:
            dropped.append({"claim": claim, "quote": quote,
                            "reason": "empty claim or quote"})
            continue
        if len(quote) > MAX_QUOTE_CHARS:
            dropped.append({"claim": claim, "quote": quote[:120] + "...",
                            "reason": f"quote longer than {MAX_QUOTE_CHARS} chars"})
            continue
        if not quote_is_grounded(quote, article):
            dropped.append({"claim": claim, "quote": quote[:160],
                            "reason": "quote_not_found_in_article"})
            continue
        kept.append(Fact(claim=claim, quote=quote))

    log["facts_kept"] = len(kept)
    log["facts_dropped"] = len(dropped)
    log["dropped_detail"] = dropped
    return VerifiedItem(item=item, facts=kept, facts_dropped=len(dropped)), log
