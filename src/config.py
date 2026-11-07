"""Configuration loading. The model name is never hardcoded."""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
PROMPT_DIR = ROOT / "prompts"
DRAFT_DIR = ROOT / "drafts"


class ConfigError(RuntimeError):
    pass


def load_yaml(name: str) -> dict:
    path = CONFIG_DIR / name
    if not path.exists():
        raise ConfigError(f"missing config file: {path}")
    with path.open() as fh:
        return yaml.safe_load(fh)


def sources() -> dict:
    return load_yaml("sources.yaml")


def rules() -> dict:
    return load_yaml("rules.yaml")


def prompt(name: str) -> str:
    path = PROMPT_DIR / name
    if not path.exists():
        raise ConfigError(f"missing prompt file: {path}")
    return path.read_text()


def prompt_version(name: str) -> str:
    """Short sha256 of a prompt file, recorded in run_log.json."""
    return hashlib.sha256((PROMPT_DIR / name).read_bytes()).hexdigest()[:16]


def prompt_versions() -> dict[str, str]:
    return {p.name: prompt_version(p.name) for p in sorted(PROMPT_DIR.glob("*.md"))}


@dataclass(frozen=True)
class Env:
    api_key: str
    model: str


def env(require_api_key: bool = True) -> Env:
    """Read OPENAI_API_KEY and OPENAI_MODEL from .env or the environment.

    OPENAI_MODEL has no default on purpose: the model must be an explicit,
    recorded choice rather than something buried in the source.
    """
    load_dotenv(ROOT / ".env")
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("OPENAI_MODEL", "").strip()
    if require_api_key and not key:
        raise ConfigError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in."
        )
    if not model:
        raise ConfigError(
            "OPENAI_MODEL is not set. Set it in .env - it is deliberately not "
            "hardcoded in the source."
        )
    return Env(api_key=key, model=model)
