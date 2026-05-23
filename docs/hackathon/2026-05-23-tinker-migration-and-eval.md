# SpecStress — Tinker migration & end-to-end evaluation

**Date:** 2026-05-23
**Project:** [`specstress`](../../README.md)
**Author:** Sakeeb Rahman
**Scope of this document:** Everything done in this session — every decision, the
reasoning behind it, the verification work, the resulting code, the real evaluation
numbers, and the honest limitations. Written for hackathon review: the reviewer
should be able to read this single file and understand what was built, why, and how
well it works.

---

## 1. Executive summary

SpecStress is a property-based "red-team" tool: it runs a candidate spec against a
panel of adversarial implementations (mutants) and tells the developer whether the
spec is strong enough to distinguish the *intended* behavior from known-bad
behaviors. The MVP shipped with an `Anthropic Claude` integration that offered to
*suggest stronger properties* when a spec was diagnosed `UNDERCONSTRAINED`.

In this session I:

1. **Replaced the Anthropic dependency entirely** with [Tinker]
   (Thinking Machines Lab), using the `Qwen/Qwen3-30B-A3B-Instruct-2507` open model.
   Single provider, one API key, billed against the user's existing Tinker credits.
2. **Built a true evaluation harness** (`specstress/eval.py`) that doesn't just
   check whether the suggester returns plausible-looking prose, but mechanically
   compiles the suggested spec, re-runs the stress test, and verifies that the
   suggestion actually kills the surviving mutants. Success ⇔
   `diagnosis == STRONG` and `mutation_score == 1.0`.
3. **Authored two new realistic, high-stakes test cases** (`money`, `jwt`) so the
   evaluation is not just on toy problems.
4. **Ran the real eval** against the live Tinker API and wrote the artifacts.

**Headline result:**

| Run | Cases | PASS | Notes |
| --- | --- | --- | --- |
| Round 1 (3 existing toys) | sort, withdraw, sanitize | 1/3 | sort failed on a defensive-copy bug; sanitize over-constrained |
| Round 2 (all 5 cases) | + money, jwt | 2/5 | sort flipped to PASS (temperature variance); money missed half-cent edge cases; jwt did substring search on base64-encoded tokens |

At 40 % round-trip success on a five-case benchmark, the suggester is **useful as a
draft for human review, not as an autonomous spec generator** — and the eval
harness now exists so we can measure (rather than guess) whether prompt tweaks,
self-critique loops, or fine-tuning move that number.

---

## 2. Background: what SpecStress does (in one diagram)

```
SpecCase                                                  CaseReport
  ├── reference_impl       ┌──────────────────────────┐    ├── diagnosis  ∈ {STRONG, UNDERCONSTRAINED,
  ├── mutants  ────────────►  for each mutant:        │    │                  OVERCONSTRAINED, AMBIGUOUS}
  ├── specs                │    run_case(impl, spec)  │────►── mutation_score ∈ [0,1]
  │     ├── weak           │  scorer.score(results)   │    ├── surviving_mutants
  │     └── strong         └──────────────────────────┘    └── reference_passed
  └── input_strategy                                                │
                                                                    ▼
                            UNDERCONSTRAINED ⇒  suggest_stronger_spec(case, "weak", report)
                                                  → LLM-suggested missing properties
```

The four-way diagnosis is the load-bearing idea (see [`scorer.score`](../../specstress/scorer.py)):

| Reference passes? | Any bad mutant passed? | Diagnosis |
| --- | --- | --- |
| ✅ | ❌ | `STRONG` |
| ✅ | ✅ | `UNDERCONSTRAINED` |
| ❌ | ❌ | `OVERCONSTRAINED` |
| ❌ | ✅ | `AMBIGUOUS` |

`UNDERCONSTRAINED` is the case the LLM is asked to fix.

---

## 3. The migration: Anthropic → Tinker

### 3.1 Why migrate at all

The MVP shipped with `anthropic>=0.40` and Claude Sonnet 4.6 for the
"Suggest stronger spec" feature. Two motivations to swap:

1. **Single-provider story.** Running both Anthropic + Tinker would have meant two
   API keys to manage in Streamlit Cloud secrets, two SDKs in `requirements.txt`,
   and a UI provider-selector that adds complexity for marginal value.
2. **Use the Tinker credits.** The user has $150 in Tinker credits available; the
   Anthropic key was paid per-call out of pocket.

