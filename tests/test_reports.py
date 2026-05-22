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
