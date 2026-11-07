"""Fact extraction: every quote is verified against the fetched article text."""
import pytest

from src import extract as extract_mod
from tests.conftest import StubLLM

ARTICLE = (
    "Survei Bank Indonesia menunjukkan harga rumah naik 8,43 persen pada "
    "kuartal III 2026. Bank Indonesia menahan suku bunga acuan di 5,25 persen. "
    "Penjualan rumah turun dibandingkan kuartal sebelumnya menurut laporan "
    "tersebut. Pemerintah menyiapkan kuota rumah subsidi tambahan untuk tahun "
    "depan sebanyak 220 ribu unit bagi masyarakat berpenghasilan rendah. "
    "Laporan itu juga mencatat bahwa permintaan kredit pemilikan rumah masih "
    "tumbuh meskipun melambat pada beberapa segmen harga. Bank sentral "
    "menyatakan kebijakan makroprudensial tetap akomodatif untuk mendukung "
    "pembiayaan sektor perumahan sepanjang tahun ini dan tahun berikutnya."
)


@pytest.fixture
def patched_fetch(monkeypatch):
    monkeypatch.setattr(extract_mod, "fetch_text", lambda url: ARTICLE)


def test_verified_quotes_are_kept(item, patched_fetch):
    llm = StubLLM([{"facts": [
        {"claim": "Harga rumah naik 8,43 persen",
         "quote": "harga rumah naik 8,43 persen pada kuartal III 2026"},
    ]}])
    vitem, log = extract_mod.extract(llm, item)
    assert len(vitem.facts) == 1
    assert log["facts_kept"] == 1
    assert log["facts_dropped"] == 0


def test_fabricated_quote_is_dropped_and_logged(item, patched_fetch):
    """The model invents a quote. Code drops the fact rather than trusting it."""
    llm = StubLLM([{"facts": [
        {"claim": "Suku bunga turun ke 3 persen",
         "quote": "Bank Indonesia menurunkan suku bunga ke 3 persen"},
    ]}])
    vitem, log = extract_mod.extract(llm, item)
    assert vitem.facts == []
    assert log["facts_dropped"] == 1
    assert log["dropped_detail"][0]["reason"] == "quote_not_found_in_article"


def test_paraphrased_quote_is_dropped(item, patched_fetch):
    llm = StubLLM([{"facts": [
        {"claim": "Harga rumah meningkat",
         "quote": "harga rumah meningkat 8,43 persen"},  # "meningkat" not in text
    ]}])
    vitem, log = extract_mod.extract(llm, item)
    assert vitem.facts == []
    assert log["dropped_detail"][0]["reason"] == "quote_not_found_in_article"


def test_mixture_keeps_only_the_verifiable_facts(item, patched_fetch):
    llm = StubLLM([{"facts": [
        {"claim": "Harga rumah naik 8,43 persen",
         "quote": "harga rumah naik 8,43 persen pada kuartal III 2026"},
        {"claim": "Suku bunga ditahan di 5,25 persen",
         "quote": "Bank Indonesia menahan suku bunga acuan di 5,25 persen"},
        {"claim": "Harga akan turun tahun depan",
         "quote": "harga diperkirakan turun tahun depan"},
    ]}])
    vitem, log = extract_mod.extract(llm, item)
    assert len(vitem.facts) == 2
    assert log["facts_dropped"] == 1


def test_overlong_quote_is_dropped(item, patched_fetch):
    llm = StubLLM([{"facts": [
        {"claim": "Terlalu panjang", "quote": ARTICLE},  # > 300 chars
    ]}])
    vitem, log = extract_mod.extract(llm, item)
    assert vitem.facts == []
    assert "longer than" in log["dropped_detail"][0]["reason"]


def test_empty_claim_or_quote_is_dropped(item, patched_fetch):
    llm = StubLLM([{"facts": [{"claim": "", "quote": ""}]}])
    vitem, log = extract_mod.extract(llm, item)
    assert vitem.facts == []
    assert log["facts_dropped"] == 1


def test_fetch_failure_is_logged_not_raised(item, monkeypatch):
    def boom(url):
        raise RuntimeError("connection reset")
    monkeypatch.setattr(extract_mod, "fetch_text", boom)
    llm = StubLLM([])
    vitem, log = extract_mod.extract(llm, item)
    assert vitem.facts == []
    assert "connection reset" in log["error"]
    assert llm.calls == []


def test_too_short_article_is_logged_and_skips_the_model(item, monkeypatch):
    monkeypatch.setattr(extract_mod, "fetch_text", lambda url: "terlalu pendek")
    llm = StubLLM([])
    vitem, log = extract_mod.extract(llm, item)
    assert vitem.facts == []
    assert "too short" in log["error"]
    assert llm.calls == []


def test_article_text_is_not_returned_in_the_log(item, patched_fetch):
    """The repo must not accumulate full article text."""
    llm = StubLLM([{"facts": []}])
    vitem, log = extract_mod.extract(llm, item)
    assert ARTICLE not in str(log)
    assert log["article_chars"] == len(ARTICLE)
