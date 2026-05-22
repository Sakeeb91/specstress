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
