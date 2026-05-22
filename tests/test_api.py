from specstress.api import stress_case
from examples.sort.case import CASE as SORT_CASE


def test_stress_case_returns_underconstrained_for_weak_sort():
    report = stress_case(SORT_CASE, "weak")
    assert report.case_name == "sort"
    assert report.spec_name == "weak"
    assert report.diagnosis == "UNDERCONSTRAINED"
    assert report.mutation_score < 1.0


def test_stress_case_returns_strong_for_strong_sort():
    report = stress_case(SORT_CASE, "strong")
    assert report.diagnosis == "STRONG"
    assert report.mutation_score == 1.0
