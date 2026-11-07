"""Step 6: caption validation. Pure code, no LLM.

Every rule here is mechanically checkable, so it is checked mechanically. The
model is never asked whether its own caption obeys the rules. In earlier
prompt-engineering work the model reported a 79 word caption that was actually
about 89 words, which is why counting lives here and not in a prompt.
"""
from __future__ import annotations

import re

from dataclasses import dataclass

from .config import rules
from .models import Fact
from .textutil import (
    NUMBER_RE,
    count_emoji,
    hashtags,
    keyword_matches,
    normalize_ws,
    split_blocks,
    split_sentences,
    strip_hashtags,
    ungrounded_number_words,
    ungrounded_numbers,
    word_count_excluding_hashtags,
)


@dataclass(frozen=True)
class Failure:
    rule: str
    message: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.message}"


def facts_blob(facts: list[Fact]) -> str:
    """All verified claim and quote text, used as the grounding corpus."""
    return normalize_ws(" ".join(f"{f.claim} {f.quote}" for f in facts))


def validate(caption: str, facts: list[Fact], source_display: str) -> list[Failure]:
    """Return every specific failure found in the caption. Empty list = pass."""
    cfg = rules()["caption"]
    failures: list[Failure] = []
    text = caption or ""

    # 1. word count, hashtags excluded
    limit = cfg["max_words_excluding_hashtags"]
    words = word_count_excluding_hashtags(text)
    if words > limit:
        failures.append(Failure(
            "word_count",
            f"Caption is {words} words excluding hashtags, limit is {limit}. "
            f"Remove at least {words - limit} words.",
        ))

    # 2. hashtags: exactly N, must include the required one
    tags = hashtags(text)
    want = cfg["hashtag_count"]
    required = cfg["required_hashtag"]
    if len(tags) != want:
        if not tags:
            # The commonest real failure by far. The message has to say what
            # to do, not just what is wrong: when it only reported the count,
            # the model returned a byte-identical caption on every retry.
            failures.append(Failure(
                "hashtag_count",
                f"The caption has no hashtags. ADD a new final line "
                f"containing exactly {want} hashtags: {required} followed by "
                f"one topic hashtag, for example \"{required} #KPR\". Keep "
                f"the rest of the caption as it is.",
            ))
        else:
            failures.append(Failure(
                "hashtag_count",
                f"Found {len(tags)} hashtags {tags}, need exactly {want}. "
                f"Rewrite the final line as {required} plus exactly one topic "
                f"hashtag.",
            ))
    lowered = [t.lower() for t in tags]
    if required.lower() not in lowered:
        failures.append(Failure(
            "required_hashtag",
            f"Required hashtag {required} is missing. Found {tags}. The final "
            f"line must start with {required}.",
        ))
    elif len(tags) == want:
        topic = [t for t in tags if t.lower() != required.lower()]
        if not topic:
            failures.append(Failure(
                "topic_hashtag",
                f"{required} appears twice. Need {required} plus one different "
                f"topic hashtag.",
            ))

    # 3. emoji
    max_emoji = cfg["max_emoji"]
    emoji = count_emoji(text)
    if emoji > max_emoji:
        failures.append(Failure(
            "emoji_count",
            f"Caption has {emoji} emoji, maximum is {max_emoji}.",
        ))

    # 4 and 5. forbidden characters
    forbidden = cfg["forbidden_characters"]
    if forbidden["em_dash"] in text:
        failures.append(Failure(
            "em_dash", "Caption contains an em dash. Use a full stop instead."))
    if forbidden["semicolon"] in text:
        failures.append(Failure(
            "semicolon", "Caption contains a semicolon. Use a full stop instead."))
    # An en dash between digits is a range ("2024-2025"). An en dash with
    # space beside it is being used as a dash, which the brief forbids.
    en_dash = forbidden["en_dash_as_separator"]
    if re.search(rf"(\s{re.escape(en_dash)}|{re.escape(en_dash)}\s)", text):
        failures.append(Failure(
            "en_dash",
            "Caption uses an en dash as a separator. Use a full stop instead.",
        ))

    # 6. banned phrases, matched on word boundaries rather than substring.
    # A plain substring search flagged "cuan" inside "suku bunga acuan", which
    # is a legitimate central-bank term.
    low = text.lower()
    hits = keyword_matches(text, cfg["banned_phrases"])
    if hits:
        failures.append(Failure(
            "banned_phrase",
            f"Caption contains banned hard-selling phrases: {hits}. Remove them.",
        ))

    # 7. source attribution
    if source_display and source_display.lower() not in low:
        failures.append(Failure(
            "missing_source",
            f'Caption must name the source "{source_display}". It does not appear.',
        ))

    # 8. number grounding
    blob = facts_blob(facts)
    brand = cfg.get("brand_tokens", [])
    missing = ungrounded_numbers(text, blob, brand)
    if missing:
        failures.append(Failure(
            "ungrounded_number",
            f"These numbers are not in the verified facts: {missing}. "
            f"Remove them or use only figures the facts state.",
        ))

    # 9. the same rule for figures written as Indonesian words. "naik delapan
    # persen" is as much a numeric claim as "naik 8 persen", and against a
    # verified "8,43 persen" it is a rounding.
    missing_words = ungrounded_number_words(text, blob, brand)
    if missing_words:
        failures.append(Failure(
            "ungrounded_number_word",
            f"These quantities written in words are not in the verified "
            f"facts: {missing_words}. Remove them or use only figures the "
            f"facts state, written the way the facts write them.",
        ))

    # 10. superlatives, absolutes and certainty words need support
    failures.extend(_check_guarded_words(text, blob, cfg))

    # 11. a hedged fact must stay hedged
    failures.extend(_check_hedges(text, facts, cfg))

    # 12. short blocks separated by blank lines
    failures.extend(_check_blocks(text, cfg))

    return failures


