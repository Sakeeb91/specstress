# Eval artifact — `jwt`

- Before: **UNDERCONSTRAINED** (score 0.25)
- After:  **UNDERCONSTRAINED** (score 0.25)
- Reference passes: True
- Success (after == STRONG, score == 1.0): **False**

## Raw model output

1. The current spec is underconstrained because it only checks that invalid signatures are rejected, but fails to enforce that valid tokens with expired `exp`, future `nbf`, or invalid `aud` are rejected — the spec lacks explicit invariants for these critical JWT claims. This allows mutants that ignore `exp`, `nbf`, or `aud` to pass, despite violating the security intent.

2. - Add an assertion that a token with a valid signature, `HS256` algorithm, and `exp` set to a time in the past (i.e., `now >= exp`) must be rejected.  
   - Add an assertion that a token with a valid signature, `HS256` algorithm, and `nbf` set to a time in the future (i.e., `now < nbf`) must be rejected.  
   - Add an assertion that a token with a valid signature, `HS256` algorithm, and `aud` set to a value not in `allowed_aud` must be rejected.  
   - Add an assertion that a token with `alg` set to `"none"` must be rejected, even if the signature is valid (to prevent algorithm confusion attacks).

3. ```python
def weak_spec(impl):
    """Naive spec: 'a bad signature must be rejected'.
    Says nothing about exp, nbf, aud, or alg=none."""

    @settings(max_examples=200, deadline=None)
    @given(_strategy)
    def test(args):
        token, now = args
        result = impl(token, SECRET, now, ALLOWED_AUD)
        assert isinstance(result, bool)
        if not _good_sig(token, SECRET):
            assert result is False, "verify must reject bad signatures"

        # Additional invariants to kill surviving mutants
        # Check that expired tokens (exp <= now) are rejected
        if "exp" in token:
            exp = token.split(".")[1]
            exp_val = json.loads(_b64u_decode(exp))["exp"]
            if now >= exp_val:
                assert result is False, "verify must reject expired tokens"

        # Check that tokens with future nbf are rejected
        if "nbf" in token:
            nbf = token.split(".")[1]
            nbf_val = json.loads(_b64u_decode(nbf))["nbf"]
            if now < nbf_val:
                assert result is False, "verify must reject tokens with future nbf"

        # Check that tokens with invalid aud are rejected
        if "aud" in token:
            aud = token.split(".")[1]
            aud_val = json.loads(_b64u_decode(aud))["aud"]
            if aud_val not in ALLOWED_AUD:
                assert result is False, "verify must reject tokens with invalid aud"

        # Check that alg=none is rejected
        if "alg" in token:
            alg = token.split(".")[0]
            alg_val = json.loads(_b64u_decode(alg))["alg"]
            if alg_val == "none":
                assert result is False, "verify must reject tokens with alg=none"

    return test
```