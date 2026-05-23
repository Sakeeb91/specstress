from __future__ import annotations

import inspect
import os
from typing import Any

from .models import CaseReport, SpecCase


DEFAULT_MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507"


SYSTEM_PROMPT = """You are a specification-validation assistant. SpecStress runs a
property-based specification against a panel of adversarial implementations. When a
known-bad implementation passes the spec, the spec is underconstrained — it is missing
an invariant the developer intended.

Your job: read the user's intent, the current weak spec, and the names + behavior of the
surviving bad implementations, and propose the **minimum set of additional properties**
that would kill the surviving mutants while still admitting the reference implementation.

Output format:
1. A one-paragraph diagnosis of what the spec is missing, named concretely.
2. A bulleted list of additional `assert` statements to add to the spec, with one
   sentence explaining each.
3. The full revised Python spec function as a code block.

Be precise. Use the Hypothesis style already in the user's spec. Do not invent new
test infrastructure. Do not add invariants the intent does not justify.
""".strip()


class MissingAPIKeyError(RuntimeError):
    """Raised when TINKER_API_KEY is unset and no client was injected."""


def _safe_source(fn: Any) -> str:
    try:
        return inspect.getsource(fn)
    except (OSError, TypeError):
        return f"<source unavailable for {getattr(fn, '__name__', fn)!r}>"


def build_user_prompt(case: SpecCase, spec_name: str, report: CaseReport) -> str:
    weak_src = _safe_source(case.specs[spec_name])
    ref_name = case.reference_impl.__name__
    ref_src = _safe_source(case.reference_impl)

    survivors_block_lines: list[str] = []
    for name in report.surviving_mutants:
        impl = case.mutants.get(name)
        src = _safe_source(impl) if impl else "<impl not in case>"
        survivors_block_lines.append(f"### `{name}` (passes the spec but is wrong)\n```python\n{src.strip()}\n```")
    survivors_block = "\n\n".join(survivors_block_lines) if survivors_block_lines else "_(none)_"

    counterexamples_block_lines: list[str] = []
    for r in report.results:
        if r.counterexample:
            counterexamples_block_lines.append(f"- `{r.impl_name}`: {r.counterexample}")
    counterexamples_block = "\n".join(counterexamples_block_lines) if counterexamples_block_lines else "_(none)_"

    return f"""# Case

**Name:** `{case.name}`
**Intent:** {case.intent}

# Current spec (`{spec_name}`)

This is the spec we are stress-testing. SpecStress reports it as **{report.diagnosis}**
with a mutation score of **{report.mutation_score * 100:.0f}%**.

```python
{weak_src.strip()}
```

# Reference implementation (`{ref_name}`)

This is the implementation we want the spec to accept.

```python
{ref_src.strip()}
```

# Surviving bad implementations

These are wrong but the current spec accepts them. Your suggested properties must
reject every one of them.

{survivors_block}

# Hypothesis counterexamples seen so far

{counterexamples_block}

# Task

Suggest the missing properties. Follow the output format from the system message.
""".strip()


def _build_sampling_client(model: str):
    api_key = os.environ.get("TINKER_API_KEY")
    if not api_key:
        raise MissingAPIKeyError(
            "TINKER_API_KEY is not set. Export it locally, or add it to "
            "Streamlit Cloud's secrets as TINKER_API_KEY."
        )
    import tinker
    service = tinker.ServiceClient()
    return service.create_sampling_client(base_model=model)


def suggest_stronger_spec(
    case: SpecCase,
    spec_name: str,
    report: CaseReport,
    *,
    client: Any | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1500,
    temperature: float = 0.7,
) -> str:
    """Ask a Tinker-hosted Qwen3 to suggest missing properties. Returns the assistant's text."""
    if client is None:
        client = _build_sampling_client(model)

    user_prompt = build_user_prompt(case, spec_name, report)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    tokenizer = client.get_tokenizer()
    formatted = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=False,
    )
    prompt_ids = tokenizer.encode(formatted)

    import tinker
    model_input = tinker.ModelInput.from_ints(prompt_ids)
    sampling_params = tinker.SamplingParams(
        max_tokens=max_tokens,
        temperature=temperature,
    )
    future = client.sample(
        prompt=model_input,
        num_samples=1,
        sampling_params=sampling_params,
    )
    response = future.result()
    output_tokens = response.sequences[0].tokens
    return tokenizer.decode(output_tokens, skip_special_tokens=True)
