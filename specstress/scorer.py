from __future__ import annotations

from typing import Any

from .models import RunResult


def score(results: list[RunResult], reference_name: str) -> dict[str, Any]:
    """Compute mutation score and diagnosis from a list of RunResults."""
    by_name = {r.impl_name: r for r in results}
    ref = by_name.get(reference_name)
    reference_passed = bool(ref and ref.passed)

    mutants = [r for r in results if r.impl_name != reference_name]
    total = len(mutants)
    surviving = [r.impl_name for r in mutants if r.passed]
    killed = total - len(surviving)
    mutation_score = (killed / total) if total else 0.0

    if not reference_passed and surviving:
        diagnosis = "AMBIGUOUS"
    elif not reference_passed:
        diagnosis = "OVERCONSTRAINED"
    elif surviving:
        diagnosis = "UNDERCONSTRAINED"
    else:
        diagnosis = "STRONG"

    return {
        "diagnosis": diagnosis,
        "mutation_score": mutation_score,
        "surviving_mutants": surviving,
        "reference_passed": reference_passed,
    }
