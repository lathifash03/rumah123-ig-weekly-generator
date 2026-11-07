"""Deterministic text helpers shared by the filter, validator and claim check.

Everything here is pure code. No LLM is asked to count, compare or judge.
"""
from __future__ import annotations

import math
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


# Common Indonesian function words and headline filler. Removed before token
# comparison so that overlap reflects the subject, not the grammar.
# Function words, plus the framing words Indonesian headlines use to package a
# story ("kabar", "fakta", "begini"). Those are removed because they appear in
# unrelated headlines every week and say nothing about which story a headline
# covers.
#
# Deliberately NOT removed: words like "orang", "500" or "dijual". They look
# generic, but they are what identifies a story cluster. Removing them dropped
# the Manggarai cluster's similarity score from 1.59 to 1.01 and the cluster
# stopped being detected at all.
_TITLE_STOPWORDS = frozenset("""
di ke dari dan yang untuk pada jadi ada baru masih sudah belum tak nggak
bakal akan juga tapi usai saat begini ini itu dengan atau sih kok para
nya oleh buat bisa mau kini dulu lagi agar karena dalam atas bagi
kabar fakta potret simak catat resmi terkini terbaru nasib asal usul
""".split())


def _title_tokens(title: str) -> set[str]:
    cleaned = normalize_ws(re.sub(r"[^\w\s]", " ", (title or "").lower()))
    return {w for w in cleaned.split()
            if w not in _TITLE_STOPWORDS and len(w) > 2}


def title_similarity(a: str, b: str) -> float:
    """Character-sequence similarity of two normalised titles."""
    from difflib import SequenceMatcher

    na = normalize_ws(re.sub(r"[^\w\s]", " ", (a or "").lower()))
    nb = normalize_ws(re.sub(r"[^\w\s]", " ", (b or "").lower()))
    return SequenceMatcher(None, na, nb).ratio()


def title_token_overlap(a: str, b: str) -> float:
    """Jaccard overlap of the content words of two titles."""
    ta, tb = _title_tokens(a), _title_tokens(b)
    union = ta | tb
    if not union:
        return 0.0
    return len(ta & tb) / len(union)


def _document_frequencies(titles: list[str]) -> dict[str, int]:
    df: dict[str, int] = {}
    for title in titles:
        for token in _title_tokens(title):
            df[token] = df.get(token, 0) + 1
    return df


def story_signature_scorer(titles: list[str], topic_words: set[str]):
    """Build a same-story scorer calibrated on this week's candidate titles.

    Returns a function (a, b) -> (score, shared_tokens).

    Shared words are weighted by rarity, log(N / df), so a word used by most
    of the week's headlines counts for little and a proper noun counts for a
    lot. Topic words are excluded entirely: they are the relevance keywords
    that selected every candidate in the first place, so two headlines sharing
    "harga rumah" or "suku bunga" have shown nothing about being the same
    story.

    Measured on the 43 candidates of 2026-11-07, this is what separates the
    cases. Retellings of one story shared specific words such as "manggarai",
    "senator" or "groundbreaking". The two worst false pairs - an Australian
    house-price story against an Indonesian one, and a UK interest-rate story
    against an Indonesian one - shared only topic words.

    The sum is divided by log(N) so the score does not grow with the size of
    the batch. Without that normalisation a threshold calibrated on a busy
    week silently stops firing on a quiet one, since every individual
    log(N / df) term shrinks as N falls.
    """
    total = max(1, len(titles))
    df = _document_frequencies(titles)
    scale = math.log(total) if total > 1 else 1.0

    def score(a: str, b: str) -> tuple[float, list[str]]:
        shared = (_title_tokens(a) & _title_tokens(b)) - topic_words
        if not shared:
            return 0.0, []
        value = sum(math.log(total / df[tok]) for tok in shared if df.get(tok))
        return value / scale, sorted(shared)

    return score


def titles_are_same_story(
    a: str,
    b: str,
    seq_threshold: float,
    score_threshold: float,
    min_shared: int,
    scorer=None,
) -> tuple[bool, dict]:
    """Whether two headlines cover the same story.

    Two signals, because neither works alone on real headlines:

    - A character-sequence ratio catches near-identical wording. On its own it
      is useless here: genuine retellings reached only about 0.64, so the
      original single threshold of 0.82 deduplicated nothing at all.
    - A rarity-weighted count of shared specific words catches a family of
      retellings worded differently. Nine headlines covered one subsidised
      apartment project in Manggarai and four covered one block in IKN.

    Both a minimum number of shared specific words and a minimum rarity score
    are required, so that one coincidental rare word is not enough.
    """
    seq = title_similarity(a, b)
    score, shared = (0.0, [])
    if scorer is not None:
        score, shared = scorer(a, b)

    by_wording = seq >= seq_threshold
    by_subject = len(shared) >= min_shared and score >= score_threshold
    return (by_wording or by_subject), {
        "sequence_ratio": round(seq, 3),
        "shared_specific_words": shared,
        "rarity_score": round(score, 2),
    }


def slugify(text: str, max_len: int = 48) -> str:
    s = unicodedata.normalize("NFKD", (text or "").lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:max_len].strip("-") or "item"
