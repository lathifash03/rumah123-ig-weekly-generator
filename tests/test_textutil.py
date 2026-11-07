"""Deterministic text rules: quote verification, number grounding, counting."""
import pytest

from src import textutil as t


# --- word counting ------------------------------------------------------------

def test_word_count_excludes_hashtags():
    assert t.word_count_excluding_hashtags("satu dua tiga #Rumah123 #KPR") == 3


def test_word_count_counts_whitespace_tokens():
    assert t.word_count_excluding_hashtags("a b  c\nd\te") == 5


def test_word_count_empty():
    assert t.word_count_excluding_hashtags("") == 0


def test_word_count_is_not_fooled_by_newlines_between_blocks():
    caption = "Hook di sini.\n\nPoin kedua.\n\n#Rumah123 #KPR"
    assert t.word_count_excluding_hashtags(caption) == 5


# --- quote substring verification --------------------------------------------

def test_quote_grounded_exact():
    assert t.quote_is_grounded("harga rumah naik", "Survei: harga rumah naik tipis")


def test_quote_grounded_across_newlines_and_double_spaces():
    source = "Survei BI:  harga rumah\n   naik 8,43 persen"
    assert t.quote_is_grounded("harga rumah naik 8,43 persen", source)


def test_quote_grounded_with_nbsp_in_source():
    assert t.quote_is_grounded("harga rumah naik", "harga rumah naik tipis")


def test_quote_not_grounded_when_paraphrased():
    assert not t.quote_is_grounded("harga rumah turun", "harga rumah naik tipis")


def test_quote_not_grounded_when_absent():
    assert not t.quote_is_grounded("suku bunga 10 persen", "harga rumah naik")


def test_quote_too_short_is_rejected():
    assert not t.quote_is_grounded("abc", "abc def")


# --- number grounding ---------------------------------------------------------

FACTS = "harga rumah naik 8,43 persen ke level 5.050 pada 2026"


def test_numbers_extracted_with_separators():
    assert t.numbers_in("naik 8,43 persen ke 5.050 pada 2026") == ["8,43", "5.050", "2026"]


def test_grounded_numbers_pass():
    assert t.ungrounded_numbers("naik 8,43 persen pada 2026", FACTS) == []


def test_ungrounded_number_is_caught():
    assert t.ungrounded_numbers("naik 99 persen", FACTS) == ["99"]


def test_rounded_number_is_still_ungrounded():
    """A plausible rounding of a real figure is not grounded."""
    assert t.ungrounded_numbers("naik 8 persen", FACTS) == ["8"]


def test_thousands_separator_variant_counts_as_grounded():
    assert t.ungrounded_numbers("level 5050", FACTS) == []


def test_decimal_separator_variant_counts_as_grounded():
    assert t.ungrounded_numbers("naik 8.43 persen", FACTS) == []


def test_hashtag_digits_are_not_treated_as_claims():
    assert t.ungrounded_numbers("teks #Rumah123", FACTS) == []


def test_brand_token_digits_in_body_are_not_treated_as_claims():
    """Rumah123 appears in prose, not only as a hashtag."""
    assert t.ungrounded_numbers("Di Rumah123 kamu bisa lihat", FACTS,
                                ignore_tokens=["Rumah123"]) == []


def test_brand_token_not_ignored_without_config_is_reported():
    """Guard the fix: without the brand token the 123 is reported."""
    assert t.ungrounded_numbers("Di Rumah123 kamu bisa lihat", FACTS) == ["123"]


def test_ungrounded_numbers_deduplicated_in_order():
    assert t.ungrounded_numbers("77 lalu 88 lalu 77", FACTS) == ["77", "88"]


# --- emoji --------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("tanpa emoji", 0),
    ("rumah 🏠 impian", 1),
    ("🏠 dan 😊", 2),
    ("✨ sparkle", 1),
    ("angka 123 dan tanda %", 0),
])
def test_emoji_counts(text, expected):
    assert t.count_emoji(text) == expected


# --- keyword boundary matching -----------------------------------------------

KW = ["mbr", "properti", "kpr", "suku bunga"]


def test_keyword_matches_on_boundary():
    assert t.keyword_matches("Rusun MBR di IKN", KW) == ["mbr"]


def test_keyword_does_not_match_inside_another_token():
    """The bug this guards: a substring search for 'mbr' fired on unrelated
    finance headlines during feed verification."""
    assert t.keyword_matches("IHSG ditutup menguat ke 5.050 Desember", KW) == []


def test_keyword_multiword_phrase_matches():
    assert "suku bunga" in t.keyword_matches("BI tahan suku bunga acuan", KW)


def test_keyword_case_insensitive():
    assert t.keyword_matches("Pasar PROPERTI melemah", KW) == ["properti"]


def test_keyword_no_partial_prefix():
    assert t.keyword_matches("properties abroad", KW) == []


# --- misc ---------------------------------------------------------------------

def test_title_similarity_detects_near_duplicates():
    a = "Rusun MBR di IKN Sedikit Lagi Selesai, Disewakan atau Dijual?"
    b = "Rusun MBR di IKN Sedikit Lagi Selesai Disewakan atau Dijual"
    assert t.title_similarity(a, b) >= 0.82


def test_title_similarity_distinguishes_different_stories():
    a = "Survei BI: Harga Rumah Naik Tipis"
    b = "Rusun MBR di IKN Tipe 36"
    assert t.title_similarity(a, b) < 0.82


def test_slugify():
    assert t.slugify("Survei BI: Harga Rumah Naik 8,43%") == "survei-bi-harga-rumah-naik-8-43"
