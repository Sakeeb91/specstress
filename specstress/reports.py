from __future__ import annotations

from .models import CaseReport


def render_markdown(report: CaseReport) -> str:
    pct = f"{report.mutation_score * 100:.0f}%"
    lines: list[str] = []
    lines.append("# SpecStress Report")
    lines.append("")
    lines.append(f"**Case:** `{report.case_name}`  ")
    lines.append(f"**Spec:** `{report.spec_name}`  ")
    lines.append(f"**Diagnosis:** **{report.diagnosis}**  ")
    lines.append(f"**Mutation score:** {pct}  ")
    lines.append(f"**Reference passed:** {report.reference_passed}")
    lines.append("")

    lines.append("## Per-implementation results")
    lines.append("")
    lines.append("| Implementation | Passed | Counterexample |")
    lines.append("| --- | --- | --- |")
    for r in report.results:
        ce = (r.counterexample or "").replace("|", "\\|") or "—"
        lines.append(f"| `{r.impl_name}` | {'✅' if r.passed else '❌'} | {ce} |")
    lines.append("")

    if report.surviving_mutants:
        lines.append("## Surviving bad implementations")
        lines.append("")
        for name in report.surviving_mutants:
            lines.append(f"- `{name}`")
        lines.append("")

    if report.notes:
        lines.append("## Notes")
        lines.append("")
        for n in report.notes:
            lines.append(f"- {n}")
        lines.append("")

    failed = [r for r in report.results if not r.passed]
    if failed:
        lines.append("## Failure details")
        lines.append("")
        for r in failed:
            lines.append(f"### `{r.impl_name}`")
            lines.append("")
            lines.append("```")
            lines.append((r.error or "").strip())
            lines.append("```")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
