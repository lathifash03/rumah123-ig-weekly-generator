"""Rules 10 to 12: superlatives, dropped hedges and block structure.

All pure code. The fixtures marked "real" are taken verbatim from run 5,
recorded in run_log.json before these rules existed.
"""
import pytest

from src.config import rules
from src.models import Fact
from src.validate import validate

SOURCE = "CNN Indonesia"


# Verified facts as the real run produced them.
@pytest.fixture
def real_facts():
    return [
        Fact(claim="Penjualan rumah tipe besar merosot 10,78 persen",
             quote="Penjualan rumah tipe besar merosot 10,78 persen."),
        Fact(claim="Suku bunga KPR relatif stabil di level 7,47 persen",
             quote="suku bunga KPR tercatat relatif stabil di level 7,47 "
                   "persen pada kuartal III 2026."),
        Fact(claim="Pembangunan fisik ditargetkan mulai Januari 2027",
             quote="pembangunan fisik ditargetkan mulai Januari 2027 dengan "
                   "estimasi penyelesaian pada Agustus 2028"),
    ]


def wrap(body):
    """Give a body valid structure so only the rule under test can fire."""
    return f"{body}\n\nMenurut kamu, bagaimana?\n\n#Rumah123 #KPR"


def rules_hit(caption, facts, source=SOURCE):
    return {f.rule for f in validate(caption, facts, source)}


# --- rule 10: superlatives and absolutes --------------------------------------

def test_real_paling_tajam_is_rejected(real_facts):
    """Run 5 wrote "penurunan paling tajam" from a fact that only gave a
    figure. "Paling" asserts a ranking the facts do not establish."""
    caption = wrap("Menurut CNN Indonesia penurunan paling tajam terjadi "
                   "pada tipe besar, 10,78 persen.")
    assert "unsupported_superlative" in rules_hit(caption, real_facts)


def test_real_tidak_berubah_is_rejected(real_facts):
    """Run 5 wrote "suku bunga tidak berubah" from "relatif stabil"."""
    caption = wrap("Menurut CNN Indonesia suku bunga KPR tidak berubah, "
                   "tetap di 7,47 persen.")
    assert "unsupported_superlative" in rules_hit(caption, real_facts)


@pytest.mark.parametrize("word", [
    "paling", "terbesar", "tertinggi", "terendah", "selalu", "pasti",
    "tidak berubah", "dijamin", "semua", "seluruh",
])
def test_every_guarded_word_fires_when_unsupported(word, real_facts):
    caption = wrap(f"Menurut CNN Indonesia angkanya {word} begitu.")
    assert "unsupported_superlative" in rules_hit(caption, real_facts), word


def test_guarded_word_is_allowed_when_the_facts_use_it():
    facts = [Fact(claim="Tipe besar turun paling tajam",
                  quote="penjualan tipe besar turun paling tajam di antara "
                        "semua tipe")]
    caption = wrap("Menurut CNN Indonesia tipe besar turun paling tajam.")
    assert "unsupported_superlative" not in rules_hit(caption, facts)


def test_guarded_word_supported_by_the_claim_not_only_the_quote():
    facts = [Fact(claim="Harga tertinggi tercatat di Jakarta",
                  quote="harga rumah di Jakarta berada di posisi teratas")]
    caption = wrap("Menurut CNN Indonesia harga tertinggi ada di Jakarta.")
    assert "unsupported_superlative" not in rules_hit(caption, facts)


def test_clean_caption_triggers_no_superlative_rule(real_facts):
    caption = wrap("Menurut CNN Indonesia tipe besar merosot 10,78 persen.")
    assert "unsupported_superlative" not in rules_hit(caption, real_facts)


def test_guarded_word_matching_is_boundary_aware(real_facts):
    """"semua" must not fire inside a longer word."""
    caption = wrap("Menurut CNN Indonesia angka itu semuanya tercatat.")
    hit = rules_hit(caption, real_facts)
    assert "unsupported_superlative" not in hit


def test_superlative_message_names_the_words(real_facts):
    caption = wrap("Menurut CNN Indonesia ini pasti yang terbesar.")
    msg = [f.message for f in validate(caption, real_facts, SOURCE)
           if f.rule == "unsupported_superlative"][0]
    assert "pasti" in msg and "terbesar" in msg


# --- rule 11: dropped hedges --------------------------------------------------

def test_real_akan_mulai_drops_the_ditargetkan_hedge(real_facts):
    """Run 5 turned "ditargetkan mulai Januari 2027" into "akan mulai"."""
    caption = wrap("Menurut CNN Indonesia rusun akan mulai dibangun "
                   "Januari 2027.")
    assert "dropped_hedge" in rules_hit(caption, real_facts)


def test_keeping_the_hedge_passes(real_facts):
    caption = wrap("Menurut CNN Indonesia pembangunan ditargetkan mulai "
                   "Januari 2027.")
    assert "dropped_hedge" not in rules_hit(caption, real_facts)


