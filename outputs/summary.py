"""Run summary: console + TXT, plus per-run diff.jsonl (SPEC §8, README §16)."""
from __future__ import annotations

import json
from pathlib import Path


def write_diff(run_dir: Path, diff: list[dict]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    with open(run_dir / "diff.jsonl", "w", encoding="utf-8") as f:
        for row in diff:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_summary(stats: dict, diff: list[dict], failed_urls: list[str],
                  elapsed_s: float, budget_min: int) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("JOB SEEK RUN SUMMARY")
    lines.append("=" * 60)
    lines.append(f"Companies processed : {stats.get('companies', 0)}")
    lines.append(f"  ok / blocked / err: {stats.get('ok',0)} / "
                 f"{stats.get('blocked',0)} / {stats.get('errors',0)}")
    lines.append(f"Roles kept this run : {stats.get('kept', 0)}")

    counts = {}
    for d in diff:
        counts[d["change"]] = counts.get(d["change"], 0) + 1
    lines.append(f"Changes             : added={counts.get('added',0)} "
                 f"reopened={counts.get('reopened',0)} "
                 f"suspected_filled={counts.get('suspected_filled',0)} "
                 f"closed={counts.get('closed',0)}")
    lines.append(f"Elapsed             : {elapsed_s:.1f}s "
                 f"(budget {budget_min} min)")

    per = stats.get("per_company", {})
    if per:
        lines.append("-" * 60)
        lines.append("Per company:")
        for name, info in per.items():
            lines.append(f"  {name:<22} kept={info.get('kept',0):<3} "
                         f"rung={info.get('rung','-'):<10} status={info.get('status','-')}")

    if diff:
        lines.append("-" * 60)
        lines.append("New / changed postings:")
        for d in diff[:40]:
            lines.append(f"  [{d['change']:<16}] {d.get('company','')}: "
                         f"{d.get('title','')} ({d.get('location','')})")

    if failed_urls:
        lines.append("-" * 60)
        lines.append(f"Failed URLs ({len(failed_urls)}):")
        for u in failed_urls[:20]:
            lines.append(f"  {u}")

    lines.append("=" * 60)
    return "\n".join(lines)


def emit(run_dir: Path, text: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.txt").write_text(text, encoding="utf-8")
    print(text)