I asked once whether to keep Anthropic as a fallback or drop it entirely. User chose
**drop entirely**, which removed an entire dimension of branching from the UI and
test code.

### 3.2 Decision log — *full replacement* vs *parallel suggester*

Initially I proposed two scoped paths:

- **(A)** Keep both. Add a provider radio in the UI; two parallel modules.
- **(B)** Replace entirely.

(B) was chosen because:
- The LLM suggester is a single, well-isolated function (`specstress/llm.py` is
  ~135 lines). Replacing one provider is genuinely simpler than abstracting
  across two when there's no requirement to compare them at runtime.
- The Streamlit Cloud deployment story collapses to one secret to manage.
- We can always re-introduce Anthropic later — the `suggest_stronger_spec`
  signature is provider-agnostic, and the `client=` injection point survives.

### 3.3 Verification before writing code (avoiding the obvious trap)

The Tinker memory in the user's global `CLAUDE.md` showed this snippet:

```python
client = ServiceClient()
training_client = client.create_training_client(model="qwen3-30b-a3b", ...)
sampling_client = client.create_sampling_client(model="qwen3-30b-a3b")
response = sampling_client.sample(prompt="Hello", max_tokens=100)
```

That snippet turned out to be **inaccurate in three ways** for `tinker==0.22.0`:

1. There is no `create_training_client(model=...)` — the LoRA-only factory is
   `create_lora_training_client(base_model=...)`.
2. `create_sampling_client` takes `base_model=...`, not `model=...`.
3. `sample()` does **not** take a plain string prompt; it takes
   `prompt: ModelInput`, `num_samples: int`, `sampling_params: SamplingParams`,
   and returns a `Future` you must `.result()`.

I caught all three before writing any production code by introspecting the
installed package:

```python
>>> import tinker, inspect
>>> inspect.signature(tinker.ServiceClient.create_sampling_client)
(self, model_path: 'str | None' = None,
       base_model: 'str | None' = None,
       retry_config: 'RetryConfig | None' = None) -> 'SamplingClient'

>>> inspect.signature(tinker.SamplingClient.sample)
(self, prompt: 'types.ModelInput',
       num_samples: 'int',
       sampling_params: 'types.SamplingParams',
       ...) -> 'ConcurrentFuture[types.SampleResponse]'
```

The lesson is general: **for any unfamiliar SDK, the installed package is the
ground truth, not blog snippets or memory.** Three minutes of `dir()` and
`inspect.signature()` prevented a wasted hour debugging mismatched calls.

### 3.4 Model selection — *why Qwen3-30B-A3B-Instruct-2507*

