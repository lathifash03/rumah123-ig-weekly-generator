"""Step 7: second LLM call checks each caption claim against verified facts.

The model's answer is not taken at face value. Every quote it returns is
verified in code as a substring of the verified facts. A claim is only treated
as supported when the model says so AND the supporting quote is findable.
"""
from __future__ import annotations

from .config import prompt
from .models import CLAIMCHECK_SCHEMA, Fact, VerifiedItem
from .textutil import quote_is_grounded
from .validate import Failure, facts_blob


def check(llm, caption: str, facts: list[Fact]) -> tuple[list[Failure], list[dict]]:
    """Return (failures, per-claim detail for the log)."""
    if not facts:
        return [Failure("claimcheck", "No verified facts to check against.")], []

    blob = facts_blob(facts)
    listing = "\n".join(
        f'{i}. claim: {f.claim}\n   quote: "{f.quote}"'
        for i, f in enumerate(facts, 1)
    )
    data = llm.json(
        prompt("claimcheck.md"),
        f"VERIFIED FACTS:\n{listing}\n\nCAPTION:\n{caption}",
        CLAIMCHECK_SCHEMA,
    )

    failures: list[Failure] = []
    detail: list[dict] = []
    for raw in data.get("claims", []):
        claim = (raw.get("claim") or "").strip()
        supported = bool(raw.get("supported"))
        quote = (raw.get("quote") or "").strip()
        if not claim:
            continue

        if not supported:
            failures.append(Failure(
                "unsupported_claim",
                f'Claim "{claim}" is not supported by the verified facts. '
                f"Remove it or restate it using only what the facts say.",
            ))
            detail.append({"claim": claim, "supported": False,
                           "verdict": "model_said_unsupported"})
            continue

        # The model said supported. Verify its evidence actually exists.
        if not quote_is_grounded(quote, blob):
            failures.append(Failure(
                "unverifiable_claim",
                f'Claim "{claim}" was marked supported but its supporting '
                f"quote is not found in the verified facts. Treat it as "
                f"unsupported and remove it.",
            ))
            detail.append({"claim": claim, "supported": False,
                           "verdict": "quote_not_found_in_facts",
                           "quote": quote[:160]})
            continue

        detail.append({"claim": claim, "supported": True,
                       "verdict": "quote_verified"})

    return failures, detail
