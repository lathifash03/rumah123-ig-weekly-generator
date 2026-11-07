"""Deterministic text helpers shared by the filter, validator and claim check.

Everything here is pure code. No LLM is asked to count, compare or judge.
"""
from __future__ import annotations

import re
import unicodedata

# --- whitespace normalisation -------------------------------------------------

_WS = re.compile(r"\s+")


def normalize_ws(text: str) -> str:
    """Collapse all whitespace runs to one space and strip the ends.

    Quote verification compares normalised strings so that a line break in the
    fetched article does not break an otherwise exact quote.
    """
    return _WS.sub(" ", (text or "").replace(" ", " ")).strip()


def quote_is_grounded(quote: str, source_text: str) -> bool:
    """True when quote appears in source_text, comparing on normalised
    whitespace. This is the deterministic check that replaces trusting the
    model's claim that it copied something."""
    q = normalize_ws(quote)
    if len(q) < 5:
        return False
    return q in normalize_ws(source_text)


# --- hashtags -----------------------------------------------------------------

HASHTAG_RE = re.compile(r"#\w+", re.UNICODE)


def hashtags(caption: str) -> list[str]:
    return HASHTAG_RE.findall(caption or "")


def strip_hashtags(caption: str) -> str:
    return HASHTAG_RE.sub(" ", caption or "")


# --- word count ---------------------------------------------------------------


def word_count_excluding_hashtags(caption: str) -> int:
    """Count whitespace separated tokens after removing hashtags.

    The counting rule lives in code because an LLM asked to self-report a word
    count gets it wrong: in earlier prompt-engineering work the model reported
    79 words for a caption that was actually about 89.
    """
    return len([t for t in strip_hashtags(caption).split() if t.strip()])


# --- emoji --------------------------------------------------------------------

_EMOJI_RANGES = (
    (0x1F300, 0x1FAFF),  # pictographs, emoticons, symbols, supplemental
    (0x1F000, 0x1F2FF),  # mahjong, dominoes, enclosed alphanumerics
    (0x2600, 0x27BF),    # misc symbols and dingbats
    (0x2B00, 0x2BFF),    # arrows and misc symbols
    (0xFE0F, 0xFE0F),    # variation selector-16
    (0x1F1E6, 0x1F1FF),  # regional indicators (flags)
)


def _is_emoji_codepoint(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES)


def count_emoji(text: str) -> int:
    """Count emoji, treating a ZWJ sequence or a flag pair as one emoji."""
    chars = list(text or "")
    count = 0
    i = 0
    while i < len(chars):
        if _is_emoji_codepoint(chars[i]):
            count += 1
            i += 1
            # swallow the rest of one grapheme cluster: modifiers, variation
            # selectors, and ZWJ-joined parts
            while i < len(chars):
                ch = chars[i]
                if ch == "‍":  # ZWJ, next codepoint belongs to this emoji
                    i += 2
                    continue
                if _is_emoji_codepoint(ch) or unicodedata.combining(ch):
                    # a following regional indicator or skin-tone modifier
                    if 0x1F3FB <= ord(ch) <= 0x1F3FF or ord(ch) == 0xFE0F:
                        i += 1
                        continue
                    break
                break
        else:
            i += 1
    return count


# --- numbers ------------------------------------------------------------------

# Matches 8, 8,43, 5.050, 2026, 7.5 - Indonesian uses "," as the decimal mark
# and "." as the thousands separator, so both are kept as part of one number.
NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")


def strip_tokens(text: str, tokens: tuple[str, ...] | list[str]) -> str:
    """Remove the given literal tokens, case-insensitively."""
    out = text or ""
    for tok in tokens:
        if tok:
            out = re.sub(re.escape(tok), " ", out, flags=re.I)
    return out


def numbers_in(text: str, ignore_tokens: tuple[str, ...] | list[str] = ()) -> list[str]:
    """Every number literal in text, with hashtags and brand tokens removed.

    Both removals are needed. "#Rumah123" is a hashtag, but "Rumah123" also
    appears in the caption body as the brand name, and in both cases the "123"
    is part of a name rather than a factual claim.
    """
    cleaned = strip_tokens(strip_hashtags(text or ""), ignore_tokens)
    return NUMBER_RE.findall(cleaned)


def _number_variants(num: str) -> set[str]:
    """Forms of a number literal that count as the same figure.

    Indonesian writes "." for thousands and "," for decimals. "5.050" and
    "5050" are the same figure, and "8,43" may be written "8.43".

    Deliberately does NOT strip "," - that would turn "8,43" into "843" and
    let an unrelated figure match.
    """
    return {num, num.replace(".", ""), num.replace(",", ".")}


def ungrounded_numbers(
    caption: str,
    facts_text: str,
    ignore_tokens: tuple[str, ...] | list[str] = (),
) -> list[str]:
    """Numbers in the caption that do not appear in the verified facts.

    Compares COMPLETE numeric tokens, not substrings. A substring comparison
    let "8 persen" pass against a fact saying "8,43 persen", because "8" is a
    substring of "8,43" - so a plausible rounding of a real figure slipped
    through grounding. Rounding a verified figure is a failure.

    ignore_tokens carries brand names whose digits belong to the name, such as
    Rumah123.
    """
    fact_forms: set[str] = set()
    for num in NUMBER_RE.findall(normalize_ws(facts_text)):
        fact_forms |= _number_variants(num)

    missing, seen = [], set()
    for num in numbers_in(caption, ignore_tokens):
        if _number_variants(num) & fact_forms:
            continue
        if num not in seen:
            seen.add(num)
            missing.append(num)
    return missing


# --- keyword matching ---------------------------------------------------------


def keyword_matches(text: str, keywords: list[str]) -> list[str]:
    """Keywords present in text, matched case-insensitively on word boundaries.

    Boundary matching rather than substring: a plain "mbr" substring search
    fired on unrelated finance headlines during feed verification.
    """
    low = (text or "").lower()
    hits = []
    for kw in keywords:
        pattern = r"(?<!\w)" + re.escape(kw.lower()) + r"(?!\w)"
        if re.search(pattern, low):
            hits.append(kw)
    return hits


def title_similarity(a: str, b: str) -> float:
    """Token-set similarity of two titles, for near-duplicate detection."""
    from difflib import SequenceMatcher

    na = normalize_ws(re.sub(r"[^\w\s]", " ", (a or "").lower()))
    nb = normalize_ws(re.sub(r"[^\w\s]", " ", (b or "").lower()))
    return SequenceMatcher(None, na, nb).ratio()


def slugify(text: str, max_len: int = 48) -> str:
    s = unicodedata.normalize("NFKD", (text or "").lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:max_len].strip("-") or "item"
