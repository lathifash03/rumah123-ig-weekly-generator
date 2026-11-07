"""run_log.json: a factual record of one real run.

Nothing here is written unless it actually happened.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from .config import ROOT, prompt_versions


class RunLog:
    def __init__(self, model: str) -> None:
        self.started = dt.datetime.now(dt.timezone.utc)
        self.data: dict[str, Any] = {
            "run_started_utc": self.started.isoformat(),
            "run_finished_utc": None,
            "duration_seconds": None,
            "model": model,
            "prompt_versions": prompt_versions(),
            "feeds_ok": [],
            "feeds_failed": [],
            "counts": {},
            "ranking": [],
            "extraction": [],
            "items": [],
            "tokens": {},
            "errors": [],
            "status": "incomplete",
        }

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def count(self, step: str, value: int) -> None:
        self.data["counts"][step] = value

    def error(self, message: str) -> None:
        self.data["errors"].append(message)

    def finish(self, status: str, tokens: dict | None = None) -> None:
        finished = dt.datetime.now(dt.timezone.utc)
        self.data["run_finished_utc"] = finished.isoformat()
        self.data["duration_seconds"] = round(
            (finished - self.started).total_seconds(), 1)
        self.data["status"] = status
        if tokens is not None:
            self.data["tokens"] = tokens

    def write(self, path: Path | None = None) -> Path:
        path = path or (ROOT / "run_log.json")
        path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n")
        return path
