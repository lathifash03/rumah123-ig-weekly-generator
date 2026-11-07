"""The generator contract: the model writes voice, code writes boilerplate."""
import pytest

from src.generate import (
    assemble_caption,
    generate,
    normalize_topic_hashtag,
)
from src.textutil import hashtags
from src.validate import validate
from tests.conftest import StubLLM

REQ = "#Rumah123"


# --- topic hashtag normalisation ---------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("KPR", "#KPR"),
    ("#KPR", "#KPR"),
    ("KPRSubsidi", "#KPRSubsidi"),
    ("#FLPP", "#FLPP"),
    ("Harga Rumah", "#HargaRumah"),
])
def test_topic_hashtag_is_normalised(raw, expected):
    assert normalize_topic_hashtag(raw, REQ, ["properti"]) == expected


def test_empty_topic_falls_back_to_a_matched_keyword():
    assert normalize_topic_hashtag("", REQ, ["rumah subsidi"]) == "#rumahsubsidi"


def test_topic_equal_to_the_required_tag_falls_back():
    """The two hashtags must differ."""
    assert normalize_topic_hashtag("Rumah123", REQ, ["kpr"]) == "#kpr"


def test_unusable_topic_and_unusable_fallbacks_still_yield_a_valid_tag():
    assert normalize_topic_hashtag("!!!", REQ, ["!!!"]) == "#Properti"


def test_fallback_never_duplicates_the_required_tag():
    assert normalize_topic_hashtag("Rumah123", REQ, ["Rumah123"]) == "#Properti"


# --- assembly -----------------------------------------------------------------

def test_assembled_caption_ends_with_exactly_two_hashtags():
    caption = assemble_caption("Isi caption.\n\nPertanyaan?", "#KPR", REQ)
    assert caption.endswith("#Rumah123 #KPR")
    assert hashtags(caption) == ["#Rumah123", "#KPR"]


def test_hashtags_the_model_put_in_the_body_are_removed():
    """Otherwise the caption would carry three hashtags."""
    caption = assemble_caption("Isi #Salah caption #Lagi.", "#KPR", REQ)
    assert hashtags(caption) == ["#Rumah123", "#KPR"]


def test_assembly_separates_the_hashtag_line_with_a_blank_line():
    caption = assemble_caption("Isi caption.", "#KPR", REQ)
    assert caption == "Isi caption.\n\n#Rumah123 #KPR"


def test_trailing_whitespace_in_the_body_is_trimmed():
    caption = assemble_caption("Isi caption.   \n\n  ", "#KPR", REQ)
    assert caption == "Isi caption.\n\n#Rumah123 #KPR"


# --- the failure class this removes ------------------------------------------

def test_generated_caption_never_fails_the_hashtag_rules(vitem):
    """Regression guard for the dominant real-run failure.

    Across three real runs the hashtag line was about half of all validation
    failures, because the model omitted it however firmly the prompt asked.
    Code builds the line now, so a hashtag failure from the generator is no
    longer reachable.
    """
    for body, topic in [
        ("Isi caption tanpa tagar.", "KPR"),
        ("Isi caption.", ""),                 # model gave no topic
        ("Isi #Salah caption.", "#KPR"),      # model put one in the body
        ("Isi caption.", "Rumah123"),         # model duplicated the brand tag
    ]:
        llm = StubLLM([{"caption_body": body, "topic_hashtag": topic,
                        "image_text": "x"}])
        caption = generate(llm, vitem, 0).caption
        rules_hit = {f.rule for f in validate(caption, vitem.facts,
                                              vitem.item.source_display)}
        assert "hashtag_count" not in rules_hit, (body, topic, caption)
        assert "required_hashtag" not in rules_hit, (body, topic, caption)
        assert "topic_hashtag" not in rules_hit, (body, topic, caption)


def test_generate_passes_the_body_through_unchanged(vitem):
    body = "Pernah merasa harga rumah naik? Menurut CNN Indonesia, naik 8,43 persen."
    llm = StubLLM([{"caption_body": body, "topic_hashtag": "KPR",
                    "image_text": "x"}])
    caption = generate(llm, vitem, 0).caption
    assert caption.startswith(body)


def test_image_text_is_carried_through(vitem):
    llm = StubLLM([{"caption_body": "Isi.", "topic_hashtag": "KPR",
                    "image_text": "Harga rumah naik 8,43 persen"}])
    assert generate(llm, vitem, 0).image_text == "Harga rumah naik 8,43 persen"
