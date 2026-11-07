"""Guards on configuration, prompt files and the no-hardcoded-model rule."""
import re

import pytest

from src import config


# --- prompts ------------------------------------------------------------------

REQUIRED_PROMPTS = ["rank.md", "extract.md", "generate.md", "claimcheck.md"]


@pytest.mark.parametrize("name", REQUIRED_PROMPTS)
def test_prompt_file_exists_and_is_not_empty(name):
    text = config.prompt(name)
    assert len(text.strip()) > 200


@pytest.mark.parametrize("name", REQUIRED_PROMPTS)
def test_prompt_states_a_json_output_schema(name):
    text = config.prompt(name)
    assert "JSON" in text
    assert "{" in text and "}" in text


def test_prompt_version_is_a_stable_hash():
    a = config.prompt_version("generate.md")
    b = config.prompt_version("generate.md")
    assert a == b and len(a) == 16


def test_prompt_versions_covers_every_prompt():
    versions = config.prompt_versions()
    for name in REQUIRED_PROMPTS:
        assert name in versions


def test_generate_prompt_states_the_hard_constraints():
    text = config.prompt("generate.md").lower()
    for needle in ["90 words", "two hashtags", "em dash", "semicolon",
                   "#rumah123", "kamu"]:
        assert needle in text, needle


def test_generate_prompt_forbids_inventing_numbers():
    text = config.prompt("generate.md").lower()
    assert "never invent" in text


def test_extract_prompt_demands_exact_quotes():
    text = config.prompt("extract.md").lower()
    assert "character for character" in text


def test_claimcheck_prompt_treats_unsure_as_unsupported():
    text = config.prompt("claimcheck.md").lower()
    assert "unsure" in text


def test_missing_prompt_raises():
    with pytest.raises(config.ConfigError):
        config.prompt("does-not-exist.md")


# --- config files -------------------------------------------------------------

def test_sources_config_has_verified_feeds():
    cfg = config.sources()
    assert cfg["feeds"]
    for feed in cfg["feeds"]:
        assert feed["url"].startswith("http")
        assert feed["name"] and feed["display"]
        assert feed["verified"]


def test_sources_config_declares_a_window():
    assert config.sources()["window_days"] == 7


def test_rules_config_has_every_caption_rule():
    caption = config.rules()["caption"]
    for key in ["max_words_excluding_hashtags", "hashtag_count",
                "required_hashtag", "max_emoji", "banned_phrases",
                "forbidden_characters", "brand_tokens"]:
        assert key in caption, key


def test_caption_limits_match_the_brief():
    caption = config.rules()["caption"]
    assert caption["max_words_excluding_hashtags"] == 90
    assert caption["hashtag_count"] == 2
    assert caption["required_hashtag"] == "#Rumah123"
    assert caption["max_emoji"] == 1


def test_missing_config_raises():
    with pytest.raises(config.ConfigError):
        config.load_yaml("nope.yaml")


# --- the no-hardcoded-model rule ---------------------------------------------

MODEL_PATTERN = re.compile(
    r"\b(gpt-[0-9a-z.\-]+|o[0-9]-(mini|preview)|chatgpt-[0-9a-z.\-]+|"
    r"text-davinci[0-9a-z.\-]*)\b",
    re.I,
)


def test_no_model_name_is_hardcoded_in_src():
    """The model must come from OPENAI_MODEL, not from the source."""
    offenders = []
    for path in sorted((config.ROOT / "src").glob("*.py")):
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if MODEL_PATTERN.search(line):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert offenders == [], "hardcoded model name(s): " + "; ".join(offenders)


def test_env_requires_an_explicit_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("OPENAI_MODEL", "")
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None)
    with pytest.raises(config.ConfigError, match="OPENAI_MODEL"):
        config.env()


def test_env_requires_an_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENAI_MODEL", "some-model")
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None)
    with pytest.raises(config.ConfigError, match="OPENAI_API_KEY"):
        config.env()


def test_env_reads_both_values(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("OPENAI_MODEL", "some-model")
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None)
    settings = config.env()
    assert settings.model == "some-model"


# --- secret hygiene -----------------------------------------------------------

def test_gitignore_excludes_dotenv():
    text = (config.ROOT / ".gitignore").read_text()
    assert ".env" in text


def test_env_example_has_no_filled_in_key():
    text = (config.ROOT / ".env.example").read_text()
    assert "OPENAI_API_KEY=" in text
    for line in text.splitlines():
        if line.startswith("OPENAI_API_KEY="):
            assert line.strip() == "OPENAI_API_KEY="
