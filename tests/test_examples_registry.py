from examples import REGISTRY


def test_registry_contains_three_cases():
    assert set(REGISTRY.keys()) == {"sort", "withdraw", "sanitize"}


def test_registry_cases_have_weak_and_strong_specs():
    for name, case in REGISTRY.items():
        assert "weak" in case.specs, f"{name} missing weak spec"
        assert "strong" in case.specs, f"{name} missing strong spec"
