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


# --- Indonesian number words --------------------------------------------------
# A caption can make a numeric claim without writing a digit.

WORD_FACTS = ("harga rumah naik 8,43 persen, tersedia 2 juta unit, "
              "tenor 12 bulan, suku bunga 5,25 persen")


@pytest.mark.parametrize("text,phrase,value", [
    ("naik delapan persen", "delapan persen", 8.0),
    ("naik sepuluh persen", "sepuluh persen", 10.0),
    ("sebelas persen", "sebelas persen", 11.0),
    ("dua belas bulan", "dua belas bulan", 12.0),
    ("dua puluh lima persen", "dua puluh lima persen", 25.0),
    ("dua kali lipat", "dua kali lipat", 2.0),
    ("dua juta unit", "dua juta unit", 2_000_000.0),
    ("setengah juta", "setengah juta", 500_000.0),
    ("delapan koma empat tiga persen", "delapan koma empat tiga persen", 8.43),
])
def test_indonesian_number_words_are_parsed(text, phrase, value):
    claims = t.number_word_claims(text)
    assert claims, f"nothing detected in {text!r}"
    assert claims[0][0] == phrase
    assert claims[0][1] == pytest.approx(value)


def test_number_word_without_a_measure_word_is_not_a_quantity():
    """Regression guard: "salah satu bank" must not be read as the number one,
    or every caption containing the phrase would fail grounding."""
    assert t.number_word_claims("salah satu bank terbesar di Indonesia") == []


def test_delapan_persen_is_not_grounded_by_a_fact_of_8_43():
    """A figure written in words is still a rounding."""
    assert t.ungrounded_number_words("naik delapan persen", WORD_FACTS) == \
        ["delapan persen"]


def test_number_word_matching_a_fact_exactly_is_grounded():
    assert t.ungrounded_number_words("tenor dua belas bulan", WORD_FACTS) == []


def test_number_word_with_scale_matches_a_digit_fact():
    """The facts write "2 juta unit"; the caption writes "dua juta unit"."""
    assert t.ungrounded_number_words("tersedia dua juta unit", WORD_FACTS) == []


def test_dua_kali_lipat_is_not_grounded_by_an_unrelated_two():
    """The facts contain "2 juta unit". A doubling claim is a different unit
    and must not borrow that number."""
    assert t.ungrounded_number_words("naik dua kali lipat", WORD_FACTS) == \
        ["dua kali lipat"]


def test_unit_class_must_match():
    """12 appears in the facts as months, so 12 percent is not grounded."""
    assert t.ungrounded_number_words("naik dua belas persen", WORD_FACTS) == \
        ["dua belas persen"]


def test_number_words_in_the_facts_ground_a_digit_free_caption():
    facts = "harga naik delapan persen menurut laporan itu"
    assert t.ungrounded_number_words("naik delapan persen", facts) == []


# --- number format variants ---------------------------------------------------
# The same figure written different ways is the same figure.

VARIANT_FACTS = ("harga rumah naik 8,43 persen, suku bunga 5,25 persen, "
                 "nilai transaksi Rp 1,2 miliar, indeks 5.050")


@pytest.mark.parametrize("caption", [
    "naik 8,43 persen",
    "naik 8.43 persen",
    "naik 8,43%",
    "suku bunga 5,25%",
    "suku bunga 5,25 persen",
    "senilai Rp 1,2 miliar",
    "senilai Rp1,2 miliar",
    "indeks 5.050",
    "indeks 5050",
])
def test_format_variants_count_as_grounded(caption):
    assert t.ungrounded_numbers(caption, VARIANT_FACTS) == [], caption


def test_numeric_interpretations_of_a_decimal_comma():
    assert t._numeric_interpretations("8,43") == {8.43}


def test_numeric_interpretations_of_a_dot_give_both_readings():
    """"5.050" is five thousand and fifty, but a dot is also how a decimal
    gets mistyped, so both readings are kept."""
    assert t._numeric_interpretations("5.050") == {5050.0, 5.05}


def test_different_figure_is_still_ungrounded_across_formats():
    assert t.ungrounded_numbers("naik 9,99 persen", VARIANT_FACTS) == ["9,99"]


# --- emoji grapheme clusters --------------------------------------------------

ZWJ = "‍"
VS16 = "️"


@pytest.mark.parametrize("name,text,expected", [
    ("plain pictograph", "\U0001F3E0", 1),
    ("variation selector 16", "❤" + VS16, 1),
    ("ZWJ family of three", "\U0001F468" + ZWJ + "\U0001F469" + ZWJ + "\U0001F467", 1),
    ("ZWJ couple with heart", "\U0001F469" + ZWJ + "❤" + VS16 + ZWJ + "\U0001F468", 1),
    ("skin tone modifier", "\U0001F44D\U0001F3FD", 1),
    ("regional indicator flag", "\U0001F1EE\U0001F1E9", 1),
    ("two flags", "\U0001F1EE\U0001F1E9\U0001F1FA\U0001F1F8", 2),
    ("combining keycap", "1" + VS16 + "⃣", 1),
    ("pictograph plus flag", "\U0001F3E0\U0001F1EE\U0001F1E9", 2),
    ("two distinct pictographs", "\U0001F3E0\U0001F60A", 2),
    ("no emoji", "tanpa emoji 123 dan %", 0),
])
def test_emoji_cluster_counting(name, text, expected):
    assert t.count_emoji(text) == expected, name


def test_flag_is_one_emoji_not_two_codepoints():
    """Regression: counting raw codepoints reported a flag as two emoji, so a
    caption with one flag failed the max-one-emoji rule."""
    assert t.count_emoji("\U0001F1EE\U0001F1E9") == 1


# --- coverage key -------------------------------------------------------------

def test_coverage_key_ignores_punctuation_and_spacing():
    assert t.coverage_key("Halo,  dunia! Ya.") == t.coverage_key("halo dunia ya")


def test_coverage_key_ignores_hashtags():
    assert t.coverage_key("Halo #Rumah123 #KPR") == t.coverage_key("Halo")


def test_coverage_key_detects_a_missing_word():
    assert t.coverage_key("halo dunia ya") != t.coverage_key("halo dunia")


def test_coverage_key_keeps_digits():
    assert t.coverage_key("naik 8,43 persen") == "naik843persen"