I called `get_server_capabilities()` against the live Tinker API to list the
*actually-supported* base models rather than relying on the docs page (which is
JS-rendered and didn't yield model strings via plain `curl`):

```
Qwen/Qwen3-4B-Instruct-2507        (small, fast, instruct-tuned)
Qwen/Qwen3-8B / -Base              (no instruct variant in the list)
Qwen/Qwen3-30B-A3B                 (MoE, base)
Qwen/Qwen3-30B-A3B-Base            (base)
Qwen/Qwen3-30B-A3B-Instruct-2507   ← chosen
Qwen/Qwen3-32B                     (dense, more expensive)
Qwen/Qwen3-235B-A22B-Instruct-2507 (frontier, ~7x cost)
meta-llama/Llama-3.3-70B-Instruct  (dense, slower)
... plus DeepSeek, Kimi, Nemotron, gpt-oss
```

**Selection criteria, in priority order:**

1. **Instruction-following is the entire task.** The model has to read multi-part
   structured prose, follow a 3-section output spec, and emit a Python code block.
   → Eliminates `*-Base` and the smaller plain `Qwen3-8B` (no instruct variant
   in the supported list).
2. **Code quality matters.** The suggested spec has to compile and run. → Favors
   the larger Qwen3 variants over Llama-3.1-8B-Instruct.
3. **Cost.** Per the user's `CLAUDE.md`, the 30B-A3B MoE is the "best value"
   in Tinker's price card ($0.36/M training tokens; sampling is similar).
   Choosing the 235B model would 7× the cost for what is, structurally, a
   spec-rewriting task — not a frontier-reasoning task.
4. **Tinker support.** All listed models work; nothing to verify.

**Result: `Qwen/Qwen3-30B-A3B-Instruct-2507`.**

The full eval (5 cases, ~3 K input tokens + ~1 K output each) cost roughly
**$0.05 per run** — cheap enough to re-run after every prompt tweak.

### 3.5 Tinker adapter — the actual flow

Final implementation in [`specstress/llm.py`](../../specstress/llm.py):

```
ServiceClient()
    └── .create_sampling_client(base_model="Qwen/Qwen3-30B-A3B-Instruct-2507")
            └── .get_tokenizer()  # HuggingFace PreTrainedTokenizer
                    └── apply_chat_template([{role:system}, {role:user}],
                                            add_generation_prompt=True,
                                            tokenize=False)
                          → str
                    └── encode(str) → List[int]
            └── .sample(prompt=ModelInput.from_ints(ids),
                        num_samples=1,
                        sampling_params=SamplingParams(max_tokens=1500,
                                                       temperature=0.7))
                  → ConcurrentFuture[SampleResponse]
                    └── .result().sequences[0].tokens
                          └── tokenizer.decode(tokens, skip_special_tokens=True)
                                → str
```

Design notes:
- **Why use the chat template?** Qwen3-Instruct expects `<|im_start|>system\n…<|im_end|>\n<|im_start|>user\n…<|im_end|>\n<|im_start|>assistant\n` framing. Raw concatenation breaks instruction-following. The HF tokenizer ships the template, so we use it.
- **Why `skip_special_tokens=True`?** Otherwise the decoded text begins with `<|im_start|>assistant\n` boilerplate that has to be stripped manually.
- **Why expose `client=`?** Same injection seam as the previous Anthropic version
  — tests mock a `SamplingClient` and never touch the real API. CI cost = $0.

### 3.6 What changed in the codebase

| File | Change |
| --- | --- |
| `specstress/llm.py` | Anthropic client → Tinker `SamplingClient`; model default `claude-sonnet-4-6` → `Qwen/Qwen3-30B-A3B-Instruct-2507`; new flow: chat template → tokenize → `ModelInput.from_ints` → `sample().result()` → decode. `MissingAPIKeyError` message now references `TINKER_API_KEY`. |
| `tests/test_llm.py` | Mock shape replaced: `_fake_sampling_client` builds a tokenizer mock + a `SampleResponse`-shaped future. All four tests still cover: prompt assembly, injected-client return path, missing-key error, role-structured chat template. |
| `app.py` | UI copy: "Strengthen with Claude" → "Strengthen with Qwen3 (Tinker)". `ANTHROPIC_API_KEY` → `TINKER_API_KEY` in both env reads and Streamlit-secrets fallback. |
| `requirements.txt`, `pyproject.toml` | `anthropic>=0.40` removed; `tinker>=0.22` added. |
| `.streamlit/secrets.toml.example` | Key name updated. |
| `README.md` | Setup snippet updated. |
| `CLAUDE.md` (project) | Architecture section's LLM-suggester paragraph rewritten to describe the Tinker flow accurately. |

End-to-end smoke test against the real API (`Qwen/Qwen3-30B-A3B-Instruct-2507`,
sort/weak): **9.7 s round-trip, correct diagnosis, correct missing invariants
named (permutation, length, immutability).** First-call success.

---

## 4. The eval harness — methodology

### 4.1 Why a separate harness was necessary

The pre-existing `tests/test_llm.py` proves:

- the prompt was assembled correctly,
- the SDK is called with the expected shape,
- the returned text is forwarded to the caller.

What those tests **do not prove** is the only thing that actually matters in
production: *if I ship this suggestion to a developer, does it close the gap?*
An LLM that confidently outputs a plausible-looking but subtly wrong spec is worse
than no LLM at all — it gives false confidence.

So the eval harness round-trips the suggestion through the real SpecStress
pipeline:

```
weak spec (UNDERCONSTRAINED, score < 1.0)
        │
        ▼
suggest_stronger_spec(...)  → text
        │
        ▼
extract_spec_code(text)     → the Python code block
        │
        ▼
compile_spec_factory(code, original)  → new SpecFactory
        │
        ▼
stress_case(case with new factory)   → CaseReport
        │
        ▼
PASS  ⇔  diagnosis == STRONG  and  mutation_score == 1.0
```

### 4.2 Three subtle design decisions in the harness

**(a) Compiling the suggestion against the original spec's globals.**

The LLM tends to reuse symbols from the original spec — `_strategy`, `Counter`,
`re`, etc. — without re-importing them. Rather than asking the model to be
self-contained (which bloats the prompt), the harness execs the suggestion with
`namespace = dict(original_factory.__globals__)`. The suggested spec inherits
exactly the same module-level symbols the original had.

```python
namespace = dict(original_factory.__globals__)
exec(compile(code, "<suggested-spec>", "exec"), namespace)
```

**(b) Identifying the new factory in the post-exec namespace.**

After exec, the namespace contains both pre-existing functions and any new
ones the suggestion defined. The harness picks the new (or replaced) callable
that takes exactly one argument; if multiple match, it prefers one whose name
matches the original factory's name (the model almost always reuses
`weak_spec` as the name). This avoids fragile string parsing.

