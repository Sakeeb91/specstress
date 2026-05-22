from specstress.runner import run_case
from specstress.scorer import score
from examples.sort.case import CASE


def test_weak_spec_misses_always_empty():
    results = [
        run_case(name, impl, CASE.specs["weak"])
        for name, impl in CASE.mutants.items()
    ]
    s = score(results, reference_name="correct_sort")
    assert "always_empty" in s["surviving_mutants"]
    assert s["diagnosis"] == "UNDERCONSTRAINED"


def test_strong_spec_kills_all_mutants():
    results = [
        run_case(name, impl, CASE.specs["strong"])
        for name, impl in CASE.mutants.items()
    ]
    s = score(results, reference_name="correct_sort")
    assert s["surviving_mutants"] == []
    assert s["diagnosis"] == "STRONG"
    assert s["mutation_score"] == 1.0
