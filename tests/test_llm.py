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


def test_suggest_uses_injected_client_and_returns_text(weak_sort_report):
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_block = MagicMock()
    mock_block.text = "Add Counter(output) == Counter(input)"
    mock_message.content = [mock_block]
    mock_client.messages.create.return_value = mock_message

    out = suggest_stronger_spec(SORT_CASE, "weak", weak_sort_report, client=mock_client)

    assert out == "Add Counter(output) == Counter(input)"
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"].startswith("claude-")
    sys_blocks = call_kwargs["system"]
    assert isinstance(sys_blocks, list)
    assert sys_blocks[0]["text"] == SYSTEM_PROMPT
    assert sys_blocks[0]["cache_control"] == {"type": "ephemeral"}
    user_msg = call_kwargs["messages"][0]["content"]
    assert "always_empty" in user_msg


def test_suggest_raises_when_no_api_key_and_no_client(monkeypatch, weak_sort_report):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError):
        suggest_stronger_spec(SORT_CASE, "weak", weak_sort_report)
