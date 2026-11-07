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


def _is_regional_indicator(ch: str) -> bool:
    return 0x1F1E6 <= ord(ch) <= 0x1F1FF


ZERO_WIDTH_JOINER = "\u200d"


def count_emoji(text: str) -> int:
    """Count emoji as a reader sees them, one grapheme cluster at a time.

    A flag is two regional indicators, a family is several people joined by
    zero-width joiners, and a red heart is a symbol plus variation selector
    16. Each is one emoji on screen, so each counts once. Counting raw
    codepoints instead reported a flag as two emoji.
    """
    chars = list(text or "")
    count = 0
    i = 0
    n = len(chars)
    while i < n:
        ch = chars[i]
        if not _is_emoji_codepoint(ch):
            i += 1
            continue

        count += 1

        # A flag is exactly a pair of regional indicators.
        if _is_regional_indicator(ch):
            i += 1
            if i < n and _is_regional_indicator(chars[i]):
                i += 1
            continue

        i += 1
        # Absorb the rest of this cluster: skin-tone modifiers, variation
        # selectors, combining marks, keycap enclosures, and anything joined
        # on with a zero-width joiner.
        while i < n:
            cp = ord(chars[i])
            if chars[i] == ZERO_WIDTH_JOINER:
                i += 1
                if i < n:
                    i += 1
                continue
            if (0x1F3FB <= cp <= 0x1F3FF          # skin tone modifier
                    or cp in (0xFE0F, 0xFE0E)     # variation selectors
                    or cp == 0x20E3               # combining enclosing keycap
                    or unicodedata.combining(chars[i])):
                i += 1
                continue
            break
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


def _numeric_interpretations(num: str) -> set[float]:
    """Every plausible value of a number literal, as Indonesian writes them.

    "8,43" is eight point four three, because a comma is the decimal mark.
    "5.050" is five thousand and fifty, because a dot groups thousands, but a
    dot is also how a decimal gets written by a careless hand, so a dot
    yields both readings rather than one guessed reading.
    """
    out: set[float] = set()
    if "," in num:
        try:
            out.add(float(num.replace(".", "").replace(",", ".")))
        except ValueError:
            pass
        return out
    if "." in num:
        for candidate in (num.replace(".", ""), num):
            try:
                out.add(float(candidate))
            except ValueError:
                pass
        return out
    try:
        out.add(float(num))
    except ValueError:
        pass
    return out


# --- Indonesian number words -------------------------------------------------
# A caption can make a numeric claim without writing a digit: "naik delapan
# persen" is as much a figure as "naik 8 persen". Grounding has to see those.

_ID_SMALL = {
    "nol": 0, "kosong": 0, "satu": 1, "dua": 2, "tiga": 3, "empat": 4,
    "lima": 5, "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9,
    "sepuluh": 10, "sebelas": 11,
}
_ID_SCALE = {
    "puluh": 10, "ratus": 100, "seratus": 100, "ribu": 1000, "seribu": 1000,
    "juta": 10 ** 6, "miliar": 10 ** 9, "milyar": 10 ** 9,
    "triliun": 10 ** 12,
}
_ID_FRACTION = {"setengah": 0.5, "separuh": 0.5, "seperempat": 0.25}

# A run of number words is only read as a quantity when a measure word is
# attached. Without this rule "salah satu bank" would be reported as the
# number one, and every caption containing it would fail grounding.
_ID_MEASURE_WORDS = frozenset("""
persen kali lipat unit rumah tahun bulan hari pekan minggu kuartal
rupiah ribu juta miliar milyar triliun meter hektare hektar orang
poin basis
""".split())

_ID_NUMBER_TOKEN = (
    set(_ID_SMALL) | set(_ID_SCALE) | set(_ID_FRACTION) | {"belas", "koma"}
)