**(c) Treating ill-formed output as a graded failure, not a crash.**

If the LLM omits a code block, emits something that doesn't parse, or defines
no single-arg callable, the eval row is marked `after_diagnosis="ERROR"` with
the parsing error and the raw text preserved. This keeps the scoreboard honest
— if 5 % of the time the LLM doesn't produce parseable code, that should show
up as a failure rate, not a crash in the run script.

### 4.3 Unit testing the harness without spending API tokens

The cleanest part of the design: I use the project's **own hand-written
`strong_spec` source** as a "fake LLM suggestion" in unit tests:

```python
def test_evaluate_suggestion_round_trip_sort_strong():
    suggestion = _wrap_as_suggestion(inspect.getsource(SORT_STRONG))
    report = evaluate_suggestion(SORT_CASE, "weak", suggestion)
    assert report.diagnosis == "STRONG"
    assert report.mutation_score == 1.0
```

This proves the round-trip plumbing (extract → compile → stress) works end-to-end
without an API call — and incidentally cross-checks that the project's own
hand-written strong specs really do kill all mutants. **Eight harness tests, all
green; zero $ cost.**

---

## 5. Two new realistic cases

The pre-existing 3 cases (`sort`, `withdraw`, `sanitize`) are valuable as
demonstrations but are well-known textbook examples. To get evaluation signal
that maps to *production* spec-writing, I added two cases drawn from
high-incident-cost domains: financial calculation and authentication.

### 5.1 `examples/money/` — order total with tax & refunds

**Intent:** `total = sum(line_items) * (1 + tax_rate)`, quantized to cents with
banker's rounding. Negative line items represent refunds and must be honored.

**Weak spec — what a junior dev would write:**

```python
if rate > 0 and subtotal > 0:
    assert total >= subtotal, "tax does not appear to have been applied"
assert isinstance(total, Decimal)
```

That spec is plausible and would survive code review. It misses **everything
important** about money:

| Mutant | What it does wrong | Why weak spec misses it |
| --- | --- | --- |
| `float_arithmetic` | Drops to `float`, loses pennies | Most outputs still happen to round to the same cents |
| `double_tax` | Applies tax twice | Total is bigger than subtotal — weak spec is happy |
| `half_down_rounding` | `ROUND_HALF_DOWN` instead of banker's | Differs by ≤ 1 cent on exact-half cases; weak spec doesn't check |
| `drops_refunds` | Silently ignores negative lines | Drops only increase total → still ≥ subtotal |

**Strong spec** (hand-written ground truth):

```python
expected = (subtotal * (Decimal("1") + rate)).quantize(CENT, rounding=ROUND_HALF_EVEN)
assert total == expected
```

Plus four `@example(...)` annotations forcing Hypothesis to hit exact half-cent
edges (`[0.30] @ 0.0250`, etc.) — without these, random sampling rarely
generates the half-cent inputs that distinguish banker's rounding from
half-down. Test:
[`tests/test_examples_money.py`](../../tests/test_examples_money.py) — passes.

### 5.2 `examples/jwt/` — HS256 token verification

**Intent:** Verify an HS256 JWT against a shared secret. Reject if: signature
invalid, `alg != HS256`, expired (`now >= exp`), not yet active
(`now < nbf`), or `aud` not in allowed set.

**Weak spec — what a junior dev wires together first:**

```python
if not _good_sig(token, SECRET):
    assert result is False, "verify must reject bad signatures"
```

Sig-only. Mutants kept:

| Mutant | What it does wrong | Why weak spec misses it |
| --- | --- | --- |
| `ignores_exp` | Skips `exp` check | Spec doesn't assert on `exp` |
| `accepts_alg_none` | Classic CVE-pattern alg=none bypass | Spec doesn't assert on `alg` |
| `ignores_aud` | Skips audience validation | Spec doesn't assert on `aud` |
| `ignores_nbf` | Skips not-before check | Spec doesn't assert on `nbf` |

