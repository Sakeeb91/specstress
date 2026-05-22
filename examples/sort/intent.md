# Sort

**Function:** `sort(xs: list[int]) -> list[int]`

**Intent:** Return the input list in ascending order, preserving every element. The
function must not mutate its argument.

**Why this demo:** Sorting has an obviously-strong informal definition that is easy to
under-specify formally. The weak "output is sorted" spec is accepted by `[]`, by
`sorted(set(xs))`, and by `[0] * len(xs)` — all of which are clearly wrong.
