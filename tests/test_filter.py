"""Relevance filtering and dedupe. Pure code."""
from src.config import rules
from src.filter import dedupe, normalize_url, relevant
from src.models import Item
from src.textutil import title_similarity


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
    """Near-identical wording is caught by the sequence-ratio signal."""
    items = [
        mk("Rusun MBR di IKN Sedikit Lagi Selesai, Disewakan atau Dijual?",
           "https://a.co/1"),
        mk("Rusun MBR di IKN Sedikit Lagi Selesai Disewakan atau Dijual",
           "https://a.co/2"),
    ]
    kept, dropped = dedupe(items)
    assert len(kept) == 1
    assert dropped[0]["reason"] == "same_story"
    assert dropped[0]["sequence_ratio"] >= 0.62


# Same-story detection weighs shared words by how rare they are across the
# batch, so these fixtures use a realistic batch. In production a week carries
# roughly 40 candidates. With only two titles every shared word appears in
# every document and carries no information by construction.
DISTRACTORS = [
    "Survei BI: Harga Rumah Naik Tipis, Penjualan Anjlok 8,43 Persen",
    "Penjualan Rumah Lesu, KPR Masih Jadi Andalan",
    "Suku Bunga di Inggris Sentuh 4%, Pertama Kali Naik dalam 3 Tahun",
    "Kondisi Industri Keuangan RI di Tengah Suku Bunga Tinggi",
    "Harga Rumah di Australia Anjlok 7 Bulan Beruntun",
    "Rusun Benhil II Berdiri Sejak 1994, Kini Kumuh Butuh Perhatian",
    "Pinggiran Jakarta Masih Dilirik Pencari Rumah, Pengembang Sasar Gen-Z",
    "PKP Gandeng Kemenkum, Godok Regulasi Bangun Rumah Makin Sat Set",
    "Asal Usul Penthouse: Dulu Kamar Pembantu, Kini Jadi Rumah Orang Tajir",
    "Bos Tapera Maunya Rusun Subsidi Terjual 10.000 Unit, tapi Baru Laku 25",
]


def with_distractors(*titles):
    """A realistic batch: the titles under test plus unrelated candidates."""
    items = [mk(t, f"https://a.co/t{n}") for n, t in enumerate(titles)]
    items += [mk(t, f"https://d.co/{n}") for n, t in enumerate(DISTRACTORS)]
    return items


def test_retellings_of_one_story_are_deduped():
    """Different wording, same story, caught by shared specific words.

    Real headlines from the 2026-11-07 fetch, where nine separate articles
    covered this one project.
    """
    items = with_distractors(
        "Ada 1.500 Orang Mau Beli Rusun Subsidi Manggarai, Kapan Mulai Dijual?",
        "Belum Resmi Dijual, Rusun Subsidi di Manggarai Sudah Diserbu 1.500 Orang",
    )
    kept, dropped = dedupe(items)
    under_test = [i.url for i in kept if i.url.startswith("https://a.co/t")]
    assert len(under_test) == 1, f"kept {under_test}, dropped {dropped}"
    merge = next(d for d in dropped if d["reason"] == "same_story")
    assert "manggarai" in merge["shared_specific_words"]
    assert merge["rarity_score"] >= 1.55


def test_dedupe_recall_is_partial_and_that_is_known():
    """Documents a real limit rather than asserting a recall the rule has not
    got.

    Headlines retelling one story in wording that shares only a single
    specific word are NOT merged, because one coincidental rare word is too
    weak a signal to act on. On the 2026-11-07 fetch this left four IKN
    headlines, which share "ikn" and nothing else specific, all reaching the
    ranker.
    """
    items = with_distractors(
        "Kabar Baru dari IKN: Rusun buat MBR Hampir Rampung!",
        "Rusun MBR di IKN Tipe 36, Penghuni Tinggal Bawa Badan",
    )
    kept, dropped = dedupe(items)
    under_test = [i.url for i in kept if i.url.startswith("https://a.co/t")]
    assert len(under_test) == 2, (
        "if this now merges, dedupe recall improved and the README limitation "
        "should be updated"
    )


def test_distinct_stories_are_both_kept():
    items = [mk("Survei BI: Harga Rumah Naik Tipis", "https://a.co/1"),
             mk("Rusun MBR di IKN Tipe 36", "https://a.co/2")]
    kept, dropped = dedupe(items)
    assert len(kept) == 2
    assert dropped == []


def test_same_topic_different_country_is_not_merged():
    """Regression: these two share only topic words ("harga", "rumah") plus
    the generic "anjlok", and are genuinely different stories. An earlier
    rarity rule that counted topic words merged them."""
    items = with_distractors(
        "Harga Rumah di Australia Anjlok 7 Bulan Beruntun Terparah 40 Tahun",
        "Survei BI: Harga Rumah Indonesia Naik Tipis Kuartal Ketiga",
    )
    kept, dropped = dedupe(items)
    under_test = [i.url for i in kept if i.url.startswith("https://a.co/t")]
    assert len(under_test) == 2, f"wrongly merged: {dropped}"


