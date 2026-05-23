# Eval artifact — `withdraw`

- Before: **UNDERCONSTRAINED** (score 0.25)
- After:  **STRONG** (score 1.00)
- Reference passes: True
- Success (after == STRONG, score == 1.0): **True**

## Raw model output

1. The current spec is underconstrained because it only checks that the balance does not go negative, but fails to enforce two critical invariants: (1) a withdrawal must only succeed when the amount is strictly positive, and (2) the balance must only decrease if the withdrawal succeeds. This allows implementations like `clamped`, `noop`, and `allows_zero` to pass by relaxing the success conditions or ignoring the amount.

2. - Add an assertion that `ok` is `False` when `amount <= 0`, ensuring that non-positive amounts cannot result in a successful withdrawal.  
   - Add an assertion that `new_balance == balance` when `ok` is `False`, ensuring that the balance is unchanged if the withdrawal fails.  
   - Add an assertion that `new_balance < balance` when `ok` is `True`, ensuring that a successful withdrawal actually reduces the balance.

3. ```python
def weak_spec(impl):
    @settings(max_examples=100, deadline=None)
    @given(_strategy)
    def test(args):
        balance, amount = args
        ok, new_balance = impl(balance, amount)
        assert new_balance >= 0, "balance must not go negative"
        assert ok == (amount > 0 and amount <= balance), "success must match positive and sufficient amount"
        assert new_balance == balance if not ok else new_balance < balance, "balance must only change on success"
    return test
```