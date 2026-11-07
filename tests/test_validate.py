"""One pass fixture and one fail fixture for every validator rule."""
import pytest

from src.models import Fact
from src.validate import format_failures, validate
from tests.conftest import PASSING_CAPTION

SOURCE = "CNN Indonesia"


def rules_hit(caption, facts, source=SOURCE):
    return {f.rule for f in validate(caption, facts, source)}


# --- the passing fixture ------------------------------------------------------

def test_passing_caption_has_no_failures(facts, passing_caption):
    assert validate(passing_caption, facts, SOURCE) == []


# --- word count ---------------------------------------------------------------

def test_word_count_at_limit_passes(facts):
    # 88 filler words + "CNN Indonesia" = exactly 90, the limit.
    caption = " ".join(["kata"] * 88) + " CNN Indonesia #Rumah123 #KPR"
    from src.textutil import word_count_excluding_hashtags
    assert word_count_excluding_hashtags(caption) == 90
    assert "word_count" not in rules_hit(caption, facts)


def test_word_count_one_over_limit_fails(facts):
    caption = " ".join(["kata"] * 89) + " CNN Indonesia #Rumah123 #KPR"
    from src.textutil import word_count_excluding_hashtags
    assert word_count_excluding_hashtags(caption) == 91
    assert "word_count" in rules_hit(caption, facts)


def test_word_count_over_limit_fails(facts):
    body = " ".join(["kata"] * 120)
    caption = f"{body} CNN Indonesia #Rumah123 #KPR"
    assert "word_count" in rules_hit(caption, facts)


def test_word_count_failure_says_how_many_to_remove(facts):
    caption = " ".join(["kata"] * 100) + " CNN Indonesia #Rumah123 #KPR"
    msg = [f.message for f in validate(caption, facts, SOURCE)
           if f.rule == "word_count"][0]
    assert "102 words" in msg and "remove at least 12" in msg.lower()


# --- hashtags -----------------------------------------------------------------

def test_exactly_two_hashtags_passes(facts, passing_caption):
    assert "hashtag_count" not in rules_hit(passing_caption, facts)


def test_one_hashtag_fails(facts):
    assert "hashtag_count" in rules_hit("CNN Indonesia teks #Rumah123", facts)


def test_three_hashtags_fails(facts):
    assert "hashtag_count" in rules_hit(
        "CNN Indonesia teks #Rumah123 #KPR #Properti", facts)


def test_missing_required_hashtag_fails(facts):
    assert "required_hashtag" in rules_hit("CNN Indonesia teks #KPR #Properti", facts)


def test_duplicate_required_hashtag_fails(facts):
    hit = rules_hit("CNN Indonesia teks #Rumah123 #Rumah123", facts)
    assert "topic_hashtag" in hit


# --- emoji --------------------------------------------------------------------

def test_one_emoji_passes(facts):
    assert "emoji_count" not in rules_hit(
        "CNN Indonesia teks 🏠 #Rumah123 #KPR", facts)


def test_zero_emoji_passes(facts, passing_caption):
    assert "emoji_count" not in rules_hit(passing_caption, facts)


def test_two_emoji_fails(facts):
    assert "emoji_count" in rules_hit(
        "CNN Indonesia teks 🏠 😊 #Rumah123 #KPR", facts)


# --- forbidden characters -----------------------------------------------------

def test_em_dash_fails(facts):
    assert "em_dash" in rules_hit("CNN Indonesia teks — lagi #Rumah123 #KPR", facts)


def test_no_em_dash_passes(facts, passing_caption):
    assert "em_dash" not in rules_hit(passing_caption, facts)


def test_semicolon_fails(facts):
    assert "semicolon" in rules_hit("CNN Indonesia teks; lagi #Rumah123 #KPR", facts)


def test_no_semicolon_passes(facts, passing_caption):
    assert "semicolon" not in rules_hit(passing_caption, facts)


# --- banned phrases -----------------------------------------------------------

@pytest.mark.parametrize("phrase", [
    "buruan", "dijamin", "gratis", "cuan", "termurah",
    "jangan sampai ketinggalan", "klik link di bio",
])
def test_each_banned_phrase_fails(facts, phrase):
    assert "banned_phrase" in rules_hit(
        f"CNN Indonesia {phrase} teks #Rumah123 #KPR", facts)


def test_banned_phrase_is_case_insensitive(facts):
    assert "banned_phrase" in rules_hit(
        "CNN Indonesia BURUAN teks #Rumah123 #KPR", facts)


def test_clean_caption_has_no_banned_phrase(facts, passing_caption):
    assert "banned_phrase" not in rules_hit(passing_caption, facts)


def test_banned_phrase_message_lists_the_hits(facts):
    msg = [f.message for f in validate(
        "CNN Indonesia buruan dijamin #Rumah123 #KPR", facts, SOURCE)
        if f.rule == "banned_phrase"][0]
    assert "buruan" in msg and "dijamin" in msg


# --- source attribution -------------------------------------------------------

def test_source_present_passes(facts, passing_caption):
    assert "missing_source" not in rules_hit(passing_caption, facts)


def test_source_absent_fails(facts):
    assert "missing_source" in rules_hit("teks tanpa sumber #Rumah123 #KPR", facts)


def test_source_match_is_case_insensitive(facts):
    assert "missing_source" not in rules_hit(
        "menurut cnn indonesia #Rumah123 #KPR", facts)


# --- number grounding ---------------------------------------------------------