def test_same_topic_different_country_interest_rates_not_merged():
    items = with_distractors(
        "Kondisi Industri Keuangan RI di Tengah Ancaman Inflasi Tinggi",
        "Suku Bunga di Inggris Sentuh 4 Persen Pertama Kali dalam 3 Tahun",
    )
    kept, dropped = dedupe(items)
    under_test = [i.url for i in kept if i.url.startswith("https://a.co/t")]
    assert len(under_test) == 2, f"wrongly merged: {dropped}"


def test_one_shared_specific_word_is_not_enough():
    """One coincidental rare word must not collapse two stories."""
    items = with_distractors(
        "Proyek Pembangunan di Manggarai Dilanjutkan Pemerintah",
        "Kuliner Manggarai Ramai Dikunjungi Wisatawan Akhir Pekan",
    )
    kept, dropped = dedupe(items)
    under_test = [i.url for i in kept if i.url.startswith("https://a.co/t")]
    assert len(under_test) == 2, f"wrongly merged: {dropped}"


def test_dedupe_records_what_it_was_a_duplicate_of():
    items = [mk("Judul A", "https://a.co/x"), mk("Judul A", "https://a.co/y")]
    kept, dropped = dedupe(items)
    assert dropped[0]["duplicate_of"] == "https://a.co/x"


# --- regression: the dedupe rule that never fired (commit c6b9d36) -----------
# The original rule required a character-sequence ratio of 0.82 between two
# titles. Measured on the 43 real candidates of 2026-11-07, genuine retellings
# of one story reached only about 0.64, so the rule could not fire at all and
# the dedupe step dropped zero items while nine headlines about one subsidised
# apartment project all reached the ranker.

# Verbatim headlines from that fetch. Nine articles covered this one project.
REAL_RETELLINGS = [
    "Fakta Rusun Subsidi Manggarai yang Belum Dibangun tapi Sudah Diburu 1.500 Orang",
    "Diperebutkan 1.500 Orang, Rusun Subsidi Manggarai Dibanderol Rp 294 Juta",
    "Ada 1.500 Orang Mau Beli Rusun Subsidi Manggarai, Kapan Mulai Dijual?",
    "Belum Resmi Dijual, Rusun Subsidi di Manggarai Sudah Diserbu 1.500 Orang",
]


def test_regression_dedupe_actually_fires_on_real_retellings():
    """The whole point of commit c6b9d36: this must drop something."""
    items = with_distractors(*REAL_RETELLINGS)
    kept, dropped = dedupe(items)
    under_test = [i.url for i in kept if i.url.startswith("https://a.co/t")]
    assert len(under_test) < len(REAL_RETELLINGS), (
        "dedupe dropped nothing, which is the exact bug commit c6b9d36 fixed"
    )
    assert any(d["reason"] == "same_story" for d in dropped)


def test_regression_sequence_threshold_is_reachable_in_practice():
    """Guards the root cause rather than the symptom.

    A sequence threshold above about 0.7 is unreachable by real retellings, so
    a value that high silently disables the signal.
    """
    threshold = rules()["dedupe"]["title_sequence_threshold"]
    best = max(
        title_similarity(a, b)
        for i, a in enumerate(REAL_RETELLINGS)
        for b in REAL_RETELLINGS[i + 1:]
    )
    assert best < 0.82, (
        "real retellings now exceed the old 0.82 threshold; the premise of "
        "this regression test should be rechecked"
    )
    assert threshold <= 0.7, (
        f"title_sequence_threshold is {threshold}, which real retellings "
        f"(best observed {best:.2f}) cannot reach. The signal is disabled."
    )


def test_regression_rarity_signal_fires_where_wording_alone_cannot():
    """The pair that the sequence ratio alone misses must still be caught."""
    a, b = REAL_RETELLINGS[0], REAL_RETELLINGS[2]
    assert title_similarity(a, b) < 0.62, "premise: wording alone is not enough"

    items = with_distractors(a, b)
    kept, dropped = dedupe(items)
    under_test = [i.url for i in kept if i.url.startswith("https://a.co/t")]
    assert len(under_test) == 1, f"kept {under_test}, dropped {dropped}"
    merge = next(d for d in dropped if d["reason"] == "same_story")
    assert merge["rarity_score"] >= rules()["dedupe"]["story_rarity_score_threshold"]
    assert "manggarai" in merge["shared_specific_words"]


def test_regression_dropped_records_explain_why():
    """A dropped item must record which signal fired, so a future change to
    these thresholds can be audited from run_log.json."""
    items = with_distractors(*REAL_RETELLINGS)
    _, dropped = dedupe(items)
    merge = next(d for d in dropped if d["reason"] == "same_story")
    for key in ["sequence_ratio", "rarity_score", "shared_specific_words",
                "duplicate_of", "duplicate_of_title"]:
        assert key in merge, key
