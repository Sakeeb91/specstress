# SpecStress Report

**Case:** `sort`  
**Spec:** `weak`  
**Diagnosis:** **UNDERCONSTRAINED**  
**Mutation score:** 0%  
**Reference passed:** True

## Per-implementation results

| Implementation | Passed | Counterexample |
| --- | --- | --- |
| `correct_sort` | ✅ | — |
| `always_empty` | ✅ | — |
| `unique_sorted` | ✅ | — |
| `constant_zeroes` | ✅ | — |
| `drops_last` | ✅ | — |
| `mutates_input` | ✅ | — |

## Surviving bad implementations

- `always_empty`
- `unique_sorted`
- `constant_zeroes`
- `drops_last`
- `mutates_input`

## Notes

- At least one known-bad implementation satisfied this spec. Look for missing invariants (length, multiset, immutability, boundary conditions).
