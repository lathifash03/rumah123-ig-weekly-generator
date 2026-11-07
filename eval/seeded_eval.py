"""Seeded-error test of the claim checker and the pure-code validators.

Reads eval/seeded_errors.json, runs both layers over every case, and writes
eval/seeded_results.md from the real run only.

Each error case carries exactly one planted fault. The controls are faithful
to the facts. A case counts as caught when either layer produces at least one
failure, and the report separates the two layers so it is clear which one did
the work.

Run:  python eval/seeded_eval.py

This spends API calls: one claim-check call per case. The claim check is run
on every case, including those the code validators already reject, because the
point is to measure the claim checker itself rather than the pipeline's
short-circuit.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.claimcheck import check                      # noqa: E402
from src.config import env, prompt_versions           # noqa: E402
from src.llm import LLM                               # noqa: E402
from src.models import Fact                           # noqa: E402
from src.validate import validate                     # noqa: E402

CASES = ROOT / "eval" / "seeded_errors.json"
OUT = ROOT / "eval" / "seeded_results.md"
RAW = ROOT / "eval" / "seeded_run.json"


def pct(num: int, den: int) -> str:
    return "n/a" if den == 0 else f"{100.0 * num / den:.0f}%"


def run(repeats: int = 3) -> dict:
    """Run every case `repeats` times.

    Repeats exist because the claim checker is not deterministic. Two single
    passes over this set gave 10 of 10 and then 9 of 10, with the wrong
    attribution case caught once and missed once. A single pass therefore
    reports luck as much as capability, so each case is run several times and
    the per-case catch count is reported.

    The pure-code layer is deterministic, so it is evaluated once per case.
    """
    data = json.loads(CASES.read_text())
    facts = [Fact(**f) for f in data["facts"]]
    source = data["source_display"]

    settings = env(require_api_key=True)
    llm = LLM(settings=settings)

    results = []
    for case in data["cases"]:
        caption = case["caption"]

        code_failures = validate(caption, facts, source)
        code_rules = sorted({f.rule for f in code_failures})
        caught_by_code = bool(code_rules)

        trials = []
        for _ in range(repeats):
            try:
                cc_failures, cc_detail = check(llm, caption, facts)
                trials.append({
                    "llm_rules": sorted({f.rule for f in cc_failures}),
                    "llm_messages": [str(f) for f in cc_failures],
                    "llm_verdicts": [d.get("verdict") for d in cc_detail],
                    "llm_error": None,
                })
            except Exception as exc:
                trials.append({
                    "llm_rules": [], "llm_messages": [], "llm_verdicts": [],
                    "llm_error": f"{type(exc).__name__}: {exc}"[:200],
                })

        llm_catches = sum(1 for t in trials if t["llm_rules"])
        # a case counts as caught in a trial if either layer fired
        trial_catches = sum(1 for t in trials
                            if t["llm_rules"] or caught_by_code)

        results.append({
            "id": case["id"],
            "error_type": case["error_type"],
            "should_be_caught": case["should_be_caught"],
            "planted": case["planted"],
            "repeats": repeats,
            "caught_in_trials": trial_catches,
            "llm_caught_in_trials": llm_catches,
            "caught_always": trial_catches == repeats,
            "caught_ever": trial_catches > 0,
            "caught_by_code": caught_by_code,
            "code_rules": code_rules,
            "code_messages": [str(f) for f in code_failures],
            "llm_rules_union": sorted({r for t in trials
                                       for r in t["llm_rules"]}),
            "trials": trials,
        })

        flag = "control" if not case["should_be_caught"] else "error  "
        print(f"{case['id']} {flag} {case['error_type']:34} "
              f"caught {trial_catches}/{repeats} (llm {llm_catches}/{repeats})")
        if code_rules:
            print(f"     code: {code_rules}")
        union = sorted({r for t in trials for r in t["llm_rules"]})
        if union:
            print(f"     llm : {union}")
        for t in trials:
            if t["llm_error"]:
                print(f"     llm call failed: {t['llm_error']}")

    return {
        "model": settings.model,
        "repeats": repeats,
        "prompt_versions": prompt_versions(),
        "results": results,
        "tokens": llm.usage.as_dict(),
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def render(run_data: dict, about: str) -> str:
    results = run_data["results"]
    repeats = run_data.get("repeats", 1)
    errors = [r for r in results if r["should_be_caught"]]
    controls = [r for r in results if not r["should_be_caught"]]

    always = [r for r in errors if r["caught_always"]]
    sometimes = [r for r in errors if r["caught_ever"] and not r["caught_always"]]
    never = [r for r in errors if not r["caught_ever"]]
    fp_ever = [r for r in controls if r["caught_ever"]]

    code_only = [r for r in errors
                 if r["caught_by_code"] and not r["llm_rules_union"]]
    llm_only = [r for r in errors
                if not r["caught_by_code"] and r["llm_rules_union"]]
    both = [r for r in errors if r["caught_by_code"] and r["llm_rules_union"]]

    total_trials = len(errors) * repeats
    total_caught = sum(r["caught_in_trials"] for r in errors)

    lines = [
        "# Seeded-error test",
        "",
        "Generated by `eval/seeded_eval.py` from a real run against the API. "
        "Every number below comes from that run.",
        "",
        f"- Model: `{run_data['model']}`",
        f"- Claim-check prompt: `{run_data['prompt_versions'].get('claimcheck.md')}`",
        f"- Repeats per case: {repeats}",
        f"- Generated: `{run_data['generated_utc']}`",
        "",
        "## What this measures",
        "",
        about,
        "",
        "**No prompt was changed in response to these results.** The cases were "
        "written, the fixtures were checked once for carrying exactly one "
        "planted fault each, and the runs below were then executed and "
        "reported as they came out.",
        "",
        "## How much this proves",
        "",
        "Read the numbers below with these limits in mind.",
        "",
        f"- **The set is small.** {len(errors)} seeded errors and "
        f"{len(controls)} controls. One extra failing case would move the rate "
        f"by about {100 // max(1, len(errors))} points.",
        "- **The cases were written by the same person who wrote the rules.** "
        "They test failure modes that were already known, several taken from "
        "real failures in run 5. This measures whether the known guards fire, "
        "not whether the system is hard to fool.",
        "- **The claim checker is not deterministic.** Two earlier single "
        "passes over this same set gave 10 of 10 and then 9 of 10, with the "
        "wrong-attribution case caught once and missed once. That is why every "
        "case is now run several times and the per-case catch count is "
        "reported instead of a single pass.",
        "- **One fault per case, with one exception.** `E02` plants a dropped "
        "hedge, but \"tidak berubah\" is also an unsupported absolute, so two "
        "independent rules fire on one planted fault.",
        "- **The controls are the weakest part.** Two clean captions cannot "
        "establish a false-positive rate. The real false-positive evidence is "
        "the pipeline run, where strict rules reject copy that reads fine.",
        "- Both layers are evaluated on every case, including cases the code "
        "already rejects, so the claim checker's own contribution is visible "
        "rather than hidden behind the pipeline's short-circuit.",
        "",
        "## Headline numbers",
        "",
        "| Measure | Count | Rate |",
        "| --- | --- | --- |",
        f"| Seeded errors | {len(errors)} | - |",
        f"| Caught in every repeat | {len(always)} | "
        f"{pct(len(always), len(errors))} |",
        f"| Caught in some repeats only | {len(sometimes)} | "
        f"{pct(len(sometimes), len(errors))} |",
        f"| Never caught | {len(never)} | {pct(len(never), len(errors))} |",
        f"| Trial-level catch rate | {total_caught}/{total_trials} | "
        f"{pct(total_caught, total_trials)} |",
        f"| Controls | {len(controls)} | - |",
        f"| Controls flagged in any repeat | {len(fp_ever)} | "
        f"{pct(len(fp_ever), len(controls))} |",
        "",
        "The strict reading is the one to quote: "
        f"{len(always)} of {len(errors)} seeded errors were caught every time. "
        f"{len(sometimes)} were caught only sometimes, which means the system "
        "would let them through on an unlucky run.",
        "",
        "## Which layer caught it",
        "",
        "The pure-code layer is deterministic, so it either catches a case or "
        "never does. The claim checker varies between repeats.",
        "",
        "| Layer | Count |",
        "| --- | --- |",
        f"| Pure code only | {len(code_only)} |",
        f"| Claim checker only | {len(llm_only)} |",
        f"| Both | {len(both)} |",
        f"| Neither | {len(never)} |",
        "",
    ]
    if llm_only:
        lines += [
            "The cases caught by the claim checker alone are the ones that "
            "justify its cost: "
            + ", ".join(f"`{r['id']}` ({r['error_type']})" for r in llm_only)
            + ".",
            "",
        ]

    lines += [
        "## Case by case",
        "",
        f"| Case | Planted fault | Caught | Code (deterministic) | "
        f"Claim checker ({repeats} repeats) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in results:
        n, total = r["caught_in_trials"], r["repeats"]
        if r["should_be_caught"]:
            if n == total:
                verdict = f"{n}/{total}"
            elif n == 0:
                verdict = f"**MISS 0/{total}**"
            else:
                verdict = f"**FLAKY {n}/{total}**"
        else:
            verdict = (f"**FALSE POSITIVE {n}/{total}**" if n
                       else f"clean 0/{total} (correct)")
        code = ", ".join(f"`{x}`" for x in r["code_rules"]) or "-"
        llm = (", ".join(f"`{x}`" for x in r["llm_rules_union"])
               + f" ({r['llm_caught_in_trials']}/{total})") \
            if r["llm_rules_union"] else f"- (0/{total})"
        lines.append(f"| `{r['id']}` | {r['error_type']} | {verdict} | "
                     f"{code} | {llm} |")

    lines += ["", "## Misses and flaky cases", ""]
    if not never and not sometimes:
        lines.append("None. Every seeded error was caught in every repeat.")
    for r in never + sometimes:
        label = "never caught" if not r["caught_ever"] else \
            f"caught {r['caught_in_trials']} of {r['repeats']} times"
        lines += [
            f"### `{r['id']}` {r['error_type']} - {label}",
            "",
            f"- Planted: {r['planted']}",
            f"- Code rules: {r['code_rules'] or 'none, this case relies on the claim checker'}",
            "- Per repeat:",
        ]
        for i, t in enumerate(r["trials"], 1):
            got = t["llm_rules"] or "nothing"
            lines.append(f"  - repeat {i}: {got}")
            if t["llm_error"]:
                lines.append(f"    - call failed: {t['llm_error']}")
        lines.append("")

    lines += ["## False positives on the controls", ""]
    if not fp_ever:
        lines.append("None. Both controls passed both layers in every repeat.")
    else:
        for r in fp_ever:
            lines += [
                f"### `{r['id']}` flagged in "
                f"{r['caught_in_trials']} of {r['repeats']} repeats",
                "",
                f"- Code rules fired: {r['code_rules']}",
            ]
            for m in r["code_messages"]:
                lines.append(f"  - {m}")
            for i, t in enumerate(r["trials"], 1):
                if t["llm_messages"]:
                    lines.append(f"- repeat {i}:")
                    for m in t["llm_messages"]:
                        lines.append(f"  - {m}")
            lines.append("")

    lines += ["## Every failure message, verbatim", ""]
    for r in results:
        msgs = list(r["code_messages"])
        seen = set(msgs)
        for t in r["trials"]:
            for m in t["llm_messages"]:
                if m not in seen:
                    seen.add(m)
                    msgs.append(m)
        if not msgs:
            continue
        lines += [f"**`{r['id']}` {r['error_type']}**", ""]
        for m in msgs:
            lines.append(f"- {m}")
        lines.append("")

    tokens = run_data["tokens"]
    lines += [
        "## Cost",
        "",
        f"- Claim-check calls: {tokens.get('calls')}",
        f"- Input tokens: {tokens.get('prompt_tokens')}",
        f"- Output tokens: {tokens.get('completion_tokens')}",
        f"- Total tokens: {tokens.get('total_tokens')}",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    if not CASES.exists():
        print(f"{CASES} not found", file=sys.stderr)
        return 2
    about = json.loads(CASES.read_text())["about"]
    repeats = 3
    for i, arg in enumerate(sys.argv):
        if arg == "--repeats" and i + 1 < len(sys.argv):
            repeats = int(sys.argv[i + 1])
    if "--render-only" in sys.argv:
        if not RAW.exists():
            print(f"{RAW} not found; run without --render-only first",
                  file=sys.stderr)
            return 2
        run_data = json.loads(RAW.read_text())
        print(f"re-rendering from {RAW.name}, no API calls made")
    else:
        run_data = run(repeats=repeats)
        RAW.write_text(json.dumps(run_data, indent=2, ensure_ascii=False) + "\n")
    OUT.write_text(render(run_data, about))

    results = run_data["results"]
    repeats = run_data.get("repeats", 1)
    errors = [r for r in results if r["should_be_caught"]]
    controls = [r for r in results if not r["should_be_caught"]]
    always = [r for r in errors if r["caught_always"]]
    flaky = [r for r in errors if r["caught_ever"] and not r["caught_always"]]
    never = [r for r in errors if not r["caught_ever"]]
    fps = [r for r in controls if r["caught_ever"]]
    print()
    print(f"caught in every repeat: {len(always)}/{len(errors)} "
          f"({pct(len(always), len(errors))})")
    print(f"flaky (some repeats):   {len(flaky)}/{len(errors)} "
          f"{[r['id'] for r in flaky]}")
    print(f"never caught:           {len(never)}/{len(errors)} "
          f"{[r['id'] for r in never]}")
    print(f"controls flagged:       {len(fps)}/{len(controls)} "
          f"({pct(len(fps), len(controls))})")
    print(f"tokens:              {run_data['tokens']}")
    print(f"written:             {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
