# SpecStress MVP Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a hackathon-ready specification-validation tool that stress-tests candidate specs against adversarial implementations using property-based testing, scores spec strength via mutation kill rate, and renders results in a Streamlit dashboard.

**Architecture:** Pure-Python library + Streamlit UI. A `SpecCase` dataclass bundles a problem's intent, Hypothesis input strategy, reference implementation, candidate specs, and adversarial mutants. A `runner` executes each (spec, impl) pair under Hypothesis, a `scorer` computes mutation kill rate and produces a diagnosis (UNDERCONSTRAINED / OVERCONSTRAINED / AMBIGUOUS / STRONG), a `reports` module emits Markdown, and `app.py` wires everything together. Three demos ship out of the box: `sort`, `withdraw`, `sanitize`.

**Tech Stack:** Python 3.11+, Hypothesis (property-based testing), Streamlit (UI), pytest (own test suite), Markdown (reports). Optional later: Z3, LLM helpers.

---

## Chunk 1: Repo Skeleton & Core Data Model

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `README.md`
- Create: `specstress/__init__.py`
- Create: `tests/__init__.py`
- Create: `examples/__init__.py`

- [ ] **Step 1: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.hypothesis/
.DS_Store
*.egg-info/
dist/
build/
reports/*.md
!reports/sample_report.md
.streamlit/secrets.toml
```

- [ ] **Step 2: Write `requirements.txt`**

```
streamlit>=1.32
hypothesis>=6.100
pytest>=8.0
```

- [ ] **Step 3: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "specstress"
version = "0.1.0"
description = "Red-team your specs before AI code uses them"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "streamlit>=1.32",
  "hypothesis>=6.100",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.setuptools.packages.find]
include = ["specstress*", "examples*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 4: Write initial `README.md`**

```markdown
# SpecStress

Red-team your specifications before AI-written code relies on them.

SpecStress runs candidate specs against adversarial implementations using property-based
testing. If known-bad implementations survive, your spec is underconstrained. If known-good
implementations fail, your spec is overconstrained. SpecStress reports a mutation kill
rate and a diagnosis you can act on.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

See `examples/` for the three built-in demos: `sort`, `withdraw`, `sanitize`.
```

- [ ] **Step 5: Create empty package files**

```bash
touch specstress/__init__.py tests/__init__.py examples/__init__.py
```

- [ ] **Step 6: Commit scaffolding**

```bash
git add .gitignore requirements.txt pyproject.toml README.md specstress/__init__.py tests/__init__.py examples/__init__.py
git commit -m "chore: scaffold specstress package"
```

---

### Task 2: Core data model

**Files:**
- Create: `specstress/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

`tests/test_models.py`:

```python
from hypothesis import strategies as st

from specstress.models import SpecCase, RunResult, CaseReport


def _impl(xs):
    return sorted(xs)


def _spec(impl):
    def test():
        assert impl([3, 1, 2]) == [1, 2, 3]
    return test


def test_speccase_fields_are_populated():
    case = SpecCase(
        name="sort",
        intent="Return sorted list.",
        input_strategy=st.lists(st.integers()),
        reference_impl=_impl,
        specs={"weak": _spec},
        mutants={"correct_sort": _impl},
    )
    assert case.name == "sort"
    assert "weak" in case.specs
    assert "correct_sort" in case.mutants
    assert case.reference_impl is _impl


def test_runresult_roundtrip():
    r = RunResult(impl_name="foo", passed=True, error=None, counterexample=None)
    assert r.impl_name == "foo"
    assert r.passed is True


def test_casereport_holds_results():
    r = RunResult(impl_name="foo", passed=True, error=None, counterexample=None)
    report = CaseReport(
        case_name="sort",
        spec_name="weak",
        results=[r],
        mutation_score=1.0,
        diagnosis="STRONG",
        surviving_mutants=[],
        reference_passed=True,
    )
    assert report.mutation_score == 1.0
    assert report.diagnosis == "STRONG"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: ImportError — `specstress.models` does not exist.

- [ ] **Step 3: Implement `specstress/models.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


SpecFactory = Callable[[Callable[..., Any]], Callable[[], None]]


@dataclass
class SpecCase:
    """A problem definition: intent + strategy + specs + mutants."""

    name: str
    intent: str
    input_strategy: Any  # Hypothesis strategy
    reference_impl: Callable[..., Any]
    specs: dict[str, SpecFactory]
    mutants: dict[str, Callable[..., Any]]


@dataclass
class RunResult:
    """Outcome of running one spec against one implementation."""

    impl_name: str
    passed: bool
    error: str | None
    counterexample: str | None


@dataclass
class CaseReport:
    """Aggregated results for one (case, spec) pairing."""

    case_name: str
    spec_name: str
    results: list[RunResult]
    mutation_score: float
    diagnosis: str
    surviving_mutants: list[str]
    reference_passed: bool
    notes: list[str] = field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add specstress/models.py tests/test_models.py
git commit -m "feat(models): add SpecCase, RunResult, CaseReport dataclasses"
```

---

## Chunk 2: Runner & Scorer

### Task 3: Spec runner

**Files:**
- Create: `specstress/runner.py`
- Test: `tests/test_runner.py`

The runner takes a spec factory (function that wraps an implementation in a Hypothesis-decorated test) and an implementation. It executes the test and returns a `RunResult`. Hypothesis raises `AssertionError` (or any exception) with a `Falsifying example:` block when it finds a counterexample — we capture the full message so the UI can render it.

- [ ] **Step 1: Write failing tests**

`tests/test_runner.py`:

```python
from hypothesis import given, strategies as st

from specstress.runner import run_case


def passing_spec(impl):
    @given(st.lists(st.integers(), max_size=10))
    def test(xs):
        assert impl(xs) == sorted(xs)
    return test


def failing_spec(impl):
    @given(st.lists(st.integers(), max_size=10))
    def test(xs):
        ys = impl(xs)
        assert ys == sorted(ys)
        assert len(ys) == len(xs)  # always_empty will fail this
    return test


def correct(xs):
    return sorted(xs)


def always_empty(xs):
    return []


def test_run_case_passes_for_correct_impl():
    r = run_case("correct", correct, passing_spec)
    assert r.passed is True
    assert r.error is None


def test_run_case_fails_for_broken_impl():
    r = run_case("always_empty", always_empty, failing_spec)
    assert r.passed is False
    assert r.error is not None
    assert "AssertionError" in r.error or "Falsifying" in r.error


def test_run_case_records_impl_name():
    r = run_case("my_impl_name", correct, passing_spec)
    assert r.impl_name == "my_impl_name"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_runner.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `specstress/runner.py`**

```python
from __future__ import annotations

import io
import traceback
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Callable

from .models import RunResult


def run_case(
    impl_name: str,
    impl: Callable[..., Any],
    spec_factory: Callable[[Callable[..., Any]], Callable[[], None]],
) -> RunResult:
    """Run a spec against an implementation. Returns a RunResult.

    spec_factory(impl) must return a zero-arg callable (typically a Hypothesis
    @given-wrapped test). Any uncaught exception is captured as a failure.
    """
    try:
        test_fn = spec_factory(impl)
    except Exception as e:
        return RunResult(
            impl_name=impl_name,
            passed=False,
            error=f"spec_factory raised: {e!r}",
            counterexample=None,
        )

    stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            test_fn()
    except Exception:
        tb = traceback.format_exc()
        counterexample = _extract_counterexample(tb, stderr_buf.getvalue())
        return RunResult(
            impl_name=impl_name,
            passed=False,
            error=tb.strip(),
            counterexample=counterexample,
        )

    return RunResult(impl_name=impl_name, passed=True, error=None, counterexample=None)


def _extract_counterexample(traceback_text: str, stderr_text: str) -> str | None:
    """Pull a Hypothesis 'Falsifying example' line out of the captured output."""
    for blob in (traceback_text, stderr_text):
        for line in blob.splitlines():
            if "Falsifying example" in line:
                return line.strip()
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_runner.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add specstress/runner.py tests/test_runner.py
git commit -m "feat(runner): execute spec factories and capture counterexamples"
```

---

### Task 4: Scorer & diagnosis

**Files:**
- Create: `specstress/scorer.py`
- Test: `tests/test_scorer.py`

Diagnosis rules:
- `STRONG`: reference passes AND all known-bad mutants fail.
- `UNDERCONSTRAINED`: at least one known-bad mutant passes the spec.
- `OVERCONSTRAINED`: reference implementation fails its own spec.
- `AMBIGUOUS`: reference fails AND at least one bad mutant passes (both pathologies at once).

A mutant is "known-bad" if its name is not the reference name. The reference impl is passed in by name so we know which result to interpret as ground truth.

- [ ] **Step 1: Write failing tests**

`tests/test_scorer.py`:

```python
from specstress.models import RunResult
from specstress.scorer import score


def _ok(name):
    return RunResult(impl_name=name, passed=True, error=None, counterexample=None)


def _fail(name):
    return RunResult(impl_name=name, passed=False, error="x", counterexample=None)


def test_strong_when_ref_passes_and_all_mutants_fail():
    results = [_ok("correct_sort"), _fail("always_empty"), _fail("unique_sorted")]
    r = score(results, reference_name="correct_sort")
    assert r["diagnosis"] == "STRONG"
    assert r["mutation_score"] == 1.0
    assert r["surviving_mutants"] == []
    assert r["reference_passed"] is True


def test_underconstrained_when_bad_mutant_passes():
    results = [_ok("correct_sort"), _ok("always_empty"), _fail("unique_sorted")]
    r = score(results, reference_name="correct_sort")
    assert r["diagnosis"] == "UNDERCONSTRAINED"
    assert r["mutation_score"] == 0.5
    assert r["surviving_mutants"] == ["always_empty"]


def test_overconstrained_when_reference_fails_and_all_mutants_fail():
    results = [_fail("correct_sort"), _fail("always_empty")]
    r = score(results, reference_name="correct_sort")
    assert r["diagnosis"] == "OVERCONSTRAINED"
    assert r["reference_passed"] is False


def test_ambiguous_when_reference_fails_and_a_mutant_passes():
    results = [_fail("correct_sort"), _ok("always_empty")]
    r = score(results, reference_name="correct_sort")
    assert r["diagnosis"] == "AMBIGUOUS"


def test_no_mutants_means_zero_score():
    results = [_ok("correct_sort")]
    r = score(results, reference_name="correct_sort")
    assert r["mutation_score"] == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scorer.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `specstress/scorer.py`**

```python
from __future__ import annotations

from typing import Any

from .models import RunResult


def score(results: list[RunResult], reference_name: str) -> dict[str, Any]:
    """Compute mutation score and diagnosis from a list of RunResults."""
    by_name = {r.impl_name: r for r in results}
    ref = by_name.get(reference_name)
    reference_passed = bool(ref and ref.passed)

    mutants = [r for r in results if r.impl_name != reference_name]
    total = len(mutants)
    surviving = [r.impl_name for r in mutants if r.passed]
    killed = total - len(surviving)
    mutation_score = (killed / total) if total else 0.0

    if not reference_passed and surviving:
        diagnosis = "AMBIGUOUS"
    elif not reference_passed:
        diagnosis = "OVERCONSTRAINED"
    elif surviving:
        diagnosis = "UNDERCONSTRAINED"
    else:
        diagnosis = "STRONG"

    return {
        "diagnosis": diagnosis,
        "mutation_score": mutation_score,
        "surviving_mutants": surviving,
        "reference_passed": reference_passed,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scorer.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add specstress/scorer.py tests/test_scorer.py
git commit -m "feat(scorer): compute mutation score and four-way diagnosis"
```

---

## Chunk 3: Demo Examples

### Task 5: Sort demo

**Files:**
- Create: `examples/sort/__init__.py`
- Create: `examples/sort/intent.md`
- Create: `examples/sort/case.py`
- Test: `tests/test_examples_sort.py`

- [ ] **Step 1: Write `examples/sort/intent.md`**

```markdown
# Sort

**Function:** `sort(xs: list[int]) -> list[int]`

**Intent:** Return the input list in ascending order, preserving every element. The
function must not mutate its argument.

**Why this demo:** Sorting has an obviously-strong informal definition that is easy to
under-specify formally. The weak "output is sorted" spec is accepted by `[]`, by
`sorted(set(xs))`, and by `[0] * len(xs)` — all of which are clearly wrong.
```

- [ ] **Step 2: Write the failing test**

`tests/test_examples_sort.py`:

```python
from specstress.runner import run_case
from specstress.scorer import score
from examples.sort.case import CASE


def test_weak_spec_misses_always_empty():
    results = [
        run_case(name, impl, CASE.specs["weak"])
        for name, impl in CASE.mutants.items()
    ]
    s = score(results, reference_name="correct_sort")
    assert "always_empty" in s["surviving_mutants"]
    assert s["diagnosis"] == "UNDERCONSTRAINED"


def test_strong_spec_kills_all_mutants():
    results = [
        run_case(name, impl, CASE.specs["strong"])
        for name, impl in CASE.mutants.items()
    ]
    s = score(results, reference_name="correct_sort")
    assert s["surviving_mutants"] == []
    assert s["diagnosis"] == "STRONG"
    assert s["mutation_score"] == 1.0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_examples_sort.py -v`
Expected: ImportError — `examples.sort.case` not yet defined.

- [ ] **Step 4: Implement `examples/sort/case.py`**

```python
from __future__ import annotations

from collections import Counter

from hypothesis import given, settings, strategies as st

from specstress.models import SpecCase


# --- Implementations -----------------------------------------------------

def correct_sort(xs):
    return sorted(xs)


def always_empty(xs):
    return []


def unique_sorted(xs):
    return sorted(set(xs))


def constant_zeroes(xs):
    return [0 for _ in xs]


def drops_last(xs):
    return sorted(xs)[:-1] if xs else []


def mutates_input(xs):
    xs.sort()
    return xs


# --- Specs ---------------------------------------------------------------

_strategy = st.lists(st.integers(min_value=-100, max_value=100), max_size=20)


def weak_spec(impl):
    @settings(max_examples=50, deadline=None)
    @given(_strategy)
    def test(xs):
        ys = impl(list(xs))  # defensive copy so impls don't leak
        assert ys == sorted(ys)
    return test


def strong_spec(impl):
    @settings(max_examples=50, deadline=None)
    @given(_strategy)
    def test(xs):
        original = list(xs)
        ys = impl(list(xs))
        assert ys == sorted(ys), "output not sorted"
        assert Counter(ys) == Counter(original), "elements not preserved"
        assert len(ys) == len(original), "length not preserved"
    return test


# --- Case ----------------------------------------------------------------

CASE = SpecCase(
    name="sort",
    intent="Return sorted list preserving every input element.",
    input_strategy=_strategy,
    reference_impl=correct_sort,
    specs={"weak": weak_spec, "strong": strong_spec},
    mutants={
        "correct_sort": correct_sort,
        "always_empty": always_empty,
        "unique_sorted": unique_sorted,
        "constant_zeroes": constant_zeroes,
        "drops_last": drops_last,
        "mutates_input": mutates_input,
    },
)
```

- [ ] **Step 5: Add `examples/sort/__init__.py`**

```python
from .case import CASE  # noqa: F401
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_examples_sort.py -v`
Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add examples/sort/ tests/test_examples_sort.py
git commit -m "feat(examples): add sort demo with weak/strong specs and 6 mutants"
```

---

### Task 6: Withdraw demo

**Files:**
- Create: `examples/withdraw/__init__.py`
- Create: `examples/withdraw/intent.md`
- Create: `examples/withdraw/case.py`
- Test: `tests/test_examples_withdraw.py`

The withdraw function returns `(success: bool, new_balance: int)`. A withdrawal succeeds iff `amount > 0` and `amount <= balance`; on success the balance decreases by exactly `amount`, on failure it is unchanged.

- [ ] **Step 1: Write `examples/withdraw/intent.md`**

```markdown
# Withdraw

**Function:** `withdraw(balance: int, amount: int) -> tuple[bool, int]`

**Intent:** Returns `(success, new_balance)`. The withdrawal succeeds if and only if
`amount > 0` and `amount <= balance`. On success, the returned balance equals
`balance - amount`. On failure, the returned balance equals `balance` unchanged.

**Why this demo:** Financial correctness is a classic place where weak specs (`new_balance
>= 0`) admit dangerous implementations such as silently capping negative withdrawals or
ignoring the amount entirely.
```

- [ ] **Step 2: Write the failing test**

`tests/test_examples_withdraw.py`:

```python
from specstress.runner import run_case
from specstress.scorer import score
from examples.withdraw.case import CASE


def test_weak_spec_is_underconstrained():
    results = [
        run_case(name, impl, CASE.specs["weak"])
        for name, impl in CASE.mutants.items()
    ]
    s = score(results, reference_name="correct_withdraw")
    assert s["diagnosis"] == "UNDERCONSTRAINED"
    assert len(s["surviving_mutants"]) >= 1


def test_strong_spec_kills_all_mutants():
    results = [
        run_case(name, impl, CASE.specs["strong"])
        for name, impl in CASE.mutants.items()
    ]
    s = score(results, reference_name="correct_withdraw")
    assert s["surviving_mutants"] == []
    assert s["diagnosis"] == "STRONG"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_examples_withdraw.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `examples/withdraw/case.py`**

```python
from __future__ import annotations

from hypothesis import given, settings, strategies as st

from specstress.models import SpecCase


# --- Implementations -----------------------------------------------------

def correct_withdraw(balance, amount):
    if amount > 0 and amount <= balance:
        return True, balance - amount
    return False, balance


def abs_amount(balance, amount):
    # Accepts negative withdrawals by silently flipping the sign.
    return True, balance - abs(amount)


def clamped(balance, amount):
    # Caps the balance at zero instead of rejecting overdrafts.
    return True, max(0, balance - amount)


def noop(balance, amount):
    # Pretends every withdrawal succeeded without moving money.
    return True, balance


def allows_zero(balance, amount):
    # Treats amount==0 as a success.
    if amount >= 0 and amount <= balance:
        return True, balance - amount
    return False, balance


# --- Specs ---------------------------------------------------------------

_strategy = st.tuples(
    st.integers(min_value=0, max_value=10_000),       # balance
    st.integers(min_value=-1_000, max_value=10_000),  # amount
)


def weak_spec(impl):
    @settings(max_examples=100, deadline=None)
    @given(_strategy)
    def test(args):
        balance, amount = args
        ok, new_balance = impl(balance, amount)
        assert new_balance >= 0, "balance must not go negative"
    return test


def strong_spec(impl):
    @settings(max_examples=200, deadline=None)
    @given(_strategy)
    def test(args):
        balance, amount = args
        ok, new_balance = impl(balance, amount)

        should_succeed = amount > 0 and amount <= balance

        assert ok == should_succeed, f"success={ok!r} but should={should_succeed!r}"
        if should_succeed:
            assert new_balance == balance - amount, "balance must decrease by amount"
        else:
            assert new_balance == balance, "balance must not change on failure"
    return test


# --- Case ----------------------------------------------------------------

CASE = SpecCase(
    name="withdraw",
    intent="Decrement balance by amount iff amount is positive and balance suffices.",
    input_strategy=_strategy,
    reference_impl=correct_withdraw,
    specs={"weak": weak_spec, "strong": strong_spec},
    mutants={
        "correct_withdraw": correct_withdraw,
        "abs_amount": abs_amount,
        "clamped": clamped,
        "noop": noop,
        "allows_zero": allows_zero,
    },
)
```

- [ ] **Step 5: Add `examples/withdraw/__init__.py`**

```python
from .case import CASE  # noqa: F401
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_examples_withdraw.py -v`
Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add examples/withdraw/ tests/test_examples_withdraw.py
git commit -m "feat(examples): add bank withdrawal demo"
```

---

### Task 7: Sanitize demo

**Files:**
- Create: `examples/sanitize/__init__.py`
- Create: `examples/sanitize/intent.md`
- Create: `examples/sanitize/case.py`
- Test: `tests/test_examples_sanitize.py`

The sanitize demo strips script execution from HTML. We don't try to be a real
sanitizer — we just demonstrate that a string-replace approach has gaping holes. Use a
small Hypothesis strategy that injects known attack payloads alongside benign text.

- [ ] **Step 1: Write `examples/sanitize/intent.md`**

```markdown
# Sanitize

**Function:** `sanitize(html: str) -> str`

**Intent:** Return an HTML string with all script-execution vectors removed while
preserving visible text. Specifically: no `<script>` tags, no `on*=` event-handler
attributes, no `javascript:` URLs (case-insensitive).

**Why this demo:** Naive string-replace sanitizers are a classic class of
under-specified security code. The weak `"<script>" not in output` check is happily
satisfied by uppercase `<SCRIPT>`, by `onclick=` handlers, and by `javascript:` URLs.
```

- [ ] **Step 2: Write the failing test**

`tests/test_examples_sanitize.py`:

```python
from specstress.runner import run_case
from specstress.scorer import score
from examples.sanitize.case import CASE


def test_weak_spec_is_underconstrained():
    results = [
        run_case(name, impl, CASE.specs["weak"])
        for name, impl in CASE.mutants.items()
    ]
    s = score(results, reference_name="correct_sanitize")
    assert s["diagnosis"] == "UNDERCONSTRAINED"
    assert len(s["surviving_mutants"]) >= 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_examples_sanitize.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `examples/sanitize/case.py`**

```python
from __future__ import annotations

import re

from hypothesis import given, settings, strategies as st

from specstress.models import SpecCase


_SCRIPT_RE = re.compile(r"<script[^>]*?>.*?</script\s*>", re.IGNORECASE | re.DOTALL)
_ON_ATTR_RE = re.compile(r"\son[a-z]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
_JS_URL_RE = re.compile(r"javascript:", re.IGNORECASE)


# --- Implementations -----------------------------------------------------

def correct_sanitize(html):
    out = _SCRIPT_RE.sub("", html)
    out = _ON_ATTR_RE.sub("", out)
    out = _JS_URL_RE.sub("blocked:", out)
    return out


def lowercase_only(html):
    return html.replace("<script>", "").replace("</script>", "")


def case_insensitive_tag_only(html):
    return _SCRIPT_RE.sub("", html)


def drop_everything(html):
    return ""


# --- Specs ---------------------------------------------------------------

_payloads = st.sampled_from([
    "<script>alert(1)</script>",
    "<SCRIPT>alert(1)</SCRIPT>",
    "<a onclick=\"alert(1)\">x</a>",
    "<a href=\"javascript:alert(1)\">x</a>",
    "<a href=\"JavaScript:alert(1)\">x</a>",
    "hello world",
    "<p>safe content</p>",
])

_strategy = st.lists(_payloads, min_size=1, max_size=4).map("".join)


def weak_spec(impl):
    @settings(max_examples=100, deadline=None)
    @given(_strategy)
    def test(html):
        out = impl(html)
        assert "<script>" not in out
    return test


def strong_spec(impl):
    @settings(max_examples=200, deadline=None)
    @given(_strategy)
    def test(html):
        out = impl(html)
        low = out.lower()
        assert "<script" not in low, "script tag survived"
        assert not re.search(r"\son[a-z]+\s*=", low), "event handler survived"
        assert "javascript:" not in low, "javascript: URL survived"
        # Preserve some visible text if the input had any plain text payload.
        if "hello world" in html:
            assert "hello world" in out, "safe text was destroyed"
    return test


CASE = SpecCase(
    name="sanitize",
    intent="Strip script execution while preserving visible text.",
    input_strategy=_strategy,
    reference_impl=correct_sanitize,
    specs={"weak": weak_spec, "strong": strong_spec},
    mutants={
        "correct_sanitize": correct_sanitize,
        "lowercase_only": lowercase_only,
        "case_insensitive_tag_only": case_insensitive_tag_only,
        "drop_everything": drop_everything,
    },
)
```

- [ ] **Step 5: Add `examples/sanitize/__init__.py`**

```python
from .case import CASE  # noqa: F401
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_examples_sanitize.py -v`
Expected: 1 passed.

- [ ] **Step 7: Commit**

```bash
git add examples/sanitize/ tests/test_examples_sanitize.py
git commit -m "feat(examples): add HTML sanitizer demo"
```

---

## Chunk 4: Reports & Registry

### Task 8: Examples registry

**Files:**
- Modify: `examples/__init__.py`
- Test: `tests/test_examples_registry.py`

A single registry lets the Streamlit UI enumerate all available cases without importing each by hand.

- [ ] **Step 1: Write the failing test**

`tests/test_examples_registry.py`:

```python
from examples import REGISTRY


def test_registry_contains_three_cases():
    assert set(REGISTRY.keys()) == {"sort", "withdraw", "sanitize"}


def test_registry_cases_have_weak_and_strong_specs():
    for name, case in REGISTRY.items():
        assert "weak" in case.specs, f"{name} missing weak spec"
        assert "strong" in case.specs, f"{name} missing strong spec"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_examples_registry.py -v`
Expected: ImportError — `REGISTRY` not defined.

- [ ] **Step 3: Implement `examples/__init__.py`**

```python
from .sort.case import CASE as _SORT
from .withdraw.case import CASE as _WITHDRAW
from .sanitize.case import CASE as _SANITIZE


REGISTRY = {
    "sort": _SORT,
    "withdraw": _WITHDRAW,
    "sanitize": _SANITIZE,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_examples_registry.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add examples/__init__.py tests/test_examples_registry.py
git commit -m "feat(examples): expose REGISTRY for UI discovery"
```

---

### Task 9: Markdown report generator

**Files:**
- Create: `specstress/reports.py`
- Test: `tests/test_reports.py`

- [ ] **Step 1: Write failing tests**

`tests/test_reports.py`:

```python
from specstress.models import CaseReport, RunResult
from specstress.reports import render_markdown


def test_markdown_contains_headline_fields():
    report = CaseReport(
        case_name="sort",
        spec_name="weak",
        results=[
            RunResult("correct_sort", True, None, None),
            RunResult("always_empty", True, None, None),
            RunResult("drops_last", False, "AssertionError", "Falsifying example: xs=[1]"),
        ],
        mutation_score=0.5,
        diagnosis="UNDERCONSTRAINED",
        surviving_mutants=["always_empty"],
        reference_passed=True,
        notes=["Consider preservation property."],
    )
    md = render_markdown(report)
    assert "# SpecStress Report" in md
    assert "sort" in md
    assert "UNDERCONSTRAINED" in md
    assert "50%" in md
    assert "always_empty" in md
    assert "Falsifying example" in md
    assert "preservation property" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_reports.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `specstress/reports.py`**

```python
from __future__ import annotations

from .models import CaseReport


def render_markdown(report: CaseReport) -> str:
    pct = f"{report.mutation_score * 100:.0f}%"
    lines: list[str] = []
    lines.append("# SpecStress Report")
    lines.append("")
    lines.append(f"**Case:** `{report.case_name}`  ")
    lines.append(f"**Spec:** `{report.spec_name}`  ")
    lines.append(f"**Diagnosis:** **{report.diagnosis}**  ")
    lines.append(f"**Mutation score:** {pct}  ")
    lines.append(f"**Reference passed:** {report.reference_passed}")
    lines.append("")

    lines.append("## Per-implementation results")
    lines.append("")
    lines.append("| Implementation | Passed | Counterexample |")
    lines.append("| --- | --- | --- |")
    for r in report.results:
        ce = (r.counterexample or "").replace("|", "\\|") or "—"
        lines.append(f"| `{r.impl_name}` | {'✅' if r.passed else '❌'} | {ce} |")
    lines.append("")

    if report.surviving_mutants:
        lines.append("## Surviving bad implementations")
        lines.append("")
        for name in report.surviving_mutants:
            lines.append(f"- `{name}`")
        lines.append("")

    if report.notes:
        lines.append("## Notes")
        lines.append("")
        for n in report.notes:
            lines.append(f"- {n}")
        lines.append("")

    failed = [r for r in report.results if not r.passed]
    if failed:
        lines.append("## Failure details")
        lines.append("")
        for r in failed:
            lines.append(f"### `{r.impl_name}`")
            lines.append("")
            lines.append("```")
            lines.append((r.error or "").strip())
            lines.append("```")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_reports.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add specstress/reports.py tests/test_reports.py
git commit -m "feat(reports): render CaseReport as Markdown"
```

---

### Task 10: Orchestrator API

**Files:**
- Create: `specstress/api.py`
- Test: `tests/test_api.py`

`stress_case(case, spec_name)` is the one-call entry point used by the UI: it runs every mutant against the chosen spec, scores them, and returns a `CaseReport`.

- [ ] **Step 1: Write failing tests**

`tests/test_api.py`:

```python
from specstress.api import stress_case
from examples.sort.case import CASE as SORT_CASE


def test_stress_case_returns_underconstrained_for_weak_sort():
    report = stress_case(SORT_CASE, "weak")
    assert report.case_name == "sort"
    assert report.spec_name == "weak"
    assert report.diagnosis == "UNDERCONSTRAINED"
    assert report.mutation_score < 1.0


def test_stress_case_returns_strong_for_strong_sort():
    report = stress_case(SORT_CASE, "strong")
    assert report.diagnosis == "STRONG"
    assert report.mutation_score == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `specstress/api.py`**

```python
from __future__ import annotations

from .models import CaseReport, SpecCase
from .runner import run_case
from .scorer import score


def stress_case(case: SpecCase, spec_name: str) -> CaseReport:
    spec_factory = case.specs[spec_name]
    results = [
        run_case(impl_name, impl, spec_factory)
        for impl_name, impl in case.mutants.items()
    ]
    s = score(results, reference_name=case.reference_impl.__name__)

    notes: list[str] = []
    if s["diagnosis"] == "UNDERCONSTRAINED":
        notes.append(
            "At least one known-bad implementation satisfied this spec. "
            "Look for missing invariants (length, multiset, immutability, "
            "boundary conditions)."
        )
    elif s["diagnosis"] == "OVERCONSTRAINED":
        notes.append(
            "The reference implementation failed its own spec. "
            "The spec demands behavior the intended implementation does not provide."
        )
    elif s["diagnosis"] == "AMBIGUOUS":
        notes.append(
            "Reference fails AND a bad mutant passes. "
            "The spec is both too strict on intended behavior and too loose on edge cases."
        )

    return CaseReport(
        case_name=case.name,
        spec_name=spec_name,
        results=results,
        mutation_score=s["mutation_score"],
        diagnosis=s["diagnosis"],
        surviving_mutants=s["surviving_mutants"],
        reference_passed=s["reference_passed"],
        notes=notes,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add specstress/api.py tests/test_api.py
git commit -m "feat(api): add stress_case orchestrator"
```

---

## Chunk 5: Streamlit UI & Polish

### Task 11: Streamlit app

**Files:**
- Create: `app.py`

The UI is intentionally thin — it loads the registry, lets the user pick a case + spec, calls `stress_case`, and renders the resulting `CaseReport` (table + diagnosis + downloadable Markdown).

- [ ] **Step 1: Implement `app.py`**

```python
from __future__ import annotations

import inspect

import streamlit as st

from examples import REGISTRY
from specstress.api import stress_case
from specstress.reports import render_markdown


DIAGNOSIS_BADGE = {
    "STRONG": ("✅", "Strong"),
    "UNDERCONSTRAINED": ("⚠️", "Underconstrained"),
    "OVERCONSTRAINED": ("🛑", "Overconstrained"),
    "AMBIGUOUS": ("❓", "Ambiguous"),
}


st.set_page_config(page_title="SpecStress", layout="wide")
st.title("SpecStress")
st.caption("Red-team your specs before AI code uses them.")

with st.sidebar:
    st.header("Case")
    case_name = st.selectbox("Demo problem", list(REGISTRY.keys()))
    case = REGISTRY[case_name]
    spec_name = st.selectbox("Spec to stress-test", list(case.specs.keys()))
    run_clicked = st.button("Run SpecStress", type="primary", use_container_width=True)

col_intent, col_spec = st.columns([1, 1])
with col_intent:
    st.subheader("Intent")
    st.write(case.intent)
    st.markdown("**Known-bad mutants:**")
    for name in case.mutants:
        marker = "🟢" if name == case.reference_impl.__name__ else "🔴"
        st.markdown(f"- {marker} `{name}`")

with col_spec:
    st.subheader(f"Spec: `{spec_name}`")
    try:
        src = inspect.getsource(case.specs[spec_name])
    except OSError:
        src = "<source unavailable>"
    st.code(src, language="python")

if run_clicked:
    with st.spinner("Stress-testing spec against adversarial implementations..."):
        report = stress_case(case, spec_name)

    icon, label = DIAGNOSIS_BADGE[report.diagnosis]
    st.markdown(f"## Diagnosis: {icon} **{label}**")

    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("Mutation score", f"{report.mutation_score * 100:.0f}%")
    m_col2.metric("Surviving bad mutants", len(report.surviving_mutants))
    m_col3.metric("Reference passed", "✅" if report.reference_passed else "❌")

    st.subheader("Per-implementation results")
    rows = []
    for r in report.results:
        is_ref = r.impl_name == case.reference_impl.__name__
        rows.append({
            "Implementation": r.impl_name,
            "Reference?": "✅" if is_ref else "",
            "Passed": "✅" if r.passed else "❌",
            "Counterexample": r.counterexample or "",
        })
    st.dataframe(rows, hide_index=True, use_container_width=True)

    if report.surviving_mutants:
        st.warning(
            "These bad implementations passed the spec — your spec missed them:\n\n"
            + "\n".join(f"- `{m}`" for m in report.surviving_mutants)
        )
    if not report.reference_passed:
        st.error(
            "The reference implementation failed the spec — the spec rules out the "
            "behavior you actually want."
        )

    if report.notes:
        st.subheader("Notes")
        for n in report.notes:
            st.info(n)

    failures = [r for r in report.results if not r.passed]
    if failures:
        with st.expander("Failure details"):
            for r in failures:
                st.markdown(f"**`{r.impl_name}`**")
                st.code(r.error or "", language="text")

    md = render_markdown(report)
    st.download_button(
        "Download Markdown report",
        data=md,
        file_name=f"specstress-{case.name}-{spec_name}.md",
        mime="text/markdown",
    )
```

- [ ] **Step 2: Smoke-test the app**

Run: `streamlit run app.py --server.headless true --server.port 8765 & sleep 4 && curl -sf http://localhost:8765/_stcore/health && kill %1`
Expected: `ok`, then the background streamlit process exits cleanly.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat(ui): streamlit dashboard for case selection and reports"
```

---

### Task 12: Sample report + README polish

**Files:**
- Create: `reports/sample_report.md`
- Modify: `README.md`

- [ ] **Step 1: Generate `reports/sample_report.md`**

```bash
mkdir -p reports
python -c "
from examples.sort.case import CASE
from specstress.api import stress_case
from specstress.reports import render_markdown
report = stress_case(CASE, 'weak')
with open('reports/sample_report.md', 'w') as f:
    f.write(render_markdown(report))
print('wrote reports/sample_report.md')
"
```

Expected output: `wrote reports/sample_report.md`. Open the file and confirm it shows `UNDERCONSTRAINED` for the weak sort spec.

- [ ] **Step 2: Expand `README.md`**

Replace the existing `README.md` with:

```markdown
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
```

- [ ] **Step 3: Commit**

```bash
git add reports/sample_report.md README.md
git commit -m "docs: add sample report and full README"
```

---

### Task 13: Full-suite green check

- [ ] **Step 1: Run the entire test suite**

Run: `pytest -q`
Expected: All tests pass (≈14 tests). If Hypothesis flakes on a deadline, the
`deadline=None` settings should already prevent it.

- [ ] **Step 2: Verify Streamlit app boots**

Run: `streamlit run app.py --server.headless true --server.port 8765 & sleep 4 && curl -sf http://localhost:8765/_stcore/health && kill %1`
Expected: `ok`.

- [ ] **Step 3: Final commit if anything changed**

```bash
git status
# if dirty:
git add -A
git commit -m "chore: final polish"
```

---

## Chunk 6: GitHub Repo

### Task 14: Create the GitHub repo and push

- [ ] **Step 1: Create the repo (public, no auto-init)**

Run:

```bash
gh repo create specstress \
  --public \
  --description "Red-team your specs before AI code uses them — mutation testing for specifications." \
  --source . \
  --remote origin \
  --push
```

Expected: a new repo at `https://github.com/Sakeeb91/specstress` with `main` pushed.

- [ ] **Step 2: Verify**

Run: `gh repo view --json url,visibility,defaultBranchRef`
Expected: visibility public, defaultBranchRef.name == main.
