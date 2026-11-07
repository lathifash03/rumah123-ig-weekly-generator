"""Step 5: generate caption variants in Indonesian from verified facts."""
from __future__ import annotations

import re

from .config import prompt, rules
from .models import GENERATE_SCHEMA, Caption, VerifiedItem
from .textutil import HASHTAG_RE

# Angle hints only steer the opening. They never add facts.
VARIANT_ANGLES = [
    "Open from the feeling of watching prices move while you are still saving.",
    "Open from a concrete everyday moment, such as comparing monthly numbers.",
    "Open from a quiet reassurance that being early in the process is normal.",
]


def render_facts(vitem: VerifiedItem) -> str:
    lines = [f"SOURCE NAME: {vitem.item.source_display}", "", "VERIFIED FACTS:"]
    for i, fact in enumerate(vitem.facts, 1):
        lines.append(f"{i}. claim: {fact.claim}")
        lines.append(f'   quote: "{fact.quote}"')
    return "\n".join(lines)


def build_user_message(
    vitem: VerifiedItem,
    variant_index: int,
    failures_text: str = "",
    previous_caption: str = "",
) -> str:
    """Build the generator's user message.

    On a retry the previous caption is included verbatim. Without it the model
    rewrites from scratch and loses parts that were already correct: in the
    first real run a caption failed only on the source name, and the retry
    fixed the source while dropping both hashtags, which then failed. The
    instruction to keep what was not reported as broken is impossible to
    follow if the model cannot see what it wrote.
    """
    parts = [render_facts(vitem)]
    angle = VARIANT_ANGLES[variant_index % len(VARIANT_ANGLES)]
    parts.append(f"\nVARIANT ANGLE: {angle}")
    if failures_text:
        if previous_caption:
            parts.append(
                "\nYOUR PREVIOUS CAPTION, which was rejected:\n"
                "---\n" + previous_caption.strip() + "\n---"
            )
            parts.append(
                "\nEdit that caption. Change only what the failures below "
                "require and leave everything else exactly as it is, "
                "including the hashtags and the source name if they were not "
                "reported as broken."
            )
        parts.append(
            "\nFAILURES from your previous attempt. Fix every one of them:\n"
            + failures_text
        )
    return "\n".join(parts)


def normalize_topic_hashtag(raw: str, required: str, fallbacks: list[str]) -> str:
    """Turn the model's chosen topic tag into one valid, distinct hashtag.

    The model picks the topic, which is a judgement call. Making it well
    formed is mechanical, so code does that part.
    """
    token = re.sub(r"\W", "", (raw or ""), flags=re.UNICODE)
    if token and f"#{token}".lower() != required.lower():
        return f"#{token}"
    for candidate in fallbacks:
        clean = re.sub(r"\W", "", candidate, flags=re.UNICODE)
        if clean and f"#{clean}".lower() != required.lower():
            return f"#{clean}"
    return "#Properti"


def assemble_caption(body: str, topic_hashtag: str, required: str) -> str:
    """Join the caption body to its hashtag line.

    The hashtag line is boilerplate: it carries no fact and no voice, and its
    rules are purely mechanical. Asking the model to emit it cost roughly half
    of all validation failures in the first real runs: the model omitted the
    line entirely about half the time however firmly the prompt asked for it.
    Building it in code makes that failure class impossible instead of
    retrying it.
    """
    # Drop any hashtags the model put in the body, so the result has exactly
    # the two the rules allow.
    clean_body = HASHTAG_RE.sub("", body or "").rstrip()
    return f"{clean_body}\n\n{required} {topic_hashtag}"


def generate(llm, vitem: VerifiedItem, variant_index: int,
             failures_text: str = "", previous_caption: str = "") -> Caption:
    cfg = rules()["caption"]
    required = cfg["required_hashtag"]

    data = llm.json(
        prompt("generate.md"),
        build_user_message(vitem, variant_index, failures_text,
                           previous_caption),
        GENERATE_SCHEMA,
    )
    topic = normalize_topic_hashtag(
        data.get("topic_hashtag", ""),
        required,
        vitem.item.keywords_matched or ["Properti"],
    )
    caption = assemble_caption(data.get("caption_body", ""), topic, required)
    return Caption(caption=caption, image_text=data.get("image_text", ""))
