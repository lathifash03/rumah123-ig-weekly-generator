"""Step 7: a second LLM call checks the caption against the verified facts.

The model's answer is not taken at face value. Three deterministic checks sit
on top of it:

1. Coverage. The model must return the caption split into sentences, and code
   verifies the sentences reproduce the caption. In v1 the model returned
   whatever claims it chose to extract, so a claim it did not bother to list
   was never checked and the caption was only as verified as the model was
   thorough.
2. Fail-closed classification. A sentence the model calls non-factual is
   re-checked for a digit, a named institution or a verb of change. If one is
   present the sentence is treated as a factual claim regardless of the
   label, and then has to be supported like any other.
3. Quote and figure verification. The supporting quote must be findable in
   the verified facts, and every figure in the sentence must appear in that
   quote. A quote that matches the wording but not the number does not
   support the sentence.
"""
from __future__ import annotations

from .config import prompt, rules
from .models import CLAIMCHECK_SCHEMA, Fact, VerifiedItem
from .textutil import (
    coverage_key,
    keyword_matches,
    normalize_ws,
    quote_is_grounded,
    strip_hashtags,
    strip_tokens,
    ungrounded_number_words,
    ungrounded_numbers,
)
from .validate import Failure, facts_blob


def _has_digit(text: str, brand_tokens) -> bool:
    """Whether the sentence contains a digit, brand names excluded.

    The digits in "Rumah123" are part of a name, not a figure.
    """
    cleaned = strip_tokens(strip_hashtags(text or ""), brand_tokens)
    return any(ch.isdigit() for ch in cleaned)


def looks_factual(text: str, cfg: dict, brand_tokens) -> list[str]:
    """Reasons the sentence must be treated as a factual claim.

    An empty list means nothing forced the issue.
    """
    reasons: list[str] = []
    if _has_digit(text, brand_tokens):
        reasons.append("contains a digit")
    institutions = keyword_matches(text, cfg.get("institution_markers", []))
    if institutions:
        reasons.append(f"names {institutions}")
    verbs = keyword_matches(text, cfg.get("trend_verbs", []))
    if verbs:
        reasons.append(f"asserts change {verbs}")
    return reasons


def check(llm, caption: str, facts: list[Fact]) -> tuple[list[Failure], list[dict]]:
    """Return (failures, per-sentence detail for the log)."""
    if not facts:
        return [Failure("claimcheck", "No verified facts to check against.")], []

    cc_cfg = rules().get("claimcheck", {})
    brand_tokens = rules()["caption"].get("brand_tokens", [])
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

    sentences = data.get("sentences", []) or []
    failures: list[Failure] = []
    detail: list[dict] = []

    # --- check 1: the sentences must reproduce the caption -------------------
    returned = coverage_key("".join(s.get("text", "") for s in sentences))
    expected = coverage_key(caption)
    if returned != expected:
        failures.append(Failure(
            "sentence_coverage",
            "The claim check did not cover the whole caption, so parts of it "
            "were never checked. Treating the caption as unverified.",
        ))
        detail.append({
            "verdict": "coverage_mismatch",
            "expected_chars": len(expected),
            "returned_chars": len(returned),
        })
        return failures, detail

    # --- check 2 and 3: per sentence -----------------------------------------
    for raw in sentences:
        text = normalize_ws(raw.get("text", ""))
        if not text:
            continue
        model_factual = bool(raw.get("factual"))
        supported = bool(raw.get("supported"))
        quote = normalize_ws(raw.get("quote", ""))

        forced = looks_factual(text, cc_cfg, brand_tokens)
        effective_factual = model_factual or bool(forced)

        record: dict = {"sentence": text, "model_factual": model_factual,
                        "treated_as_factual": effective_factual}

        if not effective_factual:
            record["verdict"] = "non_factual"
            detail.append(record)
            continue

        if forced and not model_factual:
            # Fail closed. The model called this voice, but it carries a fact.
            record["verdict"] = "reclassified_as_factual"
            record["reasons"] = forced
            failures.append(Failure(
                "mislabelled_claim",
                f'Sentence "{text}" was labelled non-factual but it '
                f"{', '.join(forced)}. It is a factual claim and must be "
                f"supported by the verified facts, or removed.",
            ))
            detail.append(record)
            continue

        if not supported:
            record["verdict"] = "model_said_unsupported"
            failures.append(Failure(
                "unsupported_claim",
                f'Claim "{text}" is not supported by the verified facts. '
                f"Remove it or restate it using only what the facts say.",
            ))
            detail.append(record)
            continue

        # The model said supported. Verify its evidence exists.
        if not quote_is_grounded(quote, blob):
            record["verdict"] = "quote_not_found_in_facts"
            record["quote"] = quote[:160]
            failures.append(Failure(
                "unverifiable_claim",
                f'Claim "{text}" was marked supported but its supporting '
                f"quote is not found in the verified facts. Treat it as "
                f"unsupported and remove it.",
            ))
            detail.append(record)
            continue

        # Every figure in the sentence must appear in the quote itself.
        missing_digits = ungrounded_numbers(text, quote, brand_tokens)
        missing_words = ungrounded_number_words(text, quote, brand_tokens)
        if missing_digits or missing_words:
            record["verdict"] = "figures_not_in_quote"
            record["missing_figures"] = missing_digits + missing_words
            failures.append(Failure(
                "unsupported_figure",
                f'Claim "{text}" cites figures '
                f"{missing_digits + missing_words} that do not appear in its "
                f"own supporting quote. Use only figures the quote states.",
            ))
            detail.append(record)
            continue

        record["verdict"] = "quote_and_figures_verified"
        record["quote"] = quote[:160]
        detail.append(record)

    return failures, detail
