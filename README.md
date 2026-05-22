# SpecStress

> Red-team your specifications before AI-written code relies on them.

AI can produce code faster than humans can review it. The bottleneck moves to the spec —
and a weak spec makes bad code look correct. SpecStress treats every candidate spec as
hostile until proven otherwise.

## What it does

SpecStress takes a problem (signature + intent), a candidate spec written as a
property-based test, and a library of adversarial implementations. It runs each
implementation against the spec under Hypothesis and produces:

- a **mutation score** — fraction of known-bad implementations the spec catches
- a **diagnosis** — `STRONG`, `UNDERCONSTRAINED`, `OVERCONSTRAINED`, or `AMBIGUOUS`
- a downloadable **Markdown report** with counterexamples

## Demo

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Three demos ship with the tool:

| Demo | Function | Why it's interesting |
| --- | --- | --- |
| `sort` | `sort(xs)` | Weak "is sorted" spec accepts `[]`, `sorted(set(xs))`, `[0]*len(xs)` |
| `withdraw` | `withdraw(balance, amount)` | Weak "balance ≥ 0" spec accepts no-op and abs-amount mutants |
| `sanitize` | `sanitize(html)` | Weak `"<script>" not in out` spec misses `<SCRIPT>`, `onclick=`, `javascript:` |

## Architecture

```
specstress/
  models.py     # SpecCase, RunResult, CaseReport
  runner.py     # execute one (spec, impl) pair under Hypothesis
  scorer.py     # mutation score + diagnosis rules
  reports.py    # render CaseReport as Markdown
  api.py        # stress_case(case, spec_name) -> CaseReport
examples/
  sort/        withdraw/        sanitize/
app.py          # Streamlit UI
tests/          # pytest suite
```

## Tests

```bash
pytest -q
```

## Roadmap

- LLM-generated spec suggestions for surviving mutants
- Z3 symbolic counterexamples for arithmetic cases
- User-defined cases (sandboxed)
- Lean / Dafny back-end for production specs

## Diagnosis reference

| Diagnosis | Meaning | Action |
| --- | --- | --- |
| `STRONG` | Reference passes; all known-bad mutants fail | Ship this spec |
| `UNDERCONSTRAINED` | At least one known-bad mutant passes | Add missing invariants |
| `OVERCONSTRAINED` | Reference fails its own spec | Loosen the spec |
| `AMBIGUOUS` | Reference fails AND a mutant passes | Spec has both pathologies — rewrite |
