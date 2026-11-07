"""Claim check: the model's verdict is only trusted when its quote verifies."""
from src.claimcheck import check
from tests.conftest import StubLLM


def test_supported_claim_with_verifiable_quote_passes(facts):
    llm = StubLLM([{"claims": [
        {"claim": "harga rumah naik 8,43 persen", "supported": True,
         "quote": "harga rumah naik 8,43 persen pada kuartal III 2026"},
    ]}])
    failures, detail = check(llm, "caption text", facts)
    assert failures == []
    assert detail[0]["verdict"] == "quote_verified"


def test_model_saying_unsupported_is_a_failure(facts):
    llm = StubLLM([{"claims": [
        {"claim": "harga rumah naik 50 persen", "supported": False, "quote": ""},
    ]}])
    failures, detail = check(llm, "caption", facts)
    assert len(failures) == 1
    assert failures[0].rule == "unsupported_claim"
    assert detail[0]["verdict"] == "model_said_unsupported"


def test_supported_claim_with_fabricated_quote_is_a_failure(facts):
    """The model claims support but its quote is not in the verified facts.
    Code catches that rather than taking the verdict at face value."""
    llm = StubLLM([{"claims": [
        {"claim": "suku bunga turun", "supported": True,
         "quote": "Bank Indonesia menurunkan suku bunga ke 3 persen"},
    ]}])
    failures, detail = check(llm, "caption", facts)
    assert len(failures) == 1
    assert failures[0].rule == "unverifiable_claim"
    assert detail[0]["verdict"] == "quote_not_found_in_facts"


def test_quote_verification_tolerates_whitespace_differences(facts):
    llm = StubLLM([{"claims": [
        {"claim": "harga naik", "supported": True,
         "quote": "harga rumah naik 8,43 persen\n  pada kuartal III 2026"},
    ]}])
    failures, _ = check(llm, "caption", facts)
    assert failures == []


def test_no_facts_is_an_immediate_failure_without_calling_the_model():
    llm = StubLLM([])  # any call would raise
    failures, detail = check(llm, "caption", [])
    assert len(failures) == 1
    assert failures[0].rule == "claimcheck"
    assert llm.calls == []


def test_mixed_claims_report_only_the_bad_ones(facts):
    llm = StubLLM([{"claims": [
        {"claim": "harga rumah naik 8,43 persen", "supported": True,
         "quote": "harga rumah naik 8,43 persen pada kuartal III 2026"},
        {"claim": "rumah akan murah tahun depan", "supported": False, "quote": ""},
    ]}])
    failures, detail = check(llm, "caption", facts)
    assert len(failures) == 1
    assert "rumah akan murah" in failures[0].message
    assert len(detail) == 2


def test_blank_claims_are_skipped(facts):
    llm = StubLLM([{"claims": [{"claim": "  ", "supported": False, "quote": ""}]}])
    failures, detail = check(llm, "caption", facts)
    assert failures == []
    assert detail == []
