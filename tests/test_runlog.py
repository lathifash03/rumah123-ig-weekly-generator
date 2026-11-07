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


# --- timestamped archive ------------------------------------------------------
# Runs 1 to 4 of this project each overwrote run_log.json and were never
# committed, so what went wrong in them is traceable only to commit messages.

def test_write_logs_writes_both_current_and_timestamped(tmp_path, monkeypatch):
    from src import run as run_mod
    from src import runlog as runlog_mod

    monkeypatch.setattr(run_mod, "ROOT", tmp_path)
    monkeypatch.setattr(runlog_mod, "ROOT", tmp_path)

    log = RunLog(model="test-model")
    log.finish("ok", {"total_tokens": 1})
    current = run_mod.write_logs(log)

    assert current.name == "run_log.json"
    assert current.exists()

    stamp = log.started.strftime("%Y%m%dT%H%M%SZ")
    archive = tmp_path / f"run_log_{stamp}.json"
    assert archive.exists(), sorted(p.name for p in tmp_path.iterdir())


def test_the_two_logs_have_identical_content(tmp_path, monkeypatch):
    from src import run as run_mod
    from src import runlog as runlog_mod

    monkeypatch.setattr(run_mod, "ROOT", tmp_path)
    monkeypatch.setattr(runlog_mod, "ROOT", tmp_path)

    log = RunLog(model="test-model")
    log.count("fetched_in_window", 7)
    log.finish("ok", {"total_tokens": 42})
    run_mod.write_logs(log)

    stamp = log.started.strftime("%Y%m%dT%H%M%SZ")
    current = json.loads((tmp_path / "run_log.json").read_text())
    archive = json.loads((tmp_path / f"run_log_{stamp}.json").read_text())
    assert current == archive
    assert current["counts"]["fetched_in_window"] == 7


def test_a_second_run_does_not_overwrite_the_first_archive(tmp_path, monkeypatch):
    """The whole point: an earlier run stays readable after a later one."""
    import datetime as dt

    from src import run as run_mod
    from src import runlog as runlog_mod

    monkeypatch.setattr(run_mod, "ROOT", tmp_path)
    monkeypatch.setattr(runlog_mod, "ROOT", tmp_path)

    first = RunLog(model="model-one")
    first.started = dt.datetime(2026, 11, 7, 4, 22, 32, tzinfo=dt.timezone.utc)
    first.finish("ok", {})
    run_mod.write_logs(first)

    second = RunLog(model="model-two")
    second.started = dt.datetime(2026, 11, 7, 4, 49, 3, tzinfo=dt.timezone.utc)
    second.finish("ok", {})
    run_mod.write_logs(second)

    archives = sorted(p.name for p in tmp_path.glob("run_log_*.json"))
    assert archives == ["run_log_20261107T042232Z.json",
                        "run_log_20261107T044903Z.json"]
    # the first run is still readable with its own model recorded
    old = json.loads((tmp_path / "run_log_20261107T042232Z.json").read_text())
    assert old["model"] == "model-one"
    # run_log.json points at the latest
    assert json.loads((tmp_path / "run_log.json").read_text())["model"] == "model-two"
