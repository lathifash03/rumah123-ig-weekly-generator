"""Step 3: LLM ranks the top 3 items. Items with no concrete facts are rejected."""
from __future__ import annotations

import json

from .config import prompt
from .models import RANK_SCHEMA, Item


def rank(llm, items: list[Item], top_n: int = 3) -> tuple[list[Item], list[dict]]:
    """Return (chosen items, per-item ranking decisions for the log)."""
    if not items:
        return [], []

    listing = "\n\n".join(
        f"index: {i}\ntitle: {it.title}\nsummary: {it.summary[:600]}\n"
        f"source: {it.source_display}\npublished: {it.published}"
        for i, it in enumerate(items)
    )
    data = llm.json(prompt("rank.md"), f"CANDIDATE ITEMS\n\n{listing}", RANK_SCHEMA)

    decisions: list[dict] = []
    chosen: list[Item] = []
    for entry in data.get("top", []):
        idx = entry.get("index")
        if not isinstance(idx, int) or not (0 <= idx < len(items)):
            decisions.append({"index": idx, "kept": False,
                              "reason": "index out of range"})
            continue
        item = items[idx]
        # The prompt forbids it, but enforce in code anyway: no concrete facts
        # means the item is not usable.
        if not entry.get("has_concrete_facts"):
            decisions.append({"index": idx, "url": item.url, "title": item.title,
                              "score": entry.get("score"), "kept": False,
                              "reason": "no_concrete_facts"})
            continue
        if any(c.url == item.url for c in chosen):
            decisions.append({"index": idx, "url": item.url, "kept": False,
                              "reason": "duplicate_in_ranking"})
            continue
        decisions.append({"index": idx, "url": item.url, "title": item.title,
                          "score": entry.get("score"), "kept": True,
                          "reason": entry.get("reason", "")})
        chosen.append(item)
        if len(chosen) >= top_n:
            break
    return chosen, decisions
