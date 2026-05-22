# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup (once)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest

# Run the Streamlit demo
streamlit run app.py

# Tests
pytest -q                                      # full suite (~21 tests)
pytest tests/test_scorer.py -v                 # one file
pytest tests/test_examples_sort.py::test_strong_spec_kills_all_mutants -v   # one test
```

There is no separate lint/build step. The package installs editable via `pip install -e .` if needed.

## Architecture

SpecStress runs a candidate specification against a panel of adversarial implementations and reports whether the spec is strong enough. The data flow is one-way and lives in five small modules:

```
SpecCase (problem definition)
   │
   ├── reference_impl        : the intended-correct function
   ├── mutants               : dict[str, Callable] of known-bad impls + reference
   ├── specs                 : dict[str, SpecFactory] — usually "weak" and "strong"
   └── input_strategy        : a Hypothesis strategy
        │
        ▼
api.stress_case(case, spec_name)
        │
        ├── for each mutant: runner.run_case(name, impl, spec_factory) → RunResult
        ├── scorer.score(results, reference_name) → diagnosis + mutation score
        └── returns CaseReport
        │
        ▼
reports.render_markdown(CaseReport)   or   app.py renders it in Streamlit
```

**Key contract — `SpecFactory`:** A spec is not a plain assertion. It is a *factory* `impl -> Callable[[], None]` whose return value is a zero-arg, Hypothesis-decorated test function. `runner.run_case` invokes the factory, then calls the test, captures any exception, and returns a `RunResult`. This indirection is what lets one spec be reused across many implementations.

**Diagnosis rules (in `scorer.score`):**

| Reference impl | Any known-bad mutant passed? | Diagnosis |
| --- | --- | --- |
| passes | no | `STRONG` |
| passes | yes | `UNDERCONSTRAINED` |
| fails | no | `OVERCONSTRAINED` |
| fails | yes | `AMBIGUOUS` |

The "reference name" is `case.reference_impl.__name__`, so the reference must also appear in `case.mutants` under that exact key (it is — by convention the first entry).

## Adding a new demo

1. `examples/<name>/case.py` defines: implementations (one reference + several adversarial mutants), an `input_strategy`, a `weak_spec` and `strong_spec` factory, and a module-level `CASE = SpecCase(...)`.
2. `examples/<name>/__init__.py` re-exports `CASE`.
3. Register in `examples/__init__.py`'s `REGISTRY` dict.
4. Add a `tests/test_examples_<name>.py` with at least:
   - weak spec produces `UNDERCONSTRAINED` and at least one surviving mutant
   - strong spec produces `STRONG` with mutation score 1.0

The Streamlit app picks up new cases automatically via `REGISTRY`.

Hypothesis specs should use `@settings(deadline=None)` to avoid flaky CI timeouts on slow mutants, and bounded strategies (`max_size`, `min_value`/`max_value`) to keep runs snappy.

## Repository conventions

- TDD: every feature lands as `test → red → impl → green → commit`. The plan at `docs/plans/2026-05-22-specstress-mvp.md` is the authoritative spec for the MVP and shows the expected commit cadence.
- No comments or docstrings unless they explain non-obvious *why*.
- Conventional-commit prefixes (`feat:`, `fix:`, `docs:`, `chore:`, scoped e.g. `feat(scorer):`).
- The `examples/` package is installed as a top-level package (see `pyproject.toml`'s `packages.find`); be aware this collides with any other top-level `examples` in the same env. The app is intended to run from the repo root.
