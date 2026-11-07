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
    count_emoji,
    hashtags,
    keyword_matches,
    normalize_ws,
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

    return failures


def format_failures(failures: list[Failure]) -> str:
    """The exact failure list handed back to the generator on retry."""
    return "\n".join(f"- {f}" for f in failures)