The Hypothesis strategy (`_token_and_now`) generates HS256 tokens, alg=none
tokens, alg=HS512 tokens, signatures signed with the wrong key (tampered), and a
spread of `now` values around the `exp`/`nbf` boundaries. The strong spec
recomputes the truth-value independently:
[`tests/test_examples_jwt.py`](../../tests/test_examples_jwt.py) — passes.

### 5.3 Registry & sanity tests

Registered both in [`examples/__init__.py`](../../examples/__init__.py); updated
[`tests/test_examples_registry.py`](../../tests/test_examples_registry.py) to
expect five cases. **Full pytest suite: 37 passed, 0 failed.**

---

## 6. Evaluation results

### 6.1 Round 1 — existing toys only

Run: `2026-05-23 19:04 UTC`, artifacts at
`eval-results/20260523T190429Z/`. **1 / 3 PASS.**

| Case | Before | After | Score | Ref passes | Result |
| --- | --- | --- | --- | --- | --- |
| `sort` | UNDERCONSTRAINED | UNDERCONSTRAINED | 0.80 | yes | **FAIL** |
| `withdraw` | UNDERCONSTRAINED | STRONG | 1.00 | yes | **PASS** |
| `sanitize` | UNDERCONSTRAINED | OVERCONSTRAINED | 1.00 | no | **FAIL** |

### 6.2 Round 2 — all five cases

Run: `2026-05-23 19:12 UTC`, artifacts at
`eval-results/20260523T191216Z/`. **2 / 5 PASS.**

| Case | Before | After | Score | Ref passes | Result |
| --- | --- | --- | --- | --- | --- |
| `sort` | UNDERCONSTRAINED | STRONG | 1.00 | yes | **PASS** |
| `withdraw` | UNDERCONSTRAINED | STRONG | 1.00 | yes | **PASS** |
| `sanitize` | UNDERCONSTRAINED | OVERCONSTRAINED | 1.00 | no | **FAIL** |
| `money` | UNDERCONSTRAINED | UNDERCONSTRAINED | 0.50 | yes | **FAIL** |
| `jwt` | UNDERCONSTRAINED | UNDERCONSTRAINED | 0.25 | yes | **FAIL** |

Total wall-clock: **39 s for 5 cases (~8 s each)**. Estimated API spend per run:
**< $0.05**.

### 6.3 Cross-run note

`sort` flipped between FAIL (round 1) and PASS (round 2) with no change to
prompt, model, or strategy — just sampling variance at `temperature=0.7`. This
matters: **any single run is noisy**. The harness is cheap to run; future work
should aggregate over several runs per case before drawing conclusions.

---

## 7. Failure analysis — three patterns

I read every failing artifact in full. The failures cluster into three
distinct failure modes, each of which suggests a different remedy.

### Pattern A — *correct diagnosis, broken code* (sort, round 1)

The model wrote, in prose:

> "Assert that the input list is unchanged after the call, preventing in-place mutation"

…and then implemented it as:

```python
xs_copy = list(xs)            # preserve original input
ys = impl(list(xs))           # defensive copy so impls don't leak
...
assert xs == xs_copy           # input not mutated   ← tautology
```

The check is structurally impossible to fail: `impl` was called with a fresh copy
(`list(xs)`), so `xs` itself cannot have been mutated by `impl`. The model
**carried over the defensive-copy pattern from the original weak spec without
realising the immutability check has to inspect the same list the impl actually
received**. Diagnosis: correct. Code: subtly wrong.

→ Captured exactly: 1 of 5 mutants survived (`mutates_input`), score 0.80.

### Pattern B — *over-correction* (sanitize, both rounds)

The model added (paraphrased):

```python
assert out == html or any(c in "<>" for c in out)
```

This says "the output must contain `<` or `>`, unless it equals the input
unchanged". The reference impl correctly strips `<script>…</script>` from an
input like `"<SCRIPT>alert(1)</SCRIPT>"` and emits `""` — no angle brackets, not
equal to input → **the reference fails its own spec.**

The model successfully killed all four mutants (score 1.0), but in doing so it
constrained behavior that the intent does not require. Diagnosis flipped from
`UNDERCONSTRAINED` to `OVERCONSTRAINED` — a different failure mode, equally
unshippable.

### Pattern C — *structural misunderstanding* (jwt, round 2)

