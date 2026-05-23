# Eval artifact — `sort`

- Before: **UNDERCONSTRAINED** (score 0.00)
- After:  **STRONG** (score 1.00)
- Reference passes: True
- Success (after == STRONG, score == 1.0): **True**

## Raw model output

1. The spec is missing invariants that ensure the output list has the same length as the input, contains exactly the same elements (with multiplicity), and does not modify the input list. Specifically, it fails to enforce that the output is a permutation of the input, which allows implementations to drop elements, introduce duplicates, or mutate the input without detection.

2. - Assert that the length of the output list equals the length of the input list, ensuring no elements are dropped or added.  
   - Assert that the multiset (i.e., sorted frequency count) of the output matches that of the input, ensuring no element is lost or duplicated.  
   - Assert that the input list is not modified in place, ensuring the implementation does not mutate the original input.

3. ```python
def weak_spec(impl):
    @settings(max_examples=50, deadline=None)
    @given(_strategy)
    def test(xs):
        xs_copy = list(xs)  # preserve original input
        ys = impl(xs_copy)
        assert len(ys) == len(xs)
        assert sorted(ys) == sorted(xs)
        assert xs_copy == xs  # input unchanged
    return test
```