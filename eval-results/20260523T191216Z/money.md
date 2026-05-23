# Eval artifact — `money`

- Before: **UNDERCONSTRAINED** (score 0.00)
- After:  **UNDERCONSTRAINED** (score 0.50)
- Reference passes: True
- Success (after == STRONG, score == 1.0): **False**

## Raw model output

1. The spec is missing a precise quantization invariant: it fails to enforce that the final total is the result of applying banker's rounding (ROUND_HALF_EVEN) to the exact mathematical value of `subtotal * (1 + tax_rate)`, which is critical for correctness when exact half-cents occur. This allows implementations using incorrect rounding modes (like `ROUND_HALF_DOWN`) or numerical approximations (like `float_arithmetic`) to pass. Additionally, the spec lacks an invariant that the total must depend on *all* line items, including negative ones, which allows `drops_refunds` to pass by ignoring refunds.

2. - Assert that `total` equals the result of `subtotal * (1 + tax_rate)` rounded to the nearest cent using `ROUND_HALF_EVEN` (banker's rounding), ensuring the correct rounding behavior.  
   - Assert that the total is sensitive to negative line items: if a refund (negative amount) is added to a list, the total must decrease (or stay the same), not remain unchanged.  
   - Assert that the total is *exactly* equal to `sum(line_items) * (1 + tax_rate)` when quantized to cents using `ROUND_HALF_EVEN`, without any intermediate float conversion or loss of precision.

3. ```python
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

        # Key fixes:
        # 1. Verify that total is the correct banker's rounding of the exact product.
        exact = subtotal * (Decimal("1") + rate)
        expected = exact.quantize(CENT, rounding=ROUND_HALF_EVEN)
        assert total == expected, "total must use banker's rounding (ROUND_HALF_EVEN)"

        # 2. Verify that negative items reduce the total (refunds matter).
        # Create a variant with a refund and check if total decreases.
        # Use a small refund to avoid edge case with zero total.
        refund = [item for item in items if item < 0]
        if refund:
            with_refund = sum(refund, Decimal("0"))
            total_with_refund = impl(refund, rate)
            assert total_with_refund <= Decimal("0"), "refunds must reduce total"
            # Also check that adding a refund to a positive item reduces total
            if any(item > 0 for item in items):
                positive = [item for item in items if item > 0]
                total_no_refund = impl(positive, rate)
                total_with_refund = impl(positive + refund, rate)
                assert total_with_refund <= total_no_refund, "negative items must reduce total"

        # 3. Ensure no float intermediates or approximations are used.
        # Use a known inexact decimal that fails under float arithmetic.
        # Example: 1.005 * 1.1 should be 1.1055 → 1.11 (banker's), but float drops precision.
        # We'll test a known case where float arithmetic fails.
        test_items = [Decimal("1.005")]
        test_rate = Decimal("0.1")
        exact_test = sum(test_items, Decimal("0")) * (Decimal("1") + test_rate)
        expected_test = exact_test.quantize(CENT, rounding=ROUND_HALF_EVEN)
        actual_test = impl(test_items, test_rate)
        assert actual_test == expected_test, "must not use float arithmetic"

    return test
```