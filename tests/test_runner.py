from hypothesis import given, strategies as st

from specstress.runner import run_case


def passing_spec(impl):
    @given(st.lists(st.integers(), max_size=10))
    def test(xs):
        assert impl(xs) == sorted(xs)
    return test


def failing_spec(impl):
    @given(st.lists(st.integers(), max_size=10))
    def test(xs):
        ys = impl(xs)
        assert ys == sorted(ys)
        assert len(ys) == len(xs)  # always_empty will fail this
    return test


def correct(xs):
    return sorted(xs)


def always_empty(xs):
    return []


def test_run_case_passes_for_correct_impl():
    r = run_case("correct", correct, passing_spec)
    assert r.passed is True
    assert r.error is None


def test_run_case_fails_for_broken_impl():
    r = run_case("always_empty", always_empty, failing_spec)
    assert r.passed is False
    assert r.error is not None
    assert "AssertionError" in r.error or "Falsifying" in r.error


def test_run_case_records_impl_name():
    r = run_case("my_impl_name", correct, passing_spec)
    assert r.impl_name == "my_impl_name"
