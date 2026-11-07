"""Claim check v2: sentence coverage, fail-closed labels, figure verification.

The model's verdict is never the last word. Code verifies that the whole
caption was covered, re-classifies sentences the model called voice, and
checks that each supporting quote really contains the figure it is cited for.
"""
import pytest

from src.claimcheck import check, looks_factual
from src.config import rules
from tests.conftest import StubLLM

FACT_QUOTE = "harga rumah naik 8,43 persen pada kuartal III 2026"
RATE_QUOTE = "Bank Indonesia menahan suku bunga acuan di 5,25 persen"


def sent(text, factual=True, supported=True, quote=""):
    return {"text": text, "factual": factual, "supported": supported,
            "quote": quote}


# --- check 1: coverage --------------------------------------------------------

CAPTION = "Harga rumah naik 8,43 persen. Ambil waktumu. #Rumah123 #KPR"


def test_full_coverage_passes(facts):
    llm = StubLLM([{"sentences": [
        sent("Harga rumah naik 8,43 persen.", quote=FACT_QUOTE),
        sent("Ambil waktumu.", factual=False, supported=False),
    ]}])
    failures, detail = check(llm, CAPTION, facts)
    assert failures == []
    assert detail[0]["verdict"] == "quote_and_figures_verified"
    assert detail[1]["verdict"] == "non_factual"


def test_skipped_sentence_fails_the_whole_check(facts):
    """A sentence left out was never checked, so the caption is unverified."""
    llm = StubLLM([{"sentences": [
        sent("Harga rumah naik 8,43 persen.", quote=FACT_QUOTE),
        # "Ambil waktumu." omitted
    ]}])
    failures, detail = check(llm, CAPTION, facts)
    assert len(failures) == 1
    assert failures[0].rule == "sentence_coverage"
    assert detail[0]["verdict"] == "coverage_mismatch"


def test_invented_sentence_fails_coverage(facts):
    llm = StubLLM([{"sentences": [
        sent("Harga rumah naik 8,43 persen.", quote=FACT_QUOTE),
        sent("Ambil waktumu.", factual=False, supported=False),
        sent("Kalimat yang tidak ada di caption.", factual=False,
             supported=False),
    ]}])
    failures, _ = check(llm, CAPTION, facts)
    assert failures[0].rule == "sentence_coverage"


def test_coverage_tolerates_respacing_and_punctuation(facts):
    """The model may re-space or drop a comma without failing the caption."""
    caption = "Harga rumah naik 8,43 persen, kata BI. Ambil waktumu. #Rumah123 #KPR"
    llm = StubLLM([{"sentences": [
        sent("Harga rumah  naik 8,43 persen kata BI", quote=FACT_QUOTE),
        sent("Ambil   waktumu", factual=False, supported=False),
    ]}])
    failures, _ = check(llm, caption, facts)
    assert all(f.rule != "sentence_coverage" for f in failures)


def test_hashtag_line_need_not_be_returned(facts):
    llm = StubLLM([{"sentences": [
        sent("Harga rumah naik 8,43 persen.", quote=FACT_QUOTE),
        sent("Ambil waktumu.", factual=False, supported=False),
    ]}])
    failures, _ = check(llm, CAPTION, facts)
    assert all(f.rule != "sentence_coverage" for f in failures)


# --- check 2: fail-closed classification -------------------------------------

def test_non_factual_label_with_a_digit_is_reclassified(facts):
    caption = "Harga naik 8,43 persen. #Rumah123 #KPR"
    llm = StubLLM([{"sentences": [
        sent("Harga naik 8,43 persen.", factual=False, supported=False),
    ]}])
    failures, detail = check(llm, caption, facts)
    assert len(failures) == 1
    assert failures[0].rule == "mislabelled_claim"
    assert detail[0]["verdict"] == "reclassified_as_factual"
    assert "contains a digit" in detail[0]["reasons"]


def test_non_factual_label_naming_an_institution_is_reclassified(facts):
    caption = "Bank Indonesia sudah memutuskan. #Rumah123 #KPR"
    llm = StubLLM([{"sentences": [
        sent("Bank Indonesia sudah memutuskan.", factual=False,
             supported=False),
    ]}])
    failures, detail = check(llm, caption, facts)
    assert failures[0].rule == "mislabelled_claim"
    assert any("bank indonesia" in r for r in detail[0]["reasons"])


def test_non_factual_label_with_a_trend_verb_is_reclassified(facts):
    caption = "Harga rumah naik lagi. #Rumah123 #KPR"
    llm = StubLLM([{"sentences": [
        sent("Harga rumah naik lagi.", factual=False, supported=False),
    ]}])
    failures, detail = check(llm, caption, facts)
    assert failures[0].rule == "mislabelled_claim"
    assert any("naik" in r for r in detail[0]["reasons"])


def test_genuine_voice_sentence_is_not_reclassified(facts):
    caption = "Rasanya berat ya. #Rumah123 #KPR"
    llm = StubLLM([{"sentences": [
        sent("Rasanya berat ya.", factual=False, supported=False),
    ]}])
    failures, detail = check(llm, caption, facts)
    assert failures == []
    assert detail[0]["verdict"] == "non_factual"


def test_brand_name_digits_do_not_force_reclassification(facts):
    """Rumah123 contains digits, but they are part of a name."""
    caption = "Di Rumah123 kamu bisa lihat-lihat. #Rumah123 #KPR"
    llm = StubLLM([{"sentences": [
        sent("Di Rumah123 kamu bisa lihat-lihat.", factual=False,
             supported=False),
    ]}])
    failures, detail = check(llm, caption, facts)
    assert failures == []
    assert detail[0]["verdict"] == "non_factual"


