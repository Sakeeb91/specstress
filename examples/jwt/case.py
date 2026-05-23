from __future__ import annotations

import base64
import hashlib
import hmac
import json

from hypothesis import given, settings, strategies as st

from specstress.models import SpecCase


SECRET = b"hackathon-shared-secret-key"
ALLOWED_AUD = frozenset({"api", "web"})


def _b64u_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64u_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(header: dict, payload: dict, key: bytes, *, alg: str = "HS256") -> str:
    h64 = _b64u_encode(json.dumps(header, sort_keys=True).encode())
    p64 = _b64u_encode(json.dumps(payload, sort_keys=True).encode())
    if alg == "none":
        return f"{h64}.{p64}."
    sig = hmac.new(key, f"{h64}.{p64}".encode(), hashlib.sha256).digest()
    return f"{h64}.{p64}.{_b64u_encode(sig)}"


def _good_sig(token: str, key: bytes) -> bool:
    try:
        h64, p64, s64 = token.split(".")
    except ValueError:
        return False
    if not s64:
        return False
    expected = hmac.new(key, f"{h64}.{p64}".encode(), hashlib.sha256).digest()
    try:
        actual = _b64u_decode(s64)
    except Exception:
        return False
    return hmac.compare_digest(expected, actual)


# --- Implementations -----------------------------------------------------

def correct_verify(token, key, now, allowed_aud):
    try:
        h64, p64, s64 = token.split(".")
        header = json.loads(_b64u_decode(h64))
        payload = json.loads(_b64u_decode(p64))
    except Exception:
        return False
    if header.get("alg") != "HS256":
        return False
    if not _good_sig(token, key):
        return False
    if "exp" in payload and now >= payload["exp"]:
        return False
    if "nbf" in payload and now < payload["nbf"]:
        return False
    if "aud" in payload and payload["aud"] not in allowed_aud:
        return False
    return True


def ignores_exp(token, key, now, allowed_aud):
    try:
        h64, p64, s64 = token.split(".")
        header = json.loads(_b64u_decode(h64))
        payload = json.loads(_b64u_decode(p64))
    except Exception:
        return False
    if header.get("alg") != "HS256":
        return False
    if not _good_sig(token, key):
        return False
    if "nbf" in payload and now < payload["nbf"]:
        return False
    if "aud" in payload and payload["aud"] not in allowed_aud:
        return False
    return True


def accepts_alg_none(token, key, now, allowed_aud):
    """Classic JWT vuln: accepts alg=none with empty signature."""
    try:
        h64, p64, s64 = token.split(".")
        header = json.loads(_b64u_decode(h64))
        payload = json.loads(_b64u_decode(p64))
    except Exception:
        return False
    alg = header.get("alg")
    if alg == "none":
        pass  # accept empty sig
    elif alg == "HS256":
        if not _good_sig(token, key):
            return False
    else:
        return False
    if "exp" in payload and now >= payload["exp"]:
        return False
    if "nbf" in payload and now < payload["nbf"]:
        return False
    if "aud" in payload and payload["aud"] not in allowed_aud:
        return False
    return True


def ignores_aud(token, key, now, allowed_aud):
    try:
        h64, p64, s64 = token.split(".")
        header = json.loads(_b64u_decode(h64))
        payload = json.loads(_b64u_decode(p64))
    except Exception:
        return False
    if header.get("alg") != "HS256":
        return False
    if not _good_sig(token, key):
        return False
    if "exp" in payload and now >= payload["exp"]:
        return False
    if "nbf" in payload and now < payload["nbf"]:
        return False
    return True


def ignores_nbf(token, key, now, allowed_aud):
    try:
        h64, p64, s64 = token.split(".")
        header = json.loads(_b64u_decode(h64))
        payload = json.loads(_b64u_decode(p64))
    except Exception:
        return False
    if header.get("alg") != "HS256":
        return False
    if not _good_sig(token, key):
        return False
    if "exp" in payload and now >= payload["exp"]:
        return False
    if "aud" in payload and payload["aud"] not in allowed_aud:
        return False
    return True


# --- Strategy ------------------------------------------------------------

@st.composite
def _token_and_now(draw):
    alg = draw(st.sampled_from(["HS256", "HS256", "HS256", "none", "HS512"]))
    exp = draw(st.integers(min_value=1000, max_value=2000))
    nbf = draw(st.integers(min_value=500, max_value=999))
    aud = draw(st.sampled_from(["api", "web", "mobile", "evil"]))
    payload = {"sub": "u1", "exp": exp, "nbf": nbf, "aud": aud}
    header = {"alg": alg, "typ": "JWT"}
    tamper = draw(st.booleans())
    if tamper and alg == "HS256":
        token = _sign(header, payload, b"wrong-key")
    else:
        token = _sign(header, payload, SECRET, alg=alg)
    now = draw(st.integers(min_value=0, max_value=3000))
    return token, now


_strategy = _token_and_now()


# --- Specs ---------------------------------------------------------------

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

    return test


def strong_spec(impl):
    """Independently recompute the truthy decision and compare."""

    @settings(max_examples=300, deadline=None)
    @given(_strategy)
    def test(args):
        token, now = args
        result = impl(token, SECRET, now, ALLOWED_AUD)

        try:
            h64, p64, _ = token.split(".")
            header = json.loads(_b64u_decode(h64))
            payload = json.loads(_b64u_decode(p64))
        except Exception:
            assert result is False
            return

        good_sig = _good_sig(token, SECRET)
        good_alg = header.get("alg") == "HS256"
        not_expired = "exp" not in payload or now < payload["exp"]
        active = "nbf" not in payload or now >= payload["nbf"]
        good_aud = "aud" not in payload or payload["aud"] in ALLOWED_AUD
        expected = good_sig and good_alg and not_expired and active and good_aud
        assert result is expected, (
            f"result={result} expected={expected} "
            f"sig={good_sig} alg={good_alg} exp_ok={not_expired} "
            f"nbf_ok={active} aud_ok={good_aud}"
        )

    return test


# --- Case ----------------------------------------------------------------

CASE = SpecCase(
    name="jwt",
    intent=(
        "Verify an HS256 JWT against a shared secret. Reject if: signature is "
        "invalid, alg is not HS256, `exp` has passed (now >= exp), `nbf` is in "
        "the future (now < nbf), or `aud` is not in the allowed set."
    ),
    input_strategy=_strategy,
    reference_impl=correct_verify,
    specs={"weak": weak_spec, "strong": strong_spec},
    mutants={
        "correct_verify": correct_verify,
        "ignores_exp": ignores_exp,
        "accepts_alg_none": accepts_alg_none,
        "ignores_aud": ignores_aud,
        "ignores_nbf": ignores_nbf,
    },
)
