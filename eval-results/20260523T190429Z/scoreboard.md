# SpecStress evaluation scoreboard

- **Model:** `Qwen/Qwen3-30B-A3B-Instruct-2507`
- **Run time:** 19.5s
- **Total cases:** 3
- **PASS:** 1 / 3

| Case | Before | After | Score | Ref passes | Result |
| --- | --- | --- | --- | --- | --- |
| `sort` | UNDERCONSTRAINED | UNDERCONSTRAINED | 0.80 | yes | **FAIL** |
| `withdraw` | UNDERCONSTRAINED | STRONG | 1.00 | yes | **PASS** |
| `sanitize` | UNDERCONSTRAINED | OVERCONSTRAINED | 1.00 | no | **FAIL** |
