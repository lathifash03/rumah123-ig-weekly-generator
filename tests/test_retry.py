"""The generate / validate / claim-check retry loop, with a mocked LLM.

No API key and no network are involved.
"""
import pytest

from src.retry import run_item, run_variant
from tests.conftest import PASSING_CAPTION, StubLLM

GOOD = {"caption": PASSING_CAPTION, "image_text": "Harga rumah naik 8,43 persen"}

# Fails validation: banned phrase, em dash, duplicate hashtag, bad number,
# and no source name.
BAD = {"caption": "Buruan beli — naik 99 persen #Rumah123 #Rumah123",
       "image_text": "x"}

CC_OK = {"claims": [
    {"claim": "harga rumah naik 8,43 persen", "supported": True,
     "quote": "harga rumah naik 8,43 persen pada kuartal III 2026"},
]}
CC_BAD = {"claims": [
    {"claim": "rumah akan murah tahun depan", "supported": False, "quote": ""},
]}


def test_first_attempt_pass_uses_one_generate_and_one_claimcheck(vitem):
    llm = StubLLM([GOOD, CC_OK])
    res = run_variant(llm, vitem, 0)
    assert res.passed
    assert len(res.attempts) == 1
    assert res.first_attempt_passed
    assert [c["schema"] for c in llm.calls] == ["caption", "claimcheck"]


def test_validation_failure_then_pass_on_retry(vitem):
    llm = StubLLM([BAD, GOOD, CC_OK])
    res = run_variant(llm, vitem, 0)
    assert res.passed
    assert len(res.attempts) == 2
    assert not res.first_attempt_passed
    assert res.attempts[0]["failures"]
    assert res.attempts[1]["failures"] == []


def test_failed_validation_skips_the_claimcheck_call(vitem):
    """A caption that fails cheap code checks must not cost an LLM call."""
    llm = StubLLM([BAD, GOOD, CC_OK])
    res = run_variant(llm, vitem, 0)
    schemas = [c["schema"] for c in llm.calls]
    assert schemas == ["caption", "caption", "claimcheck"]
    assert res.attempts[0]["claimcheck_skipped"] == "validation failed first"
    assert res.attempts[0]["claimcheck_failures"] == []


def test_exact_failure_list_is_sent_back_to_the_generator(vitem):
    llm = StubLLM([BAD, GOOD, CC_OK])
    run_variant(llm, vitem, 0)
    retry_prompt = llm.calls[1]["user"]
    assert "FAILURES" in retry_prompt
    assert "[banned_phrase]" in retry_prompt
    assert "[em_dash]" in retry_prompt
    assert "[ungrounded_number]" in retry_prompt


def test_claimcheck_failure_triggers_a_retry(vitem):
    llm = StubLLM([GOOD, CC_BAD, GOOD, CC_OK])
    res = run_variant(llm, vitem, 0)
    assert res.passed
    assert len(res.attempts) == 2
    assert res.attempts[0]["claimcheck_failures"]
    assert res.attempts[0]["validation_failures"] == []


def test_max_two_retries_means_at_most_three_attempts(vitem):
    llm = StubLLM([BAD, BAD, BAD])
    res = run_variant(llm, vitem, 0, max_retries=2)
    assert not res.passed
    assert len(res.attempts) == 3
    assert [c["schema"] for c in llm.calls] == ["caption"] * 3


def test_max_retries_zero_means_one_attempt(vitem):
    llm = StubLLM([BAD])
    res = run_variant(llm, vitem, 0, max_retries=0)
    assert not res.passed
    assert len(res.attempts) == 1


def test_every_attempt_records_its_failure_rules(vitem):
    llm = StubLLM([BAD, BAD, BAD])
    res = run_variant(llm, vitem, 0)
    for attempt in res.attempts:
        assert attempt["failure_rules"]
        assert "banned_phrase" in attempt["failure_rules"]


def test_generate_exception_is_recorded_and_retried(vitem):
    llm = StubLLM([RuntimeError("rate limited"), GOOD, CC_OK])
    res = run_variant(llm, vitem, 0)
    assert res.passed
    assert "rate limited" in res.attempts[0]["error"]
    assert len(res.attempts) == 2


def test_claimcheck_exception_is_recorded_as_a_failure(vitem):
    llm = StubLLM([GOOD, RuntimeError("timeout"), GOOD, CC_OK])
    res = run_variant(llm, vitem, 0)
    assert res.passed
    assert res.attempts[0]["claimcheck_failures"]
    assert "timeout" in res.attempts[0]["claimcheck_failures"][0]


def test_variant_angle_differs_between_variants(vitem):
    llm0 = StubLLM([GOOD, CC_OK])
    llm1 = StubLLM([GOOD, CC_OK])
    run_variant(llm0, vitem, 0)
    run_variant(llm1, vitem, 1)
    assert llm0.calls[0]["user"] != llm1.calls[0]["user"]
    assert "VARIANT ANGLE" in llm0.calls[0]["user"]


def test_run_item_produces_three_variants(vitem):
    llm = StubLLM([GOOD, CC_OK] * 3)
    results = run_item(llm, vitem, variants=3)
    assert len(results) == 3
    assert all(r.passed for r in results)


def test_verified_facts_are_in_the_generator_prompt(vitem):
    llm = StubLLM([GOOD, CC_OK])
    run_variant(llm, vitem, 0)
    user = llm.calls[0]["user"]
    assert "VERIFIED FACTS" in user
    assert "8,43" in user
    assert "CNN Indonesia" in user