def _check_guarded_words(text: str, blob: str, cfg: dict) -> list[Failure]:
    """A superlative or absolute is a claim, so the facts must make it.

    "Paling tajam" asserts a ranking. "Tidak berubah" asserts certainty. The
    model reaches for both when paraphrasing, which is why this is checked
    rather than asked for in a prompt.
    """
    guarded = cfg.get("guarded_words", [])
    used = keyword_matches(text, guarded)
    supported = set(keyword_matches(blob, guarded))
    unsupported = [w for w in used if w not in supported]
    if not unsupported:
        return []
    return [Failure(
        "unsupported_superlative",
        f"These superlative or absolute words are not used by the verified "
        f"facts: {unsupported}. The facts do not establish a ranking or a "
        f"certainty, so remove the word or restate it as the facts do.",
    )]


def _check_hedges(text: str, facts: list[Fact], cfg: dict) -> list[Failure]:
    """A figure the facts only state as a target must not become a statement.

    For each hedged fact, the figures it carries are collected. A caption
    sentence citing such a figure has to hedge too. A figure that also appears
    in an unhedged fact is left alone, because the sentence may legitimately be
    drawing on that one instead.
    """
    hedge_cfg = cfg.get("hedges", {})
    fact_hedges = hedge_cfg.get("in_facts", [])
    caption_hedges = hedge_cfg.get("allowed_in_caption", [])
    if not fact_hedges or not facts:
        return []

    hedged_figures: dict[str, str] = {}   # figure -> the hedge word used
    unhedged_figures: set[str] = set()
    for fact in facts:
        fact_text = f"{fact.claim} {fact.quote}"
        found = keyword_matches(fact_text, fact_hedges)
        figures = set(NUMBER_RE.findall(normalize_ws(fact.quote)))
        if found:
            for fig in figures:
                hedged_figures.setdefault(fig, found[0])
        else:
            unhedged_figures |= figures

    # a figure available from an unhedged fact carries no obligation
    obliged = {f: h for f, h in hedged_figures.items()
               if f not in unhedged_figures}
    if not obliged:
        return []

    failures: list[Failure] = []
    for sentence in split_sentences(strip_hashtags(text)):
        figures = set(NUMBER_RE.findall(sentence))
        hit = sorted(figures & set(obliged))
        if not hit:
            continue
        if keyword_matches(sentence, caption_hedges):
            continue
        hedge_word = obliged[hit[0]]
        failures.append(Failure(
            "dropped_hedge",
            f'Sentence "{sentence}" states {hit} as fact, but the verified '
            f'fact hedges it with "{hedge_word}". Keep the hedge, for example '
            f'with "ditargetkan", "direncanakan" or "sekitar".',
        ))
    return failures


def _check_blocks(text: str, cfg: dict) -> list[Failure]:
    """Short blocks separated by blank lines.

    Measured on run 5: three of the seven passing captions were a single
    unbroken paragraph of 57, 71 and 79 words, which reads as a wall of text
    on Instagram.
    """
    block_cfg = cfg.get("blocks") or {}
    min_blocks = block_cfg.get("min_blocks", 0)
    max_words = block_cfg.get("max_words_per_block", 0)
    if not min_blocks and not max_words:
        return []

    body = strip_hashtags(text).strip()
    blocks = split_blocks(body)
    failures: list[Failure] = []

    if min_blocks and len(blocks) < min_blocks:
        failures.append(Failure(
            "block_structure",
            f"The caption is {len(blocks)} block(s) of text. It needs at "
            f"least {min_blocks}, separated by a blank line, so it does not "
            f"read as a wall of text.",
        ))

    if max_words:
        long_blocks = [(i + 1, len(b.split())) for i, b in enumerate(blocks)
                       if len(b.split()) > max_words]
        if long_blocks:
            detail = ", ".join(f"block {n} has {w} words" for n, w in long_blocks)
            failures.append(Failure(
                "block_too_long",
                f"{detail}. Keep every block to {max_words} words or fewer by "
                f"splitting it with a blank line.",
            ))
    return failures


def format_failures(failures: list[Failure]) -> str:
    """The exact failure list handed back to the generator on retry."""
    return "\n".join(f"- {f}" for f in failures)
