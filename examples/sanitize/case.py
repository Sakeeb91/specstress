from __future__ import annotations

import re

from hypothesis import given, settings, strategies as st

from specstress.models import SpecCase


_SCRIPT_RE = re.compile(r"<script[^>]*?>.*?</script\s*>", re.IGNORECASE | re.DOTALL)
_ON_ATTR_RE = re.compile(r"\son[a-z]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
_JS_URL_RE = re.compile(r"javascript:", re.IGNORECASE)


# --- Implementations -----------------------------------------------------

def correct_sanitize(html):
    out = _SCRIPT_RE.sub("", html)
    out = _ON_ATTR_RE.sub("", out)
    out = _JS_URL_RE.sub("blocked:", out)
    return out


def lowercase_only(html):
    return html.replace("<script>", "").replace("</script>", "")


def case_insensitive_tag_only(html):
    return _SCRIPT_RE.sub("", html)


def drop_everything(html):
    return ""


# --- Specs ---------------------------------------------------------------

_payloads = st.sampled_from([
    "<script>alert(1)</script>",
    "<SCRIPT>alert(1)</SCRIPT>",
    "<a onclick=\"alert(1)\">x</a>",
    "<a href=\"javascript:alert(1)\">x</a>",
    "<a href=\"JavaScript:alert(1)\">x</a>",
    "hello world",
    "<p>safe content</p>",
])

_strategy = st.lists(_payloads, min_size=1, max_size=4).map("".join)


def weak_spec(impl):
    @settings(max_examples=100, deadline=None)
    @given(_strategy)
    def test(html):
        out = impl(html)
        assert "<script>" not in out
    return test


def strong_spec(impl):
    @settings(max_examples=200, deadline=None)
    @given(_strategy)
    def test(html):
        out = impl(html)
        low = out.lower()
        assert "<script" not in low, "script tag survived"
        assert not re.search(r"\son[a-z]+\s*=", low), "event handler survived"
        assert "javascript:" not in low, "javascript: URL survived"
        # Preserve some visible text if the input had any plain text payload.
        if "hello world" in html:
            assert "hello world" in out, "safe text was destroyed"
    return test


CASE = SpecCase(
    name="sanitize",
    intent="Strip script execution while preserving visible text.",
    input_strategy=_strategy,
    reference_impl=correct_sanitize,
    specs={"weak": weak_spec, "strong": strong_spec},
    mutants={
        "correct_sanitize": correct_sanitize,
        "lowercase_only": lowercase_only,
        "case_insensitive_tag_only": case_insensitive_tag_only,
        "drop_everything": drop_everything,
    },
)
