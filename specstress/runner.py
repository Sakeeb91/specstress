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
