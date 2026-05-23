from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest

from examples.sort.case import CASE as SORT_CASE
from specstress.api import stress_case
from specstress.llm import (
    MissingAPIKeyError,
    build_user_prompt,
    suggest_stronger_spec,
    SYSTEM_PROMPT,
)


@pytest.fixture
def weak_sort_report():
    return stress_case(SORT_CASE, "weak")


def _fake_sampling_client(decoded_text: str = "suggested fix"):
    client = MagicMock()

    tokenizer = MagicMock()
    tokenizer.apply_chat_template.return_value = "<formatted prompt>"
    tokenizer.encode.return_value = [1, 2, 3]
    tokenizer.decode.return_value = decoded_text
    client.get_tokenizer.return_value = tokenizer

    seq = MagicMock()
    seq.tokens = [10, 11, 12]
    response = MagicMock()
    response.sequences = [seq]
    future = MagicMock()
    future.result.return_value = response
    client.sample.return_value = future

    return client, tokenizer


def test_user_prompt_includes_intent_mutants_and_spec(weak_sort_report):
    prompt = build_user_prompt(SORT_CASE, "weak", weak_sort_report)
    assert SORT_CASE.intent in prompt
    assert "always_empty" in prompt
    assert "weak_spec" in prompt or "def weak" in prompt
    assert "UNDERCONSTRAINED" in prompt
    weak_src = inspect.getsource(SORT_CASE.specs["weak"])
    assert weak_src.strip().splitlines()[0] in prompt


def test_user_prompt_includes_counterexamples_when_present():
    fake_report = MagicMock()
    fake_report.diagnosis = "UNDERCONSTRAINED"
    fake_report.mutation_score = 0.0
    fake_report.surviving_mutants = ["always_empty", "unique_sorted"]
    fake_report.results = []
    fake_report.case_name = "sort"
    fake_report.spec_name = "weak"
    prompt = build_user_prompt(SORT_CASE, "weak", fake_report)
    assert "always_empty" in prompt
    assert "unique_sorted" in prompt


def test_suggest_uses_injected_client_and_returns_decoded_text(weak_sort_report):
    client, tokenizer = _fake_sampling_client("Add Counter(output) == Counter(input)")

    out = suggest_stronger_spec(SORT_CASE, "weak", weak_sort_report, client=client)

    assert out == "Add Counter(output) == Counter(input)"

    template_call = tokenizer.apply_chat_template.call_args
    messages = template_call.args[0] if template_call.args else template_call.kwargs["conversation"]
    roles = [m["role"] for m in messages]
    assert roles == ["system", "user"]
    assert messages[0]["content"] == SYSTEM_PROMPT
    assert "always_empty" in messages[1]["content"]
    assert template_call.kwargs.get("add_generation_prompt") is True
    assert template_call.kwargs.get("tokenize") is False

    sample_kwargs = client.sample.call_args.kwargs
    assert sample_kwargs["num_samples"] == 1
    assert sample_kwargs["sampling_params"].max_tokens == 1500

    tokenizer.decode.assert_called_once()
    decoded_tokens = tokenizer.decode.call_args.args[0]
    assert decoded_tokens == [10, 11, 12]


def test_suggest_raises_when_no_api_key_and_no_client(monkeypatch, weak_sort_report):
    monkeypatch.delenv("TINKER_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError):
        suggest_stronger_spec(SORT_CASE, "weak", weak_sort_report)
