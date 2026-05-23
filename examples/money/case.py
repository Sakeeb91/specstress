from __future__ import annotations

from decimal import Decimal, ROUND_HALF_DOWN, ROUND_HALF_EVEN

from hypothesis import example, given, settings, strategies as st

from specstress.models import SpecCase


CENT = Decimal("0.01")


# --- Implementations -----------------------------------------------------

def correct_total(line_items, tax_rate):
    """Sum line items (refunds allowed via negative amounts), apply tax,
    quantize to cents using banker's rounding."""
    subtotal = sum(line_items, Decimal("0"))
    total = subtotal * (Decimal("1") + tax_rate)
    return total.quantize(CENT, rounding=ROUND_HALF_EVEN)


def float_arithmetic(line_items, tax_rate):
    """Mistakenly drops to float, loses pennies."""
    subtotal = float(sum(line_items, Decimal("0")))
    total = subtotal * (1.0 + float(tax_rate))
    return Decimal(repr(round(total, 2))).quantize(CENT, rounding=ROUND_HALF_EVEN)


def double_tax(line_items, tax_rate):
    """Off-by-one: applies the tax twice."""
    subtotal = sum(line_items, Decimal("0"))
    once = subtotal * (Decimal("1") + tax_rate)
    twice = once * (Decimal("1") + tax_rate)
    return twice.quantize(CENT, rounding=ROUND_HALF_EVEN)


def half_down_rounding(line_items, tax_rate):
    """Looks identical at a glance but uses ROUND_HALF_DOWN — drops a cent
    on exact halves where banker's rounding would round to even."""
    subtotal = sum(line_items, Decimal("0"))
    total = subtotal * (Decimal("1") + tax_rate)
    return total.quantize(CENT, rounding=ROUND_HALF_DOWN)


def drops_refunds(line_items, tax_rate):
    """Silently ignores negative line items (refunds)."""
    positive = [x for x in line_items if x > 0]
    subtotal = sum(positive, Decimal("0"))
    total = subtotal * (Decimal("1") + tax_rate)
    return total.quantize(CENT, rounding=ROUND_HALF_EVEN)


# --- Specs ---------------------------------------------------------------

_strategy = st.tuples(
    st.lists(
        st.decimals(
            min_value=Decimal("-50.00"),
            max_value=Decimal("500.00"),
            allow_nan=False,
            allow_infinity=False,
            places=2,
        ),
        min_size=1,
        max_size=5,
    ),
    st.decimals(
        min_value=Decimal("0.0000"),
        max_value=Decimal("0.3000"),
        allow_nan=False,
        allow_infinity=False,
        places=4,
    ),
)


def weak_spec(impl):
    """The kind of spec a junior dev writes: 'tax was applied if any'."""

    @settings(max_examples=100, deadline=None)
    @given(_strategy)
    def test(args):
        items, rate = args
        total = impl(items, rate)
        subtotal = sum(items, Decimal("0"))
        # Weak: "if rate > 0 and we have positive subtotal, total should be >= subtotal"
        if rate > 0 and subtotal > 0:
            assert total >= subtotal, "tax does not appear to have been applied"
        assert isinstance(total, Decimal), "total must be a Decimal"

    return test


_HALF_EDGE_EXAMPLES = [
    ([Decimal("0.30")], Decimal("0.0250")),
    ([Decimal("0.10"), Decimal("0.20")], Decimal("0.0250")),
    ([Decimal("1.00"), Decimal("-0.10")], Decimal("0.0500")),
    ([Decimal("9.99")], Decimal("0.1000")),
]


def strong_spec(impl):
    """Cent-exact spec: total == subtotal * (1 + rate) rounded half-even."""

    @settings(max_examples=500, deadline=None)
    @example(args=(_HALF_EDGE_EXAMPLES[0]))
    @example(args=(_HALF_EDGE_EXAMPLES[1]))
    @example(args=(_HALF_EDGE_EXAMPLES[2]))
    @example(args=(_HALF_EDGE_EXAMPLES[3]))
    @given(_strategy)
    def test(args):
        items, rate = args
        total = impl(items, rate)
        subtotal = sum(items, Decimal("0"))
        expected = (subtotal * (Decimal("1") + rate)).quantize(
            CENT, rounding=ROUND_HALF_EVEN
        )
        assert isinstance(total, Decimal), "total must be Decimal"
        assert total == expected, f"total {total} != expected {expected}"
        if rate == 0:
            assert total == subtotal.quantize(CENT, rounding=ROUND_HALF_EVEN)

    return test


# --- Case ----------------------------------------------------------------

CASE = SpecCase(
    name="money",
    intent=(
        "Compute order total = sum(line_items) * (1 + tax_rate), quantized to "
        "cents using banker's rounding. Negative line items represent refunds "
        "and must be honored."
    ),
    input_strategy=_strategy,
    reference_impl=correct_total,
    specs={"weak": weak_spec, "strong": strong_spec},
    mutants={
        "correct_total": correct_total,
        "float_arithmetic": float_arithmetic,
        "double_tax": double_tax,
        "half_down_rounding": half_down_rounding,
        "drops_refunds": drops_refunds,
    },
)
