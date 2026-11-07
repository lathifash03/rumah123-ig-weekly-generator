"""Step 8: the generate / validate / claim-check retry loop.

On any failure the exact failure list is sent back to the generator. Every
attempt and every failure reason is recorded for run_log.json.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import claimcheck, generate
from .models import Caption, VerifiedItem
from .validate import Failure, format_failures, validate

MAX_RETRIES = 2


def variant_id(index: int) -> str:
    """Stable label for a variant: A, B, C...

    The index is the identity, so the same variant carries the same label in
    the draft, the run log and the eval. Numbering only the passing variants
    1, 2, 3 made the labels shift depending on what passed.
    """
    return chr(ord("A") + index) if 0 <= index < 26 else f"V{index}"


@dataclass
class VariantResult:
    variant_index: int
    passed: bool
    caption: Caption | None
    attempts: list[dict] = field(default_factory=list)

    @property
    def variant_id(self) -> str:
        return variant_id(self.variant_index)

    @property
    def first_attempt_passed(self) -> bool:
        return bool(self.attempts) and not self.attempts[0]["failures"]


def run_variant(
    llm,
    vitem: VerifiedItem,
    variant_index: int,
    max_retries: int = MAX_RETRIES,
) -> VariantResult:
    """Generate one variant, validating and claim-checking each attempt."""
    attempts: list[dict] = []
    failures_text = ""
    previous_caption = ""
    caption: Caption | None = None

    for attempt_no in range(max_retries + 1):
        record: dict = {"attempt": attempt_no + 1}
        try:
            caption = generate.generate(llm, vitem, variant_index,
                                        failures_text, previous_caption)
        except Exception as exc:
            record["error"] = f"generate failed: {type(exc).__name__}: {exc}"[:200]
            record["failures"] = [record["error"]]
            attempts.append(record)
            failures_text = record["error"]
            continue

        record["caption"] = caption.caption
        record["image_text"] = caption.image_text

        # Pure-code validation first. It is cheap and deterministic, so a
        # caption that fails here never costs a claim-check call.
        failures: list[Failure] = validate(
            caption.caption, vitem.facts, vitem.item.source_display
        )
        record["validation_failures"] = [str(f) for f in failures]

        if not failures:
            try:
                cc_failures, cc_detail = claimcheck.check(
                    llm, caption.caption, vitem.facts
                )
            except Exception as exc:
                cc_failures = [Failure(
                    "claimcheck_error",
                    f"claim check call failed: {type(exc).__name__}: {exc}"[:160],
                )]
                cc_detail = []
            record["claimcheck_detail"] = cc_detail
            record["claimcheck_failures"] = [str(f) for f in cc_failures]
            failures = cc_failures
        else:
            record["claimcheck_failures"] = []
            record["claimcheck_detail"] = []
            record["claimcheck_skipped"] = "validation failed first"

        record["failures"] = [str(f) for f in failures]
        record["failure_rules"] = sorted({f.rule for f in failures})
        attempts.append(record)

        if not failures:
            return VariantResult(variant_index, True, caption, attempts)

        failures_text = format_failures(failures)
        previous_caption = caption.caption

    return VariantResult(variant_index, False, caption, attempts)


def run_item(llm, vitem: VerifiedItem, variants: int = 3,
             max_retries: int = MAX_RETRIES) -> list[VariantResult]:
    return [run_variant(llm, vitem, i, max_retries) for i in range(variants)]
