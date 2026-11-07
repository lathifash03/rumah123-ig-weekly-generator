"""run_log.json records what actually happened."""
import json

from src.runlog import RunLog


def test_log_has_the_required_fields(tmp_path):
    log = RunLog(model="some-model")
    log.set("feeds_ok", [{"name": "a"}])
    log.set("feeds_failed", [{"name": "b", "error": "HTTP 403"}])
    log.count("fetched_in_window", 10)
    log.count("after_relevance", 4)
    log.finish("ok", {"total_tokens": 123, "calls": 5})
    path = log.write(tmp_path / "run_log.json")

    data = json.loads(path.read_text())
    for key in ["run_started_utc", "run_finished_utc", "duration_seconds",
                "model", "prompt_versions", "feeds_ok", "feeds_failed",
                "counts", "tokens", "status"]:
        assert key in data, key
    assert data["model"] == "some-model"
    assert data["counts"]["fetched_in_window"] == 10
    assert data["tokens"]["total_tokens"] == 123
    assert data["status"] == "ok"


def test_prompt_versions_are_recorded():
    log = RunLog(model="m")
    versions = log.data["prompt_versions"]
    assert "generate.md" in versions
    assert len(versions["generate.md"]) == 16


def test_errors_accumulate():
    log = RunLog(model="m")
    log.error("first")
    log.error("second")
    assert log.data["errors"] == ["first", "second"]


def test_status_starts_incomplete():
    assert RunLog(model="m").data["status"] == "incomplete"
