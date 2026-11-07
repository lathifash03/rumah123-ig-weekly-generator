"""Relevance filtering and dedupe. Pure code."""
from src.filter import dedupe, normalize_url, relevant
from src.models import Item


def mk(title, url, summary=""):
    return Item(title=title, url=url, published="2026-11-06T00:00:00+00:00",
                source="Test", source_display="Test", summary=summary)


# --- URL normalisation --------------------------------------------------------

def test_normalize_strips_www_and_tracking_and_fragment():
    a = normalize_url("https://WWW.Detik.com/properti/a/1/?utm_source=x&id=9#top")
    assert a == "https://detik.com/properti/a/1?id=9"


def test_normalize_strips_trailing_slash():
    assert normalize_url("https://a.co/x/") == normalize_url("https://a.co/x")


def test_normalize_keeps_meaningful_query():
    assert "id=9" in normalize_url("https://a.co/x?id=9")


# --- relevance ----------------------------------------------------------------

def test_keyword_item_is_kept():
    kept, rej = relevant([mk("Penjualan Rumah Lesu, KPR Masih Jadi Andalan",
                             "https://a.co/1")])
    assert len(kept) == 1
    assert "kpr" in kept[0].keywords_matched


def test_irrelevant_item_is_rejected():
    kept, rej = relevant([mk("Prediksi Skor AS Roma vs Sassuolo", "https://a.co/2")])
    assert kept == []
    assert rej[0]["reason"] in ("no_keyword_match", "title_blocklist")


def test_substring_only_match_is_rejected():
    """Regression: "mbr" must not fire on an unrelated finance headline."""
    kept, _ = relevant([mk("IHSG Ditutup Menguat ke 5.050 Desember",
                           "https://a.co/3")])
    assert kept == []


def test_video_prefix_is_blocklisted():
    kept, rej = relevant([mk("Video: Siasati Suku Bunga Tinggi", "https://a.co/4")])
    assert kept == []
    assert rej[0]["reason"] == "title_blocklist"


def test_keyword_can_match_in_summary():
    kept, _ = relevant([mk("Kabar Terbaru", "https://a.co/5",
                           summary="Pemerintah menambah kuota rumah subsidi.")])
    assert len(kept) == 1


# --- dedupe -------------------------------------------------------------------

def test_duplicate_url_is_dropped():
    items = [mk("Judul A", "https://a.co/x"),
             mk("Judul B", "https://www.a.co/x/?utm_source=y")]
    kept, dropped = dedupe(items)
    assert len(kept) == 1
    assert dropped[0]["reason"] == "duplicate_url"


def test_near_identical_titles_are_deduped():
    """Regression: the live detik feed carried four near-identical headlines
    about the same IKN apartment block."""
    items = [
        mk("Rusun MBR di IKN Sedikit Lagi Selesai, Disewakan atau Dijual?",
           "https://a.co/1"),
        mk("Rusun MBR di IKN Sedikit Lagi Selesai Disewakan atau Dijual",
           "https://a.co/2"),
    ]
    kept, dropped = dedupe(items)
    assert len(kept) == 1
    assert dropped[0]["reason"] == "similar_title"
    assert dropped[0]["similarity"] >= 0.82


def test_distinct_stories_are_both_kept():
    items = [mk("Survei BI: Harga Rumah Naik Tipis", "https://a.co/1"),
             mk("Rusun MBR di IKN Tipe 36", "https://a.co/2")]
    kept, dropped = dedupe(items)
    assert len(kept) == 2
    assert dropped == []


def test_dedupe_records_what_it_was_a_duplicate_of():
    items = [mk("Judul A", "https://a.co/x"), mk("Judul A", "https://a.co/y")]
    kept, dropped = dedupe(items)
    assert dropped[0]["duplicate_of"] == "https://a.co/x"
