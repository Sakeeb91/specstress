# SpecStress evaluation scoreboard

- **Model:** `Qwen/Qwen3-30B-A3B-Instruct-2507`
- **Run time:** 39.1s
- **Total cases:** 5
- **PASS:** 2 / 5

| Case | Before | After | Score | Ref passes | Result |
| --- | --- | --- | --- | --- | --- |
| `sort` | UNDERCONSTRAINED | STRONG | 1.00 | yes | **PASS** |
| `withdraw` | UNDERCONSTRAINED | STRONG | 1.00 | yes | **PASS** |
| `sanitize` | UNDERCONSTRAINED | OVERCONSTRAINED | 1.00 | no | **FAIL** |
| `money` | UNDERCONSTRAINED | UNDERCONSTRAINED | 0.50 | yes | **FAIL** |
| `jwt` | UNDERCONSTRAINED | UNDERCONSTRAINED | 0.25 | yes | **FAIL** |
