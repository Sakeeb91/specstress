# Eval artifact — `sort`

- Before: **UNDERCONSTRAINED** (score 0.00)
- After:  **UNDERCONSTRAINED** (score 0.80)
- Reference passes: True
- Success (after == STRONG, score == 1.0): **False**

## Raw model output

1. The current spec is missing two critical invariants: **element preservation** (the output must contain exactly the same elements as the input, with the same multiplicities) and **input immutability** (the input list must not be modified in-place). The spec only checks that the output is sorted, which is insufficient to distinguish correct behavior from counterexamples like `always_empty`, `unique_sorted`, `constant_zeroes`, `drops_last`, and `mutates_input`.

2. - Assert that the length of the output list equals the length of the input list, ensuring no elements are lost or added.  
   - Assert that the multiset (sorted frequency counts) of the output matches that of the input, preventing loss of duplicates (e.g., `unique_sorted` fails this).  
   - Assert that the input list is unchanged after the call, preventing in-place mutation (e.g., `mutates_input` fails this).  

3. 
```python
def weak_spec(impl):
    @settings(max_examples=50, deadline=None)
    @given(_strategy)
    def test(xs):
        xs_copy = list(xs)  # preserve original input
        ys = impl(list(xs))  # defensive copy so impls don't leak
        assert len(ys) == len(xs)  # elements preserved in count
        assert sorted(ys) == ys  # output is sorted
        assert sorted(ys) == sorted(xs)  # same elements with same multiplicities
        assert xs == xs_copy  # input not mutated
    return test
```