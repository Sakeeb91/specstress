from hypothesis import strategies as st

from specstress.models import SpecCase, RunResult, CaseReport


def _impl(xs):
    return sorted(xs)


def _spec(impl):
    def test():
        assert impl([3, 1, 2]) == [1, 2, 3]
    return test


def test_speccase_fields_are_populated():
    case = SpecCase(
        name="sort",
        intent="Return sorted list.",
        input_strategy=st.lists(st.integers()),
        reference_impl=_impl,
        specs={"weak": _spec},
        mutants={"correct_sort": _impl},
    )
    assert case.name == "sort"
    assert "weak" in case.specs
    assert "correct_sort" in case.mutants
    assert case.reference_impl is _impl


def test_runresult_roundtrip():
    r = RunResult(impl_name="foo", passed=True, error=None, counterexample=None)
    assert r.impl_name == "foo"
    assert r.passed is True


def test_casereport_holds_results():
    r = RunResult(impl_name="foo", passed=True, error=None, counterexample=None)
    report = CaseReport(
        case_name="sort",
        spec_name="weak",
        results=[r],
        mutation_score=1.0,
        diagnosis="STRONG",
        surviving_mutants=[],
        reference_passed=True,
    )
    assert report.mutation_score == 1.0
    assert report.diagnosis == "STRONG"
