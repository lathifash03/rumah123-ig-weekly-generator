"""Step 5: generate caption variants in Indonesian from verified facts."""
from __future__ import annotations

from .config import prompt
from .models import GENERATE_SCHEMA, Caption, VerifiedItem

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
) -> str:
    parts = [render_facts(vitem)]
    angle = VARIANT_ANGLES[variant_index % len(VARIANT_ANGLES)]
    parts.append(f"\nVARIANT ANGLE: {angle}")
    if failures_text:
        parts.append(
            "\nFAILURES from your previous attempt. Fix every one of them:\n"
            + failures_text
        )
    return "\n".join(parts)


def generate(llm, vitem: VerifiedItem, variant_index: int,
             failures_text: str = "") -> Caption:
    data = llm.json(
        prompt("generate.md"),
        build_user_message(vitem, variant_index, failures_text),
        GENERATE_SCHEMA,
    )
    return Caption(caption=data.get("caption", ""),
                   image_text=data.get("image_text", ""))
