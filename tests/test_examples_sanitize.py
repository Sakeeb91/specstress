from specstress.runner import run_case
from specstress.scorer import score
from examples.sanitize.case import CASE


def test_weak_spec_is_underconstrained():
    results = [
        run_case(name, impl, CASE.specs["weak"])
        for name, impl in CASE.mutants.items()
    ]
    s = score(results, reference_name="correct_sanitize")
    assert s["diagnosis"] == "UNDERCONSTRAINED"
    assert len(s["surviving_mutants"]) >= 1
