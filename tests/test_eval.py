from __future__ import annotations

import inspect

import pytest

from examples.sort.case import CASE as SORT_CASE, strong_spec as SORT_STRONG
from examples.withdraw.case import CASE as WITHDRAW_CASE, strong_spec as WITHDRAW_STRONG
from specstress.eval import (
    EvalError,
    EvalRow,
    compile_spec_factory,
    evaluate_suggestion,
    extract_spec_code,
    run_eval_one,
)


def _wrap_as_suggestion(spec_source: str) -> str:
    """Format raw spec source as if the LLM had emitted it (markdown + prose)."""
    return f"""# Diagnosis

The spec is missing X, Y, and Z.

# Suggested additions

- Add element-preservation
- Add length check

# Revised spec

```python
{spec_source}
```
"""


def test_extract_spec_code_finds_last_block():
    text = "intro\n```python\nfirst = 1\n```\nmiddle\n```python\nsecond = 2\n```\nend"
    assert extract_spec_code(text).strip() == "second = 2"


def test_extract_spec_code_accepts_unlabeled_fence():
    text = "```\nbare = 1\n```"
    assert extract_spec_code(text).strip() == "bare = 1"


def test_extract_spec_code_raises_when_missing():
    with pytest.raises(EvalError):
        extract_spec_code("no code blocks here, just prose")


def test_compile_spec_factory_returns_one_arg_callable():
    original = SORT_CASE.specs["weak"]
    code = inspect.getsource(SORT_STRONG)
    factory = compile_spec_factory(code, original_factory=original)
    sig = inspect.signature(factory)
    assert len(sig.parameters) == 1
    # Sanity: calling factory(impl) returns a callable test
    test_fn = factory(SORT_CASE.reference_impl)
    assert callable(test_fn)


def test_evaluate_suggestion_round_trip_sort_strong():
    """Feed the project's own strong_spec source back through the harness;
    it must round-trip to a STRONG diagnosis with mutation score 1.0."""
    suggestion = _wrap_as_suggestion(inspect.getsource(SORT_STRONG))
    report = evaluate_suggestion(SORT_CASE, "weak", suggestion)
    assert report.diagnosis == "STRONG", report.diagnosis
    assert report.mutation_score == 1.0
    assert report.reference_passed is True


def test_evaluate_suggestion_round_trip_withdraw_strong():
    suggestion = _wrap_as_suggestion(inspect.getsource(WITHDRAW_STRONG))
    report = evaluate_suggestion(WITHDRAW_CASE, "weak", suggestion)
    assert report.diagnosis == "STRONG"
    assert report.mutation_score == 1.0


def test_run_eval_one_uses_injected_suggester():
    captured = {}

    def fake_suggester(case, spec_name, report):
        captured["case_name"] = case.name
        captured["spec_name"] = spec_name
        captured["before_diag"] = report.diagnosis
        return _wrap_as_suggestion(inspect.getsource(SORT_STRONG))

    row = run_eval_one(SORT_CASE, "weak", suggester=fake_suggester)
    assert isinstance(row, EvalRow)
    assert captured["case_name"] == "sort"
    assert captured["spec_name"] == "weak"
    assert captured["before_diag"] == "UNDERCONSTRAINED"
    assert row.before_diagnosis == "UNDERCONSTRAINED"
    assert row.after_diagnosis == "STRONG"
    assert row.after_score == 1.0
    assert row.success is True
    assert row.error is None


def test_run_eval_one_marks_error_on_uncompilable_suggestion():
    def bad_suggester(case, spec_name, report):
        return "I have nothing helpful to say."

    row = run_eval_one(SORT_CASE, "weak", suggester=bad_suggester)
    assert row.success is False
    assert row.error is not None
    assert row.after_diagnosis == "ERROR"
