# Eval artifact — `withdraw`

- Before: **UNDERCONSTRAINED** (score 0.25)
- After:  **STRONG** (score 1.00)
- Reference passes: True
- Success (after == STRONG, score == 1.0): **True**

## Raw model output

1. The current spec is missing the invariant that a withdrawal must only succeed (return `True`) when the amount is strictly positive and sufficient to deduct from the balance. The spec currently only enforces non-negativity of the balance after withdrawal, which allows implementations to pass even when they incorrectly accept zero or negative amounts, or silently ignore withdrawals entirely.

2. - Add an assertion that the operation returns `False` when `amount <= 0`, ensuring that zero or negative withdrawals are rejected.  
   - Add an assertion that the operation returns `False` when `amount > balance`, ensuring overdrafts are not permitted.  
   - Add an assertion that the balance only decreases when the operation returns `True`, ensuring that the withdrawal actually affects the account state.

```python
def weak_spec(impl):
    @settings(max_examples=100, deadline=None)
    @given(_strategy)
    def test(args):
        balance, amount = args
        ok, new_balance = impl(balance, amount)
        assert new_balance >= 0, "balance must not go negative"
        assert ok == (amount > 0 and amount <= balance), "success must match valid withdrawal conditions"
        assert not ok or new_balance == balance - amount, "balance must decrease by amount on success"
    return test
```