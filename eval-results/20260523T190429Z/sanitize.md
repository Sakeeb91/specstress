# Eval artifact — `sanitize`

- Before: **UNDERCONSTRAINED** (score 0.00)
- After:  **OVERCONSTRAINED** (score 1.00)
- Reference passes: False
- Success (after == STRONG, score == 1.0): **False**

## Raw model output

1. The current spec is underconstrained because it only checks for the absence of `<script>` tags, but fails to enforce that legitimate visible content (e.g., text, non-script HTML elements) must be preserved. This allows implementations like `drop_everything` (which returns empty strings) and `lowercase_only` (which fails to handle case variations and attributes) to pass. The spec must additionally verify that syntactically valid text content outside of script tags is retained and that the transformation is not overly aggressive.

2. - Add an assertion that ensures the output contains at least some of the original visible text, rejecting implementations that drop all content.  
   - Add an assertion that verifies case-insensitive script tag removal by testing inputs with mixed-case tags like `<ScRiPt>`.  
   - Add an assertion that ensures JavaScript handlers in attributes (e.g., `onclick="alert()"`) are removed, rejecting implementations that only remove `<script>` tags but ignore inline event handlers.

```python
def weak_spec(impl):
    @settings(max_examples=100, deadline=None)
    @given(_strategy)
    def test(html):
        out = impl(html)
        assert "<script>" not in out.lower()
        assert "<script" not in out.lower()
        assert "script" not in out.lower()
        assert any(c.isalpha() or c.isdigit() or c.isspace() for c in out)
        assert out == out.replace("<script>", "").replace("</script>", "").replace("onload=", "").replace("onclick=", "")
    return test
```