from __future__ import annotations

from hypothesis import given, settings, strategies as st

from specstress.models import SpecCase


# --- Implementations -----------------------------------------------------

def correct_withdraw(balance, amount):
    if amount > 0 and amount <= balance:
        return True, balance - amount
    return False, balance


def abs_amount(balance, amount):
    # Accepts negative withdrawals by silently flipping the sign.
    return True, balance - abs(amount)


def clamped(balance, amount):
    # Caps the balance at zero instead of rejecting overdrafts.
    return True, max(0, balance - amount)


def noop(balance, amount):
    # Pretends every withdrawal succeeded without moving money.
    return True, balance


def allows_zero(balance, amount):
    # Treats amount==0 as a success.
    if amount >= 0 and amount <= balance:
        return True, balance - amount
    return False, balance


# --- Specs ---------------------------------------------------------------

_strategy = st.tuples(
    st.integers(min_value=0, max_value=10_000),       # balance
    st.integers(min_value=-1_000, max_value=10_000),  # amount
)


def weak_spec(impl):
    @settings(max_examples=100, deadline=None)
    @given(_strategy)
    def test(args):
        balance, amount = args
        ok, new_balance = impl(balance, amount)
        assert new_balance >= 0, "balance must not go negative"
    return test


def strong_spec(impl):
    @settings(max_examples=200, deadline=None)
    @given(_strategy)
    def test(args):
        balance, amount = args
        ok, new_balance = impl(balance, amount)

        should_succeed = amount > 0 and amount <= balance

        assert ok == should_succeed, f"success={ok!r} but should={should_succeed!r}"
        if should_succeed:
            assert new_balance == balance - amount, "balance must decrease by amount"
        else:
            assert new_balance == balance, "balance must not change on failure"
    return test


# --- Case ----------------------------------------------------------------

CASE = SpecCase(
    name="withdraw",
    intent="Decrement balance by amount iff amount is positive and balance suffices.",
    input_strategy=_strategy,
    reference_impl=correct_withdraw,
    specs={"weak": weak_spec, "strong": strong_spec},
    mutants={
        "correct_withdraw": correct_withdraw,
        "abs_amount": abs_amount,
        "clamped": clamped,
        "noop": noop,
        "allows_zero": allows_zero,
    },
)
