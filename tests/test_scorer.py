from specstress.models import RunResult
from specstress.scorer import score


def _ok(name):
    return RunResult(impl_name=name, passed=True, error=None, counterexample=None)


def _fail(name):
    return RunResult(impl_name=name, passed=False, error="x", counterexample=None)


def test_strong_when_ref_passes_and_all_mutants_fail():
    results = [_ok("correct_sort"), _fail("always_empty"), _fail("unique_sorted")]
    r = score(results, reference_name="correct_sort")
    assert r["diagnosis"] == "STRONG"
    assert r["mutation_score"] == 1.0
    assert r["surviving_mutants"] == []
    assert r["reference_passed"] is True


def test_underconstrained_when_bad_mutant_passes():
    results = [_ok("correct_sort"), _ok("always_empty"), _fail("unique_sorted")]
    r = score(results, reference_name="correct_sort")
    assert r["diagnosis"] == "UNDERCONSTRAINED"
    assert r["mutation_score"] == 0.5
    assert r["surviving_mutants"] == ["always_empty"]


def test_overconstrained_when_reference_fails_and_all_mutants_fail():
    results = [_fail("correct_sort"), _fail("always_empty")]
    r = score(results, reference_name="correct_sort")
    assert r["diagnosis"] == "OVERCONSTRAINED"
    assert r["reference_passed"] is False


def test_ambiguous_when_reference_fails_and_a_mutant_passes():
    results = [_fail("correct_sort"), _ok("always_empty")]
    r = score(results, reference_name="correct_sort")
    assert r["diagnosis"] == "AMBIGUOUS"


def test_no_mutants_means_zero_score():
    results = [_ok("correct_sort")]
    r = score(results, reference_name="correct_sort")
    assert r["mutation_score"] == 0.0
