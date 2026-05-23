from __future__ import annotations

import inspect
import os

import streamlit as st

from examples import REGISTRY
from specstress.api import stress_case
from specstress.llm import MissingAPIKeyError, suggest_stronger_spec
from specstress.reports import render_markdown


DIAGNOSIS_BADGE = {
    "STRONG": ("✅", "Strong"),
    "UNDERCONSTRAINED": ("⚠️", "Underconstrained"),
    "OVERCONSTRAINED": ("🛑", "Overconstrained"),
    "AMBIGUOUS": ("❓", "Ambiguous"),
}


def _api_key_available() -> bool:
    if os.environ.get("TINKER_API_KEY"):
        return True
    try:
        return bool(st.secrets.get("TINKER_API_KEY"))
    except Exception:
        return False


def _load_api_key_into_env() -> None:
    """Streamlit Cloud stores secrets in st.secrets; copy into env for the SDK."""
    if os.environ.get("TINKER_API_KEY"):
        return
    try:
        key = st.secrets.get("TINKER_API_KEY")
    except Exception:
        key = None
    if key:
        os.environ["TINKER_API_KEY"] = key


st.set_page_config(page_title="SpecStress", layout="wide")
st.title("SpecStress")
st.caption("Red-team your specs before AI code uses them.")

with st.sidebar:
    st.header("Case")
    case_name = st.selectbox("Demo problem", list(REGISTRY.keys()))
    case = REGISTRY[case_name]
    spec_name = st.selectbox("Spec to stress-test", list(case.specs.keys()))
    run_clicked = st.button("Run SpecStress", type="primary", use_container_width=True)

col_intent, col_spec = st.columns([1, 1])
with col_intent:
    st.subheader("Intent")
    st.write(case.intent)
    st.markdown("**Known-bad mutants:**")
    for name in case.mutants:
        marker = "🟢" if name == case.reference_impl.__name__ else "🔴"
        st.markdown(f"- {marker} `{name}`")

with col_spec:
    st.subheader(f"Spec: `{spec_name}`")
    try:
        src = inspect.getsource(case.specs[spec_name])
    except OSError:
        src = "<source unavailable>"
    st.code(src, language="python")

if run_clicked:
    with st.spinner("Stress-testing spec against adversarial implementations..."):
        st.session_state["report"] = stress_case(case, spec_name)
        st.session_state["report_case"] = case.name
        st.session_state["report_spec"] = spec_name
        st.session_state.pop("suggestion", None)

report = st.session_state.get("report")
report_case_name = st.session_state.get("report_case")
report_spec_name = st.session_state.get("report_spec")
report_is_current = (
    report is not None
    and report_case_name == case.name
    and report_spec_name == spec_name
)

if report and report_is_current:
    icon, label = DIAGNOSIS_BADGE[report.diagnosis]
    st.markdown(f"## Diagnosis: {icon} **{label}**")

    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("Mutation score", f"{report.mutation_score * 100:.0f}%")
    m_col2.metric("Surviving bad mutants", len(report.surviving_mutants))
    m_col3.metric("Reference passed", "✅" if report.reference_passed else "❌")

    st.subheader("Per-implementation results")
    rows = []
    for r in report.results:
        is_ref = r.impl_name == case.reference_impl.__name__
        rows.append({
            "Implementation": r.impl_name,
            "Reference?": "✅" if is_ref else "",
            "Passed": "✅" if r.passed else "❌",
            "Counterexample": r.counterexample or "",
        })
    st.dataframe(rows, hide_index=True, use_container_width=True)

    if report.surviving_mutants:
        st.warning(
            "These bad implementations passed the spec — your spec missed them:\n\n"
            + "\n".join(f"- `{m}`" for m in report.surviving_mutants)
        )
    if not report.reference_passed:
        st.error(
            "The reference implementation failed the spec — the spec rules out the "
            "behavior you actually want."
        )

    if report.notes:
        st.subheader("Notes")
        for n in report.notes:
            st.info(n)

    if report.diagnosis == "UNDERCONSTRAINED":
        st.subheader("🤖 Strengthen this spec with Qwen3 (Tinker)")
        st.caption(
            "A Tinker-hosted Qwen3 reads the intent, the weak spec, and the surviving "
            "mutants, and proposes the missing properties."
        )

        if not _api_key_available():
            st.info(
                "Set `TINKER_API_KEY` to enable AI suggestions. Locally: "
                "`export TINKER_API_KEY=...`. On Streamlit Cloud: add it under "
                "**Settings → Secrets** as `TINKER_API_KEY = \"...\"`."
            )
        else:
            if st.button("Suggest stronger spec", type="secondary"):
                _load_api_key_into_env()
                with st.spinner("Asking Qwen3 (via Tinker) for missing properties..."):
                    try:
                        st.session_state["suggestion"] = suggest_stronger_spec(
                            case, spec_name, report
                        )
                    except MissingAPIKeyError as e:
                        st.error(str(e))
                    except Exception as e:  # noqa: BLE001 — surface SDK errors verbatim
                        st.error(f"Tinker API error: {e}")

        if st.session_state.get("suggestion"):
            st.markdown(st.session_state["suggestion"])

    failures = [r for r in report.results if not r.passed]
    if failures:
        with st.expander("Failure details"):
            for r in failures:
                st.markdown(f"**`{r.impl_name}`**")
                st.code(r.error or "", language="text")

    md = render_markdown(report)
    st.download_button(
        "Download Markdown report",
        data=md,
        file_name=f"specstress-{case.name}-{spec_name}.md",
        mime="text/markdown",
    )
