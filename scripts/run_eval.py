"""Run the full evaluation: ask Qwen3 to strengthen every weak spec in REGISTRY,
compile the suggestions, and report whether they actually kill the mutants.

Usage:
    TINKER_API_KEY=tml-... python scripts/run_eval.py
    TINKER_API_KEY=tml-... python scripts/run_eval.py --cases sort jwt

Writes:
    eval-results/<UTC-timestamp>/scoreboard.md
    eval-results/<UTC-timestamp>/<case>.md   (raw suggestion + parsed result)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from examples import REGISTRY
from specstress.eval import EvalRow, run_eval_one
from specstress.llm import suggest_stronger_spec


def _check_marker(success: bool, after_diag: str) -> str:
    if success:
        return "PASS"
    if after_diag == "ERROR":
        return "ERROR"
    if after_diag == "SKIPPED":
        return "SKIP"
    return "FAIL"


def _render_scoreboard(rows: list[EvalRow], model: str, elapsed: float) -> str:
    lines = [
        "# SpecStress evaluation scoreboard",
        "",
        f"- **Model:** `{model}`",
        f"- **Run time:** {elapsed:.1f}s",
        f"- **Total cases:** {len(rows)}",
        f"- **PASS:** {sum(1 for r in rows if r.success)} / {len(rows)}",
        "",
        "| Case | Before | After | Score | Ref passes | Result |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        marker = _check_marker(r.success, r.after_diagnosis)
        lines.append(
            f"| `{r.case_name}` | {r.before_diagnosis} | {r.after_diagnosis} | "
            f"{r.after_score:.2f} | {'yes' if r.ref_passes else 'no'} | **{marker}** |"
        )
    lines.append("")
    error_rows = [r for r in rows if r.error]
    if error_rows:
        lines.append("## Errors / notes")
        lines.append("")
        for r in error_rows:
            lines.append(f"- `{r.case_name}`: {r.error}")
        lines.append("")
    return "\n".join(lines)


def _render_case_artifact(row: EvalRow) -> str:
    parts = [
        f"# Eval artifact — `{row.case_name}`",
        "",
        f"- Before: **{row.before_diagnosis}** (score {row.before_score:.2f})",
        f"- After:  **{row.after_diagnosis}** (score {row.after_score:.2f})",
        f"- Reference passes: {row.ref_passes}",
        f"- Success (after == STRONG, score == 1.0): **{row.success}**",
    ]
    if row.error:
        parts += ["", f"## Error\n\n```\n{row.error}\n```"]
    if row.raw_suggestion:
        parts += ["", "## Raw model output", "", row.raw_suggestion]
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases",
        nargs="*",
        default=None,
        help="Subset of cases to evaluate (default: all in REGISTRY).",
    )
    parser.add_argument(
        "--spec",
        default="weak",
        help="Which spec name to stress-test in each case (default: weak).",
    )
    args = parser.parse_args()

    if not os.environ.get("TINKER_API_KEY"):
        print("ERROR: TINKER_API_KEY is not set", file=sys.stderr)
        return 2

    names = args.cases or list(REGISTRY.keys())
    unknown = [n for n in names if n not in REGISTRY]
    if unknown:
        print(f"ERROR: unknown case(s): {unknown}", file=sys.stderr)
        return 2

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "eval-results" / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Writing results to {out_dir.relative_to(ROOT)}/")

    t0 = time.time()
    rows: list[EvalRow] = []
    for name in names:
        case = REGISTRY[name]
        print(f"  -> {name} ... ", end="", flush=True)
        t_case = time.time()
        row = run_eval_one(case, args.spec, suggester=suggest_stronger_spec)
        marker = _check_marker(row.success, row.after_diagnosis)
        print(f"{marker} (after={row.after_diagnosis}, score={row.after_score:.2f}, "
              f"{time.time() - t_case:.1f}s)")
        rows.append(row)
        (out_dir / f"{name}.md").write_text(_render_case_artifact(row))

    elapsed = time.time() - t0
    from specstress.llm import DEFAULT_MODEL
    scoreboard = _render_scoreboard(rows, DEFAULT_MODEL, elapsed)
    (out_dir / "scoreboard.md").write_text(scoreboard)
    print()
    print(scoreboard)
    return 0 if all(r.success for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
