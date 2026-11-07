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


# --- same-story detection -----------------------------------------------------

MANGGARAI = [
    "Ada 1.500 Orang Mau Beli Rusun Subsidi Manggarai, Kapan Mulai Dijual?",
    "Belum Resmi Dijual, Rusun Subsidi di Manggarai Sudah Diserbu 1.500 Orang",
    "Fakta Rusun Subsidi Manggarai yang Belum Dibangun tapi Sudah Diburu",
]
OTHERS = [
    "Survei BI: Harga Rumah Naik Tipis, Penjualan Anjlok 8,43 Persen",
    "Harga Rumah di Australia Anjlok 7 Bulan Beruntun",
    "Suku Bunga di Inggris Sentuh 4%, Pertama Kali Naik dalam 3 Tahun",
    "Kondisi Industri Keuangan RI di Tengah Suku Bunga Tinggi",
]
TOPIC_WORDS = {"harga", "rumah", "properti", "suku", "bunga", "kpr", "rusun",
               "subsidi", "hunian", "perumahan", "apartemen", "mbr"}


def test_scorer_ranks_retellings_above_same_topic_pairs():
    titles = MANGGARAI + OTHERS
    score = t.story_signature_scorer(titles, TOPIC_WORDS)
    same_story, _ = score(MANGGARAI[0], MANGGARAI[1])
    diff_country, _ = score(OTHERS[0], OTHERS[1])
    assert same_story > diff_country


def test_topic_words_are_excluded_from_the_score():
    titles = MANGGARAI + OTHERS
    score = t.story_signature_scorer(titles, TOPIC_WORDS)
    value, shared = score(OTHERS[2], OTHERS[3])
    assert "suku" not in shared and "bunga" not in shared


def test_same_story_detected_for_retellings():
    titles = MANGGARAI + OTHERS
    score = t.story_signature_scorer(titles, TOPIC_WORDS)
    same, detail = t.titles_are_same_story(
        MANGGARAI[0], MANGGARAI[1], 0.62, 1.55, 2, score)
    assert same
    assert "manggarai" in detail["shared_specific_words"]


def test_different_stories_on_the_same_topic_are_not_same_story():
    titles = MANGGARAI + OTHERS
    score = t.story_signature_scorer(titles, TOPIC_WORDS)
    same, detail = t.titles_are_same_story(
        OTHERS[0], OTHERS[1], 0.62, 1.55, 2, score)
    assert not same, detail


def test_sequence_signal_alone_can_mark_same_story():
    same, detail = t.titles_are_same_story(
        "Rusun MBR di IKN Sedikit Lagi Selesai, Disewakan atau Dijual?",
        "Rusun MBR di IKN Sedikit Lagi Selesai Disewakan atau Dijual",
        0.62, 1.55, 2, None)
    assert same
    assert detail["sequence_ratio"] >= 0.62


def test_no_scorer_means_only_the_wording_signal():
    same, _ = t.titles_are_same_story(
        MANGGARAI[0], MANGGARAI[1], 0.62, 1.55, 2, None)
    assert not same


def test_token_overlap_ignores_stopwords():
    assert t.title_token_overlap("Rumah di Jakarta", "Rumah untuk Jakarta") == 1.0
