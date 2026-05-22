from __future__ import annotations

from .models import CaseReport, SpecCase
from .runner import run_case
from .scorer import score


def stress_case(case: SpecCase, spec_name: str) -> CaseReport:
    spec_factory = case.specs[spec_name]
    results = [
        run_case(impl_name, impl, spec_factory)
        for impl_name, impl in case.mutants.items()
    ]
    s = score(results, reference_name=case.reference_impl.__name__)

    notes: list[str] = []
    if s["diagnosis"] == "UNDERCONSTRAINED":
        notes.append(
            "At least one known-bad implementation satisfied this spec. "
            "Look for missing invariants (length, multiset, immutability, "
            "boundary conditions)."
        )
    elif s["diagnosis"] == "OVERCONSTRAINED":
        notes.append(
            "The reference implementation failed its own spec. "
            "The spec demands behavior the intended implementation does not provide."
        )
    elif s["diagnosis"] == "AMBIGUOUS":
        notes.append(
            "Reference fails AND a bad mutant passes. "
            "The spec is both too strict on intended behavior and too loose on edge cases."
        )

    return CaseReport(
        case_name=case.name,
        spec_name=spec_name,
        results=results,
        mutation_score=s["mutation_score"],
        diagnosis=s["diagnosis"],
        surviving_mutants=s["surviving_mutants"],
        reference_passed=s["reference_passed"],
        notes=notes,
    )
