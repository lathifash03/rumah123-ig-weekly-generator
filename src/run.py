"""Orchestrator. One module per pipeline step, wired together here.

Run:  python -m src.run
Every step records what actually happened in run_log.json.
"""
from __future__ import annotations

import argparse
import sys

from . import draft, extract, filter as filter_mod, rank, retry
from .config import ConfigError, env
from .llm import LLM
from .runlog import RunLog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Weekly IG post generator")
    parser.add_argument("--max-items", type=int, default=3,
                        help="How many ranked items to turn into drafts.")
    parser.add_argument("--variants", type=int, default=3,
                        help="Caption variants per item.")
    parser.add_argument("--max-retries", type=int, default=retry.MAX_RETRIES,
                        help="Retries per variant after a failure.")
    args = parser.parse_args(argv)

    try:
        settings = env(require_api_key=True)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    log = RunLog(model=settings.model)
    llm = LLM(settings=settings)
    print(f"model: {settings.model}")

    # --- step 1: ingest -------------------------------------------------------
    items, feeds_ok, feeds_failed = ingest_step(log)
    print(f"ingest: {len(items)} items in window, "
          f"{len(feeds_ok)} feeds ok, {len(feeds_failed)} failed")
    if not items:
        log.error("no items fetched from any feed")
        log.finish("no_items", llm.usage.as_dict())
        log.write()
        print("no items fetched. run_log.json written.")
        return 1

    # --- step 2: filter and dedupe -------------------------------------------
    relevant_items, rejected = filter_mod.relevant(items)
    log.count("after_relevance", len(relevant_items))
    log.set("relevance_rejected", len(rejected))
    deduped, dropped = filter_mod.dedupe(relevant_items)
    log.count("after_dedupe", len(deduped))
    log.set("dedupe_dropped", dropped)
    print(f"filter: {len(relevant_items)} relevant, {len(deduped)} after dedupe")

    if not deduped:
        log.error("no relevant items after filtering")
        log.finish("no_relevant_items", llm.usage.as_dict())
        log.write()
        print("no relevant items. run_log.json written.")
        return 1

    # --- step 3: rank ---------------------------------------------------------
    try:
        chosen, decisions = rank.rank(llm, deduped, top_n=args.max_items)
    except Exception as exc:
        log.error(f"ranking failed: {type(exc).__name__}: {exc}")
        log.finish("rank_failed", llm.usage.as_dict())
        log.write()
        print(f"ranking failed: {exc}", file=sys.stderr)
        return 1
    log.set("ranking", decisions)
    log.count("after_ranking", len(chosen))
    print(f"rank: {len(chosen)} item(s) chosen")

    # --- steps 4 to 9 ---------------------------------------------------------
    written: list[str] = []
    item_records: list[dict] = []
    index = 0

    for vitem_source in chosen:
        verified, ex_log = extract.extract(llm, vitem_source)
        log.data["extraction"].append(ex_log)
        print(f"extract: {vitem_source.title[:60]} -> "
              f"{len(verified.facts)} verified fact(s), "
              f"{verified.facts_dropped} dropped")

        record: dict = {
            "url": vitem_source.url,
            "title": vitem_source.title,
            "source": vitem_source.source_display,
            "facts_verified": len(verified.facts),
            "facts_dropped": verified.facts_dropped,
        }

        if not verified.facts:
            record["skipped"] = "no verified facts"
            item_records.append(record)
            print("  skipped: no verified facts")
            continue

        results = retry.run_item(llm, verified, variants=args.variants,
                                 max_retries=args.max_retries)
        record["variants"] = [
            {
                "variant_index": r.variant_index,
                "variant_id": r.variant_id,
                "passed": r.passed,
                "first_attempt_passed": r.first_attempt_passed,
                "attempts": r.attempts,
            }
            for r in results
        ]
        passing = sum(1 for r in results if r.passed)
        record["variants_passing"] = passing
        print(f"  variants: {passing}/{len(results)} passed")

        index += 1
        path = draft.write_draft(verified, results, index)
        rel = str(path.relative_to(path.parent.parent.parent))
        record["draft"] = rel
        written.append(rel)
        print(f"  draft: {rel}")
        item_records.append(record)

    log.set("items", item_records)
    log.count("drafts_written", len(written))
    log.set("drafts", written)
    log.finish("ok" if written else "no_drafts", llm.usage.as_dict())
    path = log.write()
    print(f"\n{len(written)} draft(s) written. log: {path.name}")
    print(f"tokens: {llm.usage.as_dict()}")
    return 0 if written else 1


def ingest_step(log: RunLog):
    from . import ingest
    items, ok, failed = ingest.fetch_all()
    log.set("feeds_ok", ok)
    log.set("feeds_failed", failed)
    log.count("fetched_in_window", len(items))
    return items, ok, failed


if __name__ == "__main__":
    raise SystemExit(main())