def _parse_id_number(tokens: list[str]) -> float | None:
    """Value of a run of Indonesian number words, or None if it does not parse.

    Covers the forms that appear in captions: "delapan", "dua belas",
    "dua puluh lima", "seratus", "dua juta", "delapan koma empat tiga".
    """
    if not tokens:
        return None
    if len(tokens) == 1 and tokens[0] in _ID_FRACTION:
        return _ID_FRACTION[tokens[0]]

    total = 0.0
    current = 0.0
    seen_any = False
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "koma":
            digits = []
            i += 1
            while i < len(tokens) and tokens[i] in _ID_SMALL:
                digits.append(str(_ID_SMALL[tokens[i]]))
                i += 1
            if not digits or not seen_any:
                return None
            base = total + current
            try:
                return float(f"{base:.0f}." + "".join(digits))
            except ValueError:
                return None
        if tok == "belas":
            if current == 0:
                return None
            current += 10
            seen_any = True
            i += 1
            continue
        if tok in _ID_FRACTION:
            current += _ID_FRACTION[tok]
            seen_any = True
            i += 1
            continue
        if tok in _ID_SCALE:
            scale = _ID_SCALE[tok]
            if scale >= 1000:
                total = (total + (current or 1)) * scale
                current = 0.0
            else:
                current = (current or 1) * scale
            seen_any = True
            i += 1
            continue
        if tok in _ID_SMALL:
            current += _ID_SMALL[tok]
            seen_any = True
            i += 1
            continue
        return None
    return (total + current) if seen_any else None


# Scale words multiply the number in front of them: "2 juta", "dua juta",
# "Rp 1,2 miliar".
_SCALE_MULTIPLIER = {
    "ribu": 10 ** 3, "juta": 10 ** 6, "miliar": 10 ** 9,
    "milyar": 10 ** 9, "triliun": 10 ** 12,
}

# The unit a quantity is measured in, collapsed into classes. A value without
# its unit is not comparable: "2 juta unit" and "dua kali lipat" both reduce
# to the number two, but one is a count of homes and the other is a doubling.
_MEASURE_CLASS = {
    "persen": "percent", "perseratus": "percent",
    "kali": "multiplier", "lipat": "multiplier",
    "unit": "count", "rumah": "count", "orang": "count", "jiwa": "count",
    "tahun": "time", "bulan": "time", "hari": "time", "pekan": "time",
    "minggu": "time", "kuartal": "time",
    "rupiah": "money",
    "meter": "area", "hektare": "area", "hektar": "area",
    "poin": "points", "basis": "points",
}


def _measure_class(word: str) -> str:
    return _MEASURE_CLASS.get(word, "")


def _tokenize_quantities(text: str) -> list[str]:
    return re.findall(r"\d+(?:[.,]\d+)*|[a-z]+|%", text.lower())


