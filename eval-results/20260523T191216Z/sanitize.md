# Eval artifact — `sanitize`

- Before: **UNDERCONSTRAINED** (score 0.00)
- After:  **OVERCONSTRAINED** (score 1.00)
- Reference passes: False
- Success (after == STRONG, score == 1.0): **False**

## Raw model output

1. The spec is missing invariants that ensure the preservation of non-script content and structural text, particularly the retention of visible text outside script tags and the integrity of HTML structure (e.g., tag names, attributes, and visible content). The current spec only checks for the absence of `<script>`, which is insufficient: it fails to prevent over-removal (e.g., deleting all content) or under-removal (e.g., missing case-insensitive or attribute-based script patterns), and it does not require that meaningful text content remains.

2. - Ensure that the output contains at least some visible text from the input when the input contains non-script content, to reject implementations that drop everything.  
   - Verify that the output retains the original case of non-script tag names and attribute values, to distinguish correct sanitization from case-insensitive tag stripping.  
   - Confirm that the output preserves text content within non-script elements (e.g., `<div>hello</div>` should not become empty), to reject implementations that naively remove all tags or content.  

3. ```python
def weak_spec(impl):
    @settings(max_examples=100, deadline=None)
    @given(_strategy)
    def test(html):
        out = impl(html)
        assert "<script>" not in out
        assert "<SCRIPT>" not in out
        assert "<ScRiPt>" not in out
        assert any(c not in " \t\n\r" for c in out) or not any(c in "<>" for c in html), "Must preserve non-whitespace content when present"
        assert out == html or any(c in "<>" for c in out), "Must preserve HTML structure if input contains tags"
        if "<script" in html or "</script" in html:
            assert len(out) < len(html) or out == html, "Should reduce or alter content when script tags are present"
    return test
```