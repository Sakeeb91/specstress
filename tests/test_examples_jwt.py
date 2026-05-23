from __future__ import annotations

from examples.jwt.case import CASE
from specstress.api import stress_case


def test_weak_spec_is_underconstrained_with_survivors():
    report = stress_case(CASE, "weak")
    assert report.diagnosis == "UNDERCONSTRAINED"
    assert report.reference_passed is True
    assert len(report.surviving_mutants) >= 2


def test_strong_spec_kills_all_mutants():
    report = stress_case(CASE, "strong")
    assert report.diagnosis == "STRONG", report.surviving_mutants
    assert report.mutation_score == 1.0
    assert report.reference_passed is True
