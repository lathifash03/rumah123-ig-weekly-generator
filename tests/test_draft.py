"""Draft output: structure, status, and honest reporting of failures."""
import datetime as dt

from src.draft import week_folder, write_draft
from src.retry import VariantResult
from src.models import Caption

NOW = dt.datetime(2026, 11, 7, 12, 0, tzinfo=dt.timezone.utc)


def passing_result(idx, caption_text):
    return VariantResult(
        variant_index=idx, passed=True,
        caption=Caption(caption=caption_text, image_text="Harga rumah naik"),
        attempts=[{"attempt": 1, "failures": []}],
    )


def failing_result(idx):
    return VariantResult(
        variant_index=idx, passed=False,
        caption=Caption(caption="buruan", image_text="x"),
        attempts=[
            {"attempt": 1, "failures": ["[banned_phrase] contains buruan"]},
            {"attempt": 2, "failures": ["[banned_phrase] contains buruan"]},
            {"attempt": 3, "failures": ["[word_count] too long"]},
        ],
    )


def test_week_folder_is_iso_week():
    assert week_folder(NOW) == "2026-W45"


def test_draft_path_layout(vitem, tmp_path):
    path = write_draft(vitem, [passing_result(0, "teks")], 1,
                       now=NOW, draft_dir=tmp_path)
    assert path.parent.name == "2026-W45"
    assert path.name.startswith("01-")
    assert path.suffix == ".md"


def test_draft_contains_needs_approval_status(vitem, tmp_path):
    path = write_draft(vitem, [passing_result(0, "teks")], 1,
                       now=NOW, draft_dir=tmp_path)
    text = path.read_text()
    assert 'status: "needs_approval"' in text
    assert "No auto-posting" in text


def test_draft_contains_caption_image_text_source_and_facts(vitem, tmp_path):
    path = write_draft(vitem, [passing_result(0, "ini captionnya")], 1,
                       now=NOW, draft_dir=tmp_path)
    text = path.read_text()
    assert "ini captionnya" in text
    assert "Harga rumah naik" in text          # image text
    assert vitem.item.url in text              # source url
    assert "CNN Indonesia" in text             # source name
    assert "8,43" in text                      # verified fact
    assert "supporting quote" in text


def test_draft_lists_every_passing_variant(vitem, tmp_path):
    results = [passing_result(0, "satu"), passing_result(1, "dua"),
               passing_result(2, "tiga")]
    text = write_draft(vitem, results, 1, now=NOW, draft_dir=tmp_path).read_text()
    for needle in ["Variant A", "Variant B", "Variant C", "satu", "dua", "tiga"]:
        assert needle in text
    assert "variants_passing: 3" in text
    assert 'variants_passing_ids: "A, B, C"' in text


def test_variant_ids_are_stable_when_only_some_pass(vitem, tmp_path):
    """Variant C must still be called C when A and B failed, so the label
    means the same thing in the draft, the run log and the eval."""
    results = [failing_result(0), failing_result(1), passing_result(2, "tiga")]
    text = write_draft(vitem, results, 1, now=NOW, draft_dir=tmp_path).read_text()
    assert "### Variant C" in text
    assert "### Variant A" not in text
    assert 'variants_passing_ids: "C"' in text
    assert "**Variant A: FAILED**" in text
    assert "**Variant B: FAILED**" in text
    assert "**Variant C: passed**" in text


def test_draft_reports_failures_honestly(vitem, tmp_path):
    text = write_draft(vitem, [failing_result(0)], 1,
                       now=NOW, draft_dir=tmp_path).read_text()
    assert "variants_passing: 0" in text
    assert "None." in text
    assert "banned_phrase" in text
    assert "attempt 3" in text


def test_draft_records_dropped_facts(vitem, tmp_path):
    vitem.facts_dropped = 2
    text = write_draft(vitem, [passing_result(0, "teks")], 1,
                       now=NOW, draft_dir=tmp_path).read_text()
    assert "2 extracted fact(s) were dropped" in text


def test_draft_mixed_pass_and_fail(vitem, tmp_path):
    results = [passing_result(0, "bagus"), failing_result(1)]
    text = write_draft(vitem, results, 1, now=NOW, draft_dir=tmp_path).read_text()
    assert "variants_passing: 1" in text
    assert "variants_attempted: 2" in text
    assert "Variant B: FAILED" in text
