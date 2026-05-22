# SpecStress

Red-team your specifications before AI-written code relies on them.

SpecStress runs candidate specs against adversarial implementations using property-based
testing. If known-bad implementations survive, your spec is underconstrained. If known-good
implementations fail, your spec is overconstrained. SpecStress reports a mutation kill
rate and a diagnosis you can act on.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

See `examples/` for the three built-in demos: `sort`, `withdraw`, `sanitize`.
