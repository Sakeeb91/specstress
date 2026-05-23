from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from typing import Any, Callable

from .api import stress_case
from .models import CaseReport, SpecCase, SpecFactory


class EvalError(RuntimeError):
    """Raised when a suggestion cannot be parsed, compiled, or evaluated."""


_FENCE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def extract_spec_code(llm_text: str) -> str:
    """Pull the last python code fence out of the LLM response."""
    blocks = _FENCE_RE.findall(llm_text)
    if not blocks:
        raise EvalError("no fenced code block found in LLM response")
    return blocks[-1].strip()


def compile_spec_factory(code: str, *, original_factory: SpecFactory) -> SpecFactory:
    """Exec `code` in the original spec's module globals; return the new factory.

    Sharing the original module's globals means the suggested spec inherits
    `_strategy`, `Counter`, `re`, etc. without the LLM having to re-import.
    """
    namespace: dict[str, Any] = dict(original_factory.__globals__)
    before_ids = {k: id(v) for k, v in namespace.items()}

    try:
        compiled = compile(code, "<suggested-spec>", "exec")
        exec(compiled, namespace)
    except SyntaxError as e:
        raise EvalError(f"suggested code did not parse: {e}") from e
    except Exception as e:  # noqa: BLE001 — surface anything verbatim
        raise EvalError(f"suggested code raised at import time: {e}") from e

    candidates: list[tuple[str, Callable[..., Any]]] = []
    for name, val in namespace.items():
        if name.startswith("__"):
            continue
        if not callable(val):
            continue
        if before_ids.get(name) == id(val):
            continue
        try:
            sig = inspect.signature(val)
        except (TypeError, ValueError):
            continue
        params = list(sig.parameters.values())
        if len(params) != 1:
            continue
        candidates.append((name, val))

    if not candidates:
        raise EvalError("no new single-argument callable found in suggested code")

    original_name = original_factory.__name__
    for name, val in candidates:
        if name == original_name:
            return val
    return candidates[-1][1]


def evaluate_suggestion(
    case: SpecCase,
    spec_name: str,
    llm_text: str,
) -> CaseReport:
    """Compile the suggestion and run stress_case with it. Returns the new report."""
    code = extract_spec_code(llm_text)
    original_factory = case.specs[spec_name]
    new_factory = compile_spec_factory(code, original_factory=original_factory)

    new_specs = {**case.specs, "_suggested": new_factory}
    new_case = SpecCase(
        name=case.name,
        intent=case.intent,
        input_strategy=case.input_strategy,
        reference_impl=case.reference_impl,
        specs=new_specs,
        mutants=case.mutants,
    )
    return stress_case(new_case, "_suggested")


@dataclass
class EvalRow:
    case_name: str
    before_diagnosis: str
    before_score: float
    after_diagnosis: str
    after_score: float
    ref_passes: bool
    success: bool
    error: str | None = None
    raw_suggestion: str | None = None


def run_eval_one(
    case: SpecCase,
    spec_name: str,
    *,
    suggester: Callable[[SpecCase, str, CaseReport], str],
) -> EvalRow:
    before = stress_case(case, spec_name)
    if before.diagnosis != "UNDERCONSTRAINED":
        return EvalRow(
            case_name=case.name,
            before_diagnosis=before.diagnosis,
            before_score=before.mutation_score,
            after_diagnosis="SKIPPED",
            after_score=0.0,
            ref_passes=before.reference_passed,
            success=False,
            error=f"precondition: spec is {before.diagnosis}, not UNDERCONSTRAINED",
        )

    try:
        suggestion = suggester(case, spec_name, before)
    except Exception as e:  # noqa: BLE001
        return EvalRow(
            case_name=case.name,
            before_diagnosis=before.diagnosis,
            before_score=before.mutation_score,
            after_diagnosis="ERROR",
            after_score=0.0,
            ref_passes=before.reference_passed,
            success=False,
            error=f"suggester raised: {e}",
        )

    try:
        after = evaluate_suggestion(case, spec_name, suggestion)
    except EvalError as e:
        return EvalRow(
            case_name=case.name,
            before_diagnosis=before.diagnosis,
            before_score=before.mutation_score,
            after_diagnosis="ERROR",
            after_score=0.0,
            ref_passes=before.reference_passed,
            success=False,
            error=str(e),
            raw_suggestion=suggestion,
        )

    return EvalRow(
        case_name=case.name,
        before_diagnosis=before.diagnosis,
        before_score=before.mutation_score,
        after_diagnosis=after.diagnosis,
        after_score=after.mutation_score,
        ref_passes=after.reference_passed,
        success=(after.diagnosis == "STRONG" and after.mutation_score == 1.0),
        raw_suggestion=suggestion,
    )