The model added time-bound checks like:

```python
if "exp" in token:
    exp = token.split(".")[1]
    exp_val = json.loads(_b64u_decode(exp))["exp"]
    if now >= exp_val:
        assert result is False, "verify must reject expired tokens"
```

The guard `if "exp" in token` does substring-matching on the **base64-encoded**
token. A token's payload `{"exp":1500,...}` base64-encodes to
`eyJleHAiOjE1MDAsIm5iZiI6...` — the literal three-letter substring `"exp"`
**does not appear** in the encoded form. The guard is virtually always False, so
the assertion never fires, and the four mutants pass through. Score: 0.25
(1 / 4 mutants caught — probably variance).

This is the most instructive failure: the model **knows what to check
semantically** (the prose-level diagnosis names `exp`, `nbf`, `aud`, `alg=none`
correctly) but **does not reliably reason about encoding boundaries** when
translating that into code. A human writing this would unconditionally `_b64u_decode`
the payload section once at the top of the test, then check the *decoded*
claims directly.

### Pattern D — *missing edge-case sampling* (money, round 2)

The model's spec **was** correct in shape:

```python
exact = subtotal * (Decimal("1") + rate)
expected = exact.quantize(CENT, rounding=ROUND_HALF_EVEN)
assert total == expected
```

But Hypothesis with random sampling rarely produces the exact-half-cent inputs
that distinguish `ROUND_HALF_EVEN` from `ROUND_HALF_DOWN`. The hand-written
strong spec (sec. 5.1) needed four `@example(...)` annotations to reliably
catch the `half_down_rounding` mutant. The LLM didn't add any — so
`half_down_rounding` survives in practice, even though the cent-exact assertion
would catch it on the right input.

This is a tooling-aware failure: the model writes a spec that is *correct against
an oracle* but **does not understand that property-based testing requires
forcing edge cases**. A prompt addition like "*if your invariant only fires on
specific edge inputs, add `@example(...)` annotations*" would likely fix this.

### Summary of patterns and their cures

| Pattern | Example | Diagnosis quality | Code quality | Cure |
| --- | --- | --- | --- | --- |
| A: Diagnosis right, code subtly wrong | sort | ✅ | ❌ | Self-critique loop: re-run the spec, feed the surviving mutant back |
| B: Over-correction | sanitize | partially ✅ | over-eager | Stronger guardrail in system prompt about preserving reference behavior |
| C: Structural misunderstanding | jwt | ✅ in prose | ❌ encoded-boundary errors | Few-shot examples showing decode-once-then-inspect patterns |
| D: Missing edge-case sampling | money | ✅ | ✅ shape, ❌ coverage | Add `@example` instruction; or run Hypothesis with higher `max_examples` |

---

## 8. Honest limitations

- **40 % round-trip success is too low to ship as an autonomous "fix this" button.**
  The current UI does the right thing: it shows the suggestion as a draft for a
  human to review, and the human still has to read it. The eval harness is what
  tells us whether prompt or model changes move the number.
- **High variance per run.** `sort` flipped between rounds with no prompt change.
  Real benchmarking needs n≥3 runs per case before declaring a regression or
  improvement.
- **Five cases is a small sample.** Three "real-world" patterns (Patterns A–D)
  are visible but more cases (maybe 10–20) would make the failure-mode taxonomy
  statistically meaningful.
- **No comparison against the previous (Anthropic) provider.** I removed the
  Anthropic path before running this benchmark. The honest answer to "is Qwen3
  better, worse, or the same as Claude Sonnet 4.6 at this task?" is **I don't know
  yet** — re-introducing a comparison branch is one of the easiest follow-ups.
- **Costs are tiny but real.** ~$0.01 per case, ~$0.05 per full eval run.
  CI shouldn't run the real eval on every push.

---

## 9. What's next (in order of cost-to-value)

1. **Self-critique loop.** When the round-trip fails, automatically send the
   surviving mutant's name and source back to the model and ask "your previous
   spec did not kill `<mutant>` — revise". This is one extra API call per
   failure and likely closes Pattern A (sort/defensive-copy) immediately.
2. **Prompt hardening.** Add to the system prompt:
   - "If the original spec calls `impl(copy)`, the immutability check must
     compare against the copy, not the original."
   - "Property-based tests with random sampling will miss exact-half-cent or
     other knife-edge inputs unless you add `@example(...)` annotations."
   - "Inspect decoded JSON claims, not the encoded token string, when reasoning
     about JWT payloads."
   Each rule maps to a real failure mode in the artifacts.