def quantity_claims(
    text: str,
    ignore_tokens: tuple[str, ...] | list[str] = (),
    words_only: bool = False,
) -> list[tuple[str, frozenset, str]]:
    """Quantities in text as (phrase, possible values, measure class).

    Handles digits ("8,43 persen", "2 juta unit", "Rp 1,2 miliar"), Indonesian
    number words ("delapan persen", "dua kali lipat"), and the mixture of a
    digit with a scale word. words_only restricts the scan to number words,
    which is what the number-word grounding rule checks in a caption.

    A value carries its measure class because a bare value is not comparable.
    Grounding "dua kali lipat" against a fact mentioning "2 juta unit" would
    otherwise pass, since both reduce to two.
    """
    cleaned = strip_tokens(strip_hashtags(text or ""), ignore_tokens)
    tokens = _tokenize_quantities(cleaned)
    out: list[tuple[str, frozenset, str]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        values: set[float] | None = None
        phrase_parts: list[str] = []

        if not words_only and NUMBER_RE.fullmatch(tok):
            values = set(_numeric_interpretations(tok))
            phrase_parts = [tok]
            i += 1
        elif tok in _ID_NUMBER_TOKEN and tok not in ("koma", "belas"):
            j = i
            run: list[str] = []
            while j < len(tokens) and tokens[j] in _ID_NUMBER_TOKEN:
                run.append(tokens[j])
                j += 1
            # A bare scale word is not a quantity. The first real run
            # reported "juta" in "ratusan juta" as the number one million.
            if all(tok in _SCALE_MULTIPLIER or tok in _ID_SCALE for tok in run):
                i = max(j, i + 1)
                continue
            parsed = _parse_id_number(run)
            if parsed is None:
                i = max(j, i + 1)
                continue
            values = {parsed}
            phrase_parts = list(run)
            i = j
        else:
            i += 1
            continue

        # an optional scale word multiplies the value
        if i < len(tokens) and tokens[i] in _SCALE_MULTIPLIER:
            # "dua juta" already consumed "juta" as part of the word run
            if tokens[i] not in phrase_parts:
                mult = _SCALE_MULTIPLIER[tokens[i]]
                values = {v * mult for v in values}
                phrase_parts.append(tokens[i])
                i += 1

        # an optional measure word names the unit
        measure = ""
        if i < len(tokens):
            nxt = tokens[i]
            if nxt == "%":
                measure = "percent"
                phrase_parts.append("%")
                i += 1
            elif _measure_class(nxt):
                measure = _measure_class(nxt)
                phrase_parts.append(nxt)
                i += 1
                # "dua kali lipat": absorb the second half of the unit
                if (i < len(tokens) and _measure_class(tokens[i]) == measure
                        and tokens[i] != nxt):
                    phrase_parts.append(tokens[i])
                    i += 1

        if words_only and measure == "" and not any(
                part in _SCALE_MULTIPLIER for part in phrase_parts):
            # a bare number word with no unit is not a quantitative claim
            continue

        out.append((" ".join(phrase_parts), frozenset(values), measure))
    return out


def number_word_claims(
    text: str,
    ignore_tokens: tuple[str, ...] | list[str] = (),
) -> list[tuple[str, float]]:
    """Indonesian number-word quantities as (phrase, value)."""
    return [
        (phrase, min(values))
        for phrase, values, _ in quantity_claims(text, ignore_tokens,
                                                 words_only=True)
    ]


def ungrounded_number_words(
    caption: str,
    facts_text: str,
    ignore_tokens: tuple[str, ...] | list[str] = (),
) -> list[str]:
    """Number-word quantities in the caption that the facts do not state.

    A phrase is grounded when the facts give the same value in the same unit,
    written either as digits or in words. "naik delapan persen" against a fact
    of "8,43 persen" is not grounded: it is a rounding, and rounding a
    verified figure is what these rules exist to catch.
    """
    fact_claims = quantity_claims(facts_text, ignore_tokens)

    missing, seen = [], set()
    for phrase, values, measure in quantity_claims(caption, ignore_tokens,
                                                   words_only=True):
        grounded = any(
            measure == fact_measure and values & fact_values
            for _, fact_values, fact_measure in fact_claims
        )
        if grounded or phrase in seen:
            continue
        seen.add(phrase)
        missing.append(phrase)
    return missing


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


def coverage_key(text: str) -> str:
    """Letters and digits only, lowercased, for checking that a list of
    sentences covers a caption completely.

    Punctuation and whitespace are discarded so a model splitting a caption
    into sentences is not failed for re-spacing it or dropping a comma, while
    any skipped, reordered or invented word still changes the key.
    """
    return re.sub(r"[^0-9a-z]+", "", strip_hashtags(text or "").lower())


# --- sentence splitting -------------------------------------------------------

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    """Split a caption into sentences, deterministically.

    Splits on a blank line, a single newline and sentence-ending punctuation.
    Used by the hedge rule to decide which sentence carries which figure, so
    it has to be code rather than something the model reports.
    """
    out: list[str] = []
    for line in (text or "").replace("\r", "").split("\n"):
        line = line.strip()
        if not line:
            continue
        for part in _SENTENCE_END.split(line):
            part = part.strip()
            if part:
                out.append(part)
    return out


def split_blocks(text: str) -> list[str]:
    """Blank-line separated blocks of a caption."""
    return [b.strip() for b in re.split(r"\n\s*\n", (text or "").strip())
            if b.strip()]