def test_a_fact_asserted_inside_a_question_counts_as_a_claim(facts):
    """A hook or question is not automatically voice."""
    caption = "Pernah dengar harga rumah naik 8,43 persen? #Rumah123 #KPR"
    llm = StubLLM([{"sentences": [
        sent("Pernah dengar harga rumah naik 8,43 persen?", factual=False,
             supported=False),
    ]}])
    failures, _ = check(llm, caption, facts)
    assert failures[0].rule == "mislabelled_claim"


def test_question_carrying_a_verified_figure_can_pass_when_labelled_properly(facts):
    caption = "Pernah dengar harga rumah naik 8,43 persen? #Rumah123 #KPR"
    llm = StubLLM([{"sentences": [
        sent("Pernah dengar harga rumah naik 8,43 persen?", quote=FACT_QUOTE),
    ]}])
    failures, detail = check(llm, caption, facts)
    assert failures == []
    assert detail[0]["verdict"] == "quote_and_figures_verified"


# --- check 3: quote and figure verification ----------------------------------

def test_fabricated_quote_is_caught(facts):
    caption = "Suku bunga turun ke 3 persen. #Rumah123 #KPR"
    llm = StubLLM([{"sentences": [
        sent("Suku bunga turun ke 3 persen.",
             quote="Bank Indonesia menurunkan suku bunga ke 3 persen"),
    ]}])
    failures, detail = check(llm, caption, facts)
    assert failures[0].rule == "unverifiable_claim"
    assert detail[0]["verdict"] == "quote_not_found_in_facts"


def test_figure_absent_from_its_own_quote_is_caught(facts):
    """The quote is real and supports the wording, but not the number."""
    caption = "Harga rumah naik 12 persen. #Rumah123 #KPR"
    llm = StubLLM([{"sentences": [
        sent("Harga rumah naik 12 persen.", quote=FACT_QUOTE),
    ]}])
    failures, detail = check(llm, caption, facts)
    assert failures[0].rule == "unsupported_figure"
    assert "12" in detail[0]["missing_figures"]


def test_number_word_absent_from_its_own_quote_is_caught(facts):
    caption = "Harga rumah naik delapan persen. #Rumah123 #KPR"
    llm = StubLLM([{"sentences": [
        sent("Harga rumah naik delapan persen.", quote=FACT_QUOTE),
    ]}])
    failures, detail = check(llm, caption, facts)
    assert failures[0].rule == "unsupported_figure"
    assert any("delapan" in f for f in detail[0]["missing_figures"])


def test_figure_present_in_the_quote_passes(facts):
    caption = "Suku bunga acuan ditahan di 5,25 persen. #Rumah123 #KPR"
    llm = StubLLM([{"sentences": [
        sent("Suku bunga acuan ditahan di 5,25 persen.", quote=RATE_QUOTE),
    ]}])
    failures, _ = check(llm, caption, facts)
    assert failures == []


def test_model_saying_unsupported_is_a_failure(facts):
    caption = "Rumah akan murah tahun depan. #Rumah123 #KPR"
    llm = StubLLM([{"sentences": [
        sent("Rumah akan murah tahun depan.", supported=False),
    ]}])
    failures, detail = check(llm, caption, facts)
    assert failures[0].rule == "unsupported_claim"
    assert detail[0]["verdict"] == "model_said_unsupported"


def test_quote_verification_tolerates_whitespace_differences(facts):
    caption = "Harga rumah naik 8,43 persen. #Rumah123 #KPR"
    llm = StubLLM([{"sentences": [
        sent("Harga rumah naik 8,43 persen.",
             quote="harga rumah naik 8,43 persen\n   pada kuartal III 2026"),
    ]}])
    failures, _ = check(llm, caption, facts)
    assert failures == []


def test_no_facts_fails_without_calling_the_model():
    llm = StubLLM([])
    failures, detail = check(llm, "apa pun", [])
    assert failures[0].rule == "claimcheck"
    assert llm.calls == []


def test_mixed_caption_reports_only_the_bad_sentence(facts):
    caption = ("Harga rumah naik 8,43 persen. Rumah akan murah tahun depan. "
               "#Rumah123 #KPR")
    llm = StubLLM([{"sentences": [
        sent("Harga rumah naik 8,43 persen.", quote=FACT_QUOTE),
        sent("Rumah akan murah tahun depan.", supported=False),
    ]}])
    failures, detail = check(llm, caption, facts)
    assert len(failures) == 1
    assert "murah tahun depan" in failures[0].message
    assert len(detail) == 2


# --- the reclassification helper ---------------------------------------------

@pytest.fixture
def cc_cfg():
    return rules()["claimcheck"]


@pytest.fixture
def brand():
    return rules()["caption"]["brand_tokens"]


@pytest.mark.parametrize("sentence", [
    "Harga naik 8,43 persen.",
    "Bank Indonesia menahan suku bunga.",
    "Harga rumah turun.",
    "Penjualan rumah lesu.",
    "Pemerintah menambah kuota.",
])
def test_sentences_that_must_be_treated_as_factual(sentence, cc_cfg, brand):
    assert looks_factual(sentence, cc_cfg, brand)


@pytest.mark.parametrize("sentence", [
    "Rasanya berat ya menabung.",
    "Ambil waktumu.",
    "Menurut kamu bagaimana?",
    "Di Rumah123 kamu bisa lihat-lihat dulu.",
])
def test_sentences_that_are_genuinely_voice(sentence, cc_cfg, brand):
    assert looks_factual(sentence, cc_cfg, brand) == []