def test_grounded_numbers_pass(facts):
    assert "ungrounded_number" not in rules_hit(
        "CNN Indonesia naik 8,43 persen dan 5,25 persen #Rumah123 #KPR", facts)


def test_invented_number_fails(facts):
    assert "ungrounded_number" in rules_hit(
        "CNN Indonesia naik 99 persen #Rumah123 #KPR", facts)


def test_rounded_number_fails(facts):
    """8 is a rounding of the verified 8,43 and must still fail."""
    assert "ungrounded_number" in rules_hit(
        "CNN Indonesia naik 8 persen #Rumah123 #KPR", facts)


def test_brand_digits_do_not_count_as_a_number(facts):
    assert "ungrounded_number" not in rules_hit(
        "CNN Indonesia lihat di Rumah123 #Rumah123 #KPR", facts)


def test_ungrounded_number_message_names_the_number(facts):
    msg = [f.message for f in validate(
        "CNN Indonesia naik 77 persen #Rumah123 #KPR", facts, SOURCE)
        if f.rule == "ungrounded_number"][0]
    assert "77" in msg


# --- multiple failures and formatting ----------------------------------------

def test_multiple_failures_all_reported(facts):
    caption = "Buruan; dijamin — naik 99 persen 🏠😊 #Rumah123 #Rumah123"
    hit = rules_hit(caption, facts)
    for rule in ["topic_hashtag", "emoji_count", "em_dash", "semicolon",
                 "banned_phrase", "missing_source", "ungrounded_number"]:
        assert rule in hit, f"expected {rule} in {hit}"


def test_format_failures_is_a_bullet_list(facts):
    out = format_failures(validate("teks", facts, SOURCE))
    assert out.startswith("- [")
    assert "\n" in out


def test_empty_caption_fails_several_rules(facts):
    assert len(validate("", facts, SOURCE)) >= 3


def test_no_facts_means_any_number_is_ungrounded():
    assert "ungrounded_number" in {
        f.rule for f in validate(
            "CNN Indonesia naik 5 persen #Rumah123 #KPR", [], SOURCE)}


# --- regression guards --------------------------------------------------------

def test_acuan_is_not_flagged_as_the_banned_word_cuan(facts):
    """Regression: a substring search flagged "cuan" inside "suku bunga acuan",
    a legitimate central-bank term."""
    caption = ("CNN Indonesia menahan suku bunga acuan di 5,25 persen "
               "#Rumah123 #KPR")
    assert "banned_phrase" not in rules_hit(caption, facts)


def test_cuan_as_its_own_word_is_still_flagged(facts):
    caption = "CNN Indonesia cari cuan cepat #Rumah123 #KPR"
    assert "banned_phrase" in rules_hit(caption, facts)


def test_banned_word_as_a_prefix_of_another_word_is_not_flagged(facts):
    """Boundary matching means "gratis" does not fire inside "gratisan"."""
    assert "banned_phrase" not in rules_hit(
        "CNN Indonesia gratisan bukan istilah itu #Rumah123 #KPR", facts)


def test_gratis_as_its_own_word_is_flagged(facts):
    assert "banned_phrase" in rules_hit(
        "CNN Indonesia biaya gratis untuk kamu #Rumah123 #KPR", facts)


# --- en dash ------------------------------------------------------------------

EN_DASH = "–"


def test_en_dash_as_a_separator_fails(facts):
    caption = f"CNN Indonesia teks {EN_DASH} lanjut #Rumah123 #KPR"
    assert "en_dash" in rules_hit(caption, facts)


def test_en_dash_with_space_on_one_side_fails(facts):
    caption = f"CNN Indonesia teks{EN_DASH} lanjut #Rumah123 #KPR"
    assert "en_dash" in rules_hit(caption, facts)


def test_en_dash_in_a_numeric_range_is_allowed(facts):
    """A range like 2024-2025 is not a dash used as punctuation."""
    caption = f"CNN Indonesia periode 2024{EN_DASH}2025 #Rumah123 #KPR"
    assert "en_dash" not in rules_hit(caption, facts)


def test_clean_caption_has_no_en_dash(facts, passing_caption):
    assert "en_dash" not in rules_hit(passing_caption, facts)


# --- figures written as words -------------------------------------------------

def test_number_word_rounding_fails(facts):
    """The facts say 8,43 percent. "delapan persen" is a rounding."""
    caption = "CNN Indonesia naik delapan persen #Rumah123 #KPR"
    assert "ungrounded_number_word" in rules_hit(caption, facts)


def test_number_word_matching_the_facts_passes(facts):
    caption = "CNN Indonesia suku bunga lima koma dua lima persen #Rumah123 #KPR"
    assert "ungrounded_number_word" not in rules_hit(caption, facts)


def test_dua_kali_lipat_without_support_fails(facts):
    caption = "CNN Indonesia harga naik dua kali lipat #Rumah123 #KPR"
    assert "ungrounded_number_word" in rules_hit(caption, facts)


def test_salah_satu_is_not_treated_as_a_figure(facts):
    caption = "CNN Indonesia salah satu pilihan untuk kamu #Rumah123 #KPR"
    assert "ungrounded_number_word" not in rules_hit(caption, facts)


def test_number_word_failure_names_the_phrase(facts):
    caption = "CNN Indonesia naik delapan persen #Rumah123 #KPR"
    msg = [f.message for f in validate(caption, facts, SOURCE)
           if f.rule == "ungrounded_number_word"][0]
    assert "delapan persen" in msg