@pytest.mark.parametrize("hedge", [
    "ditargetkan", "direncanakan", "rencananya", "sekitar", "diperkirakan",
    "estimasi", "kurang lebih",
])
def test_any_allowed_hedge_satisfies_the_rule(hedge, real_facts):
    caption = wrap(f"Menurut CNN Indonesia pembangunan {hedge} mulai "
                   f"Januari 2027.")
    assert "dropped_hedge" not in rules_hit(caption, real_facts), hedge


def test_relatif_hedge_must_be_kept(real_facts):
    caption = wrap("Menurut CNN Indonesia suku bunga KPR tetap di 7,47 persen.")
    assert "dropped_hedge" in rules_hit(caption, real_facts)


def test_relatif_hedge_kept_passes(real_facts):
    caption = wrap("Menurut CNN Indonesia suku bunga KPR relatif stabil di "
                   "7,47 persen.")
    assert "dropped_hedge" not in rules_hit(caption, real_facts)


def test_unhedged_fact_carries_no_obligation(real_facts):
    """10,78 comes from a fact with no hedge, so no hedge is required."""
    caption = wrap("Menurut CNN Indonesia tipe besar merosot 10,78 persen.")
    assert "dropped_hedge" not in rules_hit(caption, real_facts)


def test_figure_available_from_an_unhedged_fact_is_not_obliged():
    """The same figure appears hedged in one fact and plain in another, so the
    caption may be drawing on the plain one."""
    facts = [
        Fact(claim="Target 2027", quote="pembangunan ditargetkan mulai 2027"),
        Fact(claim="Anggaran 2027 sudah disetujui",
             quote="anggaran untuk 2027 sudah disetujui DPR"),
    ]
    caption = wrap("Menurut CNN Indonesia anggaran 2027 sudah disetujui.")
    assert "dropped_hedge" not in rules_hit(caption, facts)


def test_only_the_offending_sentence_is_reported(real_facts):
    caption = ("Menurut CNN Indonesia tipe besar merosot 10,78 persen.\n\n"
               "Rusun akan mulai dibangun Januari 2027.\n\n"
               "Menurut kamu?\n\n#Rumah123 #KPR")
    failures = [f for f in validate(caption, real_facts, SOURCE)
                if f.rule == "dropped_hedge"]
    assert len(failures) == 1
    assert "2027" in failures[0].message
    assert "10,78" not in failures[0].message


def test_hedge_message_names_the_facts_hedge_word(real_facts):
    caption = wrap("Menurut CNN Indonesia rusun akan mulai dibangun "
                   "Januari 2027.")
    msg = [f.message for f in validate(caption, real_facts, SOURCE)
           if f.rule == "dropped_hedge"][0]
    assert "ditargetkan" in msg


def test_no_facts_means_no_hedge_rule():
    assert "dropped_hedge" not in rules_hit(wrap("Teks CNN Indonesia."), [])


# --- rule 12: block structure -------------------------------------------------

def test_single_block_caption_is_rejected(real_facts):
    caption = "Menurut CNN Indonesia ada kabar baru. #Rumah123 #KPR"
    assert "block_structure" in rules_hit(caption, real_facts)


def test_two_blocks_pass(real_facts):
    caption = "Menurut CNN Indonesia ada kabar.\n\nMenurut kamu?\n\n#Rumah123 #KPR"
    assert "block_structure" not in rules_hit(caption, real_facts)


def test_wall_of_text_is_rejected_for_length(real_facts):
    """Run 5 passed captions of 57, 71 and 79 words in one unbroken block."""
    body = "Menurut CNN Indonesia " + " ".join(["kata"] * 55)
    caption = f"{body}\n\nMenurut kamu?\n\n#Rumah123 #KPR"
    assert "block_too_long" in rules_hit(caption, real_facts)


def test_block_at_the_limit_passes(real_facts):
    limit = rules()["caption"]["blocks"]["max_words_per_block"]
    body = "Menurut CNN Indonesia " + " ".join(["kata"] * (limit - 3))
    caption = f"{body}\n\nMenurut kamu?\n\n#Rumah123 #KPR"
    assert "block_too_long" not in rules_hit(caption, real_facts)


def test_block_message_names_which_block_and_how_long(real_facts):
    body = "Menurut CNN Indonesia " + " ".join(["kata"] * 55)
    caption = f"{body}\n\nMenurut kamu?\n\n#Rumah123 #KPR"
    msg = [f.message for f in validate(caption, real_facts, SOURCE)
           if f.rule == "block_too_long"][0]
    assert "block 1" in msg and "58 words" in msg


def test_hashtag_line_is_not_counted_as_a_block(real_facts):
    """Otherwise a one-block caption would look like two."""
    caption = "Menurut CNN Indonesia ada kabar.\n\n#Rumah123 #KPR"
    assert "block_structure" in rules_hit(caption, real_facts)


def test_single_newlines_do_not_make_blocks(real_facts):
    """Run 5's walls of text used single newlines, not blank lines."""
    caption = ("Menurut CNN Indonesia ada kabar.\nBaris kedua.\nBaris ketiga."
               "\n\n#Rumah123 #KPR")
    assert "block_structure" in rules_hit(caption, real_facts)
