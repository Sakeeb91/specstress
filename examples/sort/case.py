from __future__ import annotations

from collections import Counter

from hypothesis import given, settings, strategies as st

from specstress.models import SpecCase


# --- Implementations -----------------------------------------------------

def correct_sort(xs):
    return sorted(xs)


def always_empty(xs):
    return []


def unique_sorted(xs):
    return sorted(set(xs))


def constant_zeroes(xs):
    return [0 for _ in xs]


def drops_last(xs):
    return sorted(xs)[:-1] if xs else []


def mutates_input(xs):
    xs.sort()
    return xs


# --- Specs ---------------------------------------------------------------

_strategy = st.lists(st.integers(min_value=-100, max_value=100), max_size=20)


def weak_spec(impl):
    @settings(max_examples=50, deadline=None)
    @given(_strategy)
    def test(xs):
        ys = impl(list(xs))  # defensive copy so impls don't leak
        assert ys == sorted(ys)
    return test


def strong_spec(impl):
    @settings(max_examples=50, deadline=None)
    @given(_strategy)
    def test(xs):
        original = list(xs)
        ys = impl(list(xs))
        assert ys == sorted(ys), "output not sorted"
        assert Counter(ys) == Counter(original), "elements not preserved"
        assert len(ys) == len(original), "length not preserved"
    return test


# --- Case ----------------------------------------------------------------

CASE = SpecCase(
    name="sort",
    intent="Return sorted list preserving every input element.",
    input_strategy=_strategy,
    reference_impl=correct_sort,
    specs={"weak": weak_spec, "strong": strong_spec},
    mutants={
        "correct_sort": correct_sort,
        "always_empty": always_empty,
        "unique_sorted": unique_sorted,
        "constant_zeroes": constant_zeroes,
        "drops_last": drops_last,
        "mutates_input": mutates_input,
    },
)