3. **Larger benchmark.** Grow `examples/` to 10–15 cases covering: pagination,
   date-range overlap, slug generation, idempotency keys, password strength,
   retry-with-backoff, dedup-with-hash, URL normalization, CSV parsing,
   permission scoping.
4. **Re-introduce comparison.** Optional `--model` flag on the eval script to
   benchmark Qwen3-30B vs Qwen3-235B vs Llama-3.3-70B-Instruct vs Claude.
   Numbers > intuition.
5. **Fine-tuning** — the original Phase-2 path. With the eval harness in place,
   we can now measure whether fine-tuning Qwen3 on (weak, ref, mutants → strong)
   pairs actually beats the prompt-engineered baseline. This was previously
   deferred; now it has a numerical baseline to beat.

---

## 10. File inventory

### Added

| File | Purpose |
| --- | --- |
| `specstress/eval.py` | Round-trip evaluation harness: `extract_spec_code`, `compile_spec_factory`, `evaluate_suggestion`, `run_eval_one`, `EvalRow`. |
| `tests/test_eval.py` | 8 unit tests covering parsing, compilation, end-to-end round-trip using project's own strong specs as ground truth. No API cost. |
| `scripts/run_eval.py` | CLI: iterate REGISTRY, call Tinker, write `eval-results/<UTC>/scoreboard.md` plus one artifact per case. |
| `examples/money/case.py` + `__init__.py` | Order-total with refunds + tax + banker's rounding. 4 mutants (float arithmetic, double tax, half-down rounding, drops refunds). |
| `examples/jwt/case.py` + `__init__.py` | HS256 verification with exp/nbf/aud/alg checks. 4 mutants (ignores exp/aud/nbf, accepts alg=none). |
| `tests/test_examples_money.py`, `tests/test_examples_jwt.py` | Conventional weak-is-underconstrained / strong-kills-all-mutants tests. |
| `eval-results/20260523T190429Z/` | Round-1 artifacts (3 cases). |
| `eval-results/20260523T191216Z/` | Round-2 artifacts (all 5 cases). |
| `docs/hackathon/2026-05-23-tinker-migration-and-eval.md` | This document. |

### Modified

| File | Change |
| --- | --- |
| `specstress/llm.py` | Anthropic → Tinker; chat-template flow; `TINKER_API_KEY`. |
| `tests/test_llm.py` | Mock shape replaced for Tinker `SamplingClient`. |
| `app.py` | UI copy + env var swap. |
| `requirements.txt`, `pyproject.toml` | `anthropic>=0.40` → `tinker>=0.22`. |
| `.streamlit/secrets.toml.example` | Key name. |
| `README.md` | Setup snippet + architecture line. |
| `CLAUDE.md` (project) | LLM-suggester architecture paragraph rewritten. |
| `examples/__init__.py` | Registry now includes `money` and `jwt`. |
| `tests/test_examples_registry.py` | Expects 5 cases. |

---

## 11. Reproducing this work

### Setup

```bash
git clone <repo>
cd specstress
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q                      # 37 passed
```

### Run the unit-test eval harness (no API cost)

```bash
pytest tests/test_eval.py -v   # 8 passed
```

### Run the real eval against the live Tinker API

```bash
export TINKER_API_KEY="tml-..."
python scripts/run_eval.py                    # all 5 cases
python scripts/run_eval.py --cases money jwt  # subset
```

Results are written to `eval-results/<UTC-timestamp>/`:
- `scoreboard.md` — the headline table
- `<case>.md` per case — full LLM response + parsed result

### Inspect an existing run

```bash
cat eval-results/20260523T191216Z/scoreboard.md
cat eval-results/20260523T191216Z/jwt.md      # see the substring-on-base64 bug verbatim
```

---

## 12. Acknowledgements

- **Tinker** ([Thinking Machines Lab](https://thinkingmachines.ai/tinker/)) for the
  managed Qwen3 inference and the introspectable Python SDK.
- **Hypothesis** for the property-based testing framework that makes
  mutation-style stress-testing tractable in pure Python.
- **The prior MVP** documented in [`docs/plans/2026-05-22-specstress-mvp.md`](../plans/2026-05-22-specstress-mvp.md)
  for establishing the `SpecCase`/`stress_case` architecture this work builds on.
