"""Feed ingestion: 7 day window, failure recording, no exceptions escaping."""
import datetime as dt

import pytest

from src import ingest as ingest_mod


class FakeResponse:
    def __init__(self, content=b"", status_code=200):
        self.content = content
        self.status_code = status_code


def rss(entries):
    items = "".join(
        f"<item><title>{t}</title><link>{l}</link>"
        f"<pubDate>{d}</pubDate><description>{s}</description></item>"
        for t, l, d, s in entries
    )
    return (b"<?xml version='1.0'?><rss version='2.0'><channel>"
            + f"<title>Fake</title>{items}".encode()
            + b"</channel></rss>")


NOW = dt.datetime(2026, 11, 7, 12, 0, tzinfo=dt.timezone.utc)


def fmt(days_ago):
    d = NOW - dt.timedelta(days=days_ago)
    return d.strftime("%a, %d %b %Y %H:%M:%S +0000")


def test_only_items_inside_the_window_are_kept(monkeypatch):
    body = rss([
        ("Berita KPR Baru", "https://a.co/1", fmt(1), "soal kpr"),
        ("Berita Lama", "https://a.co/2", fmt(30), "soal kpr"),
    ])
    monkeypatch.setattr(ingest_mod.requests, "get",
                        lambda *a, **k: FakeResponse(body))
    items, ok, failed = ingest_mod.fetch_all(now=NOW)
    urls = [i.url for i in items]
    assert "https://a.co/1" in urls
    assert "https://a.co/2" not in urls
    assert failed == []


def test_http_error_is_recorded_as_a_failed_feed(monkeypatch):
    monkeypatch.setattr(ingest_mod.requests, "get",
                        lambda *a, **k: FakeResponse(b"", 403))
    items, ok, failed = ingest_mod.fetch_all(now=NOW)
    assert items == []
    assert len(failed) > 0
    assert all("HTTP 403" in f["error"] for f in failed)
    assert all("url" in f and "name" in f for f in failed)


def test_network_exception_is_recorded_not_raised(monkeypatch):
    def boom(*a, **k):
        raise OSError("dns failure")
    monkeypatch.setattr(ingest_mod.requests, "get", boom)
    items, ok, failed = ingest_mod.fetch_all(now=NOW)
    assert items == []
    assert all("dns failure" in f["error"] for f in failed)


def test_empty_feed_is_recorded_as_a_failure(monkeypatch):
    monkeypatch.setattr(ingest_mod.requests, "get",
                        lambda *a, **k: FakeResponse(rss([])))
    items, ok, failed = ingest_mod.fetch_all(now=NOW)
    assert items == []
    assert all(f["error"] == "parsed but 0 entries" for f in failed)


def test_items_carry_source_and_display_name(monkeypatch):
    body = rss([("Berita KPR", "https://a.co/1", fmt(1), "kpr")])
    monkeypatch.setattr(ingest_mod.requests, "get",
                        lambda *a, **k: FakeResponse(body))
    items, ok, failed = ingest_mod.fetch_all(now=NOW)
    assert items
    assert all(i.source and i.source_display for i in items)


def test_ok_report_counts_entries_and_kept(monkeypatch):
    body = rss([("A", "https://a.co/1", fmt(1), "x"),
                ("B", "https://a.co/2", fmt(40), "x")])
    monkeypatch.setattr(ingest_mod.requests, "get",
                        lambda *a, **k: FakeResponse(body))
    items, ok, failed = ingest_mod.fetch_all(now=NOW)
    assert ok[0]["entries"] == 2
    assert ok[0]["kept_in_window"] == 1


def test_item_with_no_date_is_skipped_and_counted(monkeypatch):
    body = (b"<?xml version='1.0'?><rss version='2.0'><channel><title>F</title>"
            b"<item><title>No date</title><link>https://a.co/9</link></item>"
            b"</channel></rss>")
    monkeypatch.setattr(ingest_mod.requests, "get",
                        lambda *a, **k: FakeResponse(body))
    items, ok, failed = ingest_mod.fetch_all(now=NOW)
    assert items == []
    assert ok[0]["skipped_no_date"] == 1
