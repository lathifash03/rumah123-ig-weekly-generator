"""Pydantic models plus the JSON schemas sent to the model as structured
output schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Item(BaseModel):
    """One candidate news item from a feed. Full article text is never stored."""

    title: str
    url: str
    published: str          # ISO 8601
    source: str             # feed name
    source_display: str     # short name used for attribution in the caption
    summary: str = ""
    keywords_matched: list[str] = Field(default_factory=list)


class Fact(BaseModel):
    claim: str
    quote: str


class VerifiedItem(BaseModel):
    item: Item
    facts: list[Fact] = Field(default_factory=list)
    facts_dropped: int = 0


class Caption(BaseModel):
    caption: str
    image_text: str


class ClaimCheckResult(BaseModel):
    claim: str
    supported: bool
    quote: str = ""


# --- JSON schemas for OpenAI structured outputs -------------------------------
# strict mode requires additionalProperties: false and every property listed
# in "required".

RANK_SCHEMA = {
    "name": "ranking",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["top"],
        "properties": {
            "top": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["index", "score", "has_concrete_facts", "reason"],
                    "properties": {
                        "index": {"type": "integer"},
                        "score": {"type": "integer"},
                        "has_concrete_facts": {"type": "boolean"},
                        "reason": {"type": "string"},
                    },
                },
            }
        },
    },
}

EXTRACT_SCHEMA = {
    "name": "extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["facts"],
        "properties": {
            "facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["claim", "quote"],
                    "properties": {
                        "claim": {"type": "string"},
                        "quote": {"type": "string"},
                    },
                },
            }
        },
    },
}

GENERATE_SCHEMA = {
    "name": "caption",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["caption", "image_text"],
        "properties": {
            "caption": {"type": "string"},
            "image_text": {"type": "string"},
        },
    },
}

CLAIMCHECK_SCHEMA = {
    "name": "claimcheck",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["claims"],
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["claim", "supported", "quote"],
                    "properties": {
                        "claim": {"type": "string"},
                        "supported": {"type": "boolean"},
                        "quote": {"type": "string"},
                    },
                },
            }
        },
    },
}
