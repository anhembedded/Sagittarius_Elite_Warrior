"""`EPIC-021B` — `ExchangeCredentials` must never leak the real secret
through any of the paths that read `repr()`/`str()` automatically: an
unhandled exception's traceback, `logger.debug(f"{obj}")`, and a pytest
assertion diff all call `repr()` without anyone asking for it."""

from __future__ import annotations

import dataclasses

import pytest
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_credentials import (
    ExchangeCredentials,
)

_API_KEY = "Bx7fABCDEFGH9dQ2"
_API_SECRET = "sEcReT-do-not-print-me-anywhere"  # noqa: S105 - test fixture data


def _credentials() -> ExchangeCredentials:
    return ExchangeCredentials(api_key=_API_KEY, api_secret=_API_SECRET)


def test_repr_never_contains_the_real_secret_and_only_partially_masks_the_key():
    text = repr(_credentials())

    assert _API_SECRET not in text
    assert _API_KEY not in text
    assert "***" in text
    # Partial masking is deliberate (not full redaction of both fields): a
    # user needs to tell two testnet accounts' keys apart without the full
    # value ever reaching a log line.
    assert _API_KEY[:4] in text
    assert _API_KEY[-4:] in text


def test_str_matches_repr():
    creds = _credentials()
    assert str(creds) == repr(creds)


def test_fstring_interpolation_never_contains_the_real_secret():
    creds = _credentials()
    text = f"{creds}"

    assert _API_SECRET not in text
    assert _API_KEY not in text


def test_an_exception_carrying_the_object_does_not_leak_it_in_the_traceback():
    creds = _credentials()

    with pytest.raises(RuntimeError) as excinfo:
        raise RuntimeError(f"boom while holding {creds!r}")

    rendered = str(excinfo.value)
    assert _API_SECRET not in rendered
    assert _API_KEY not in rendered


def test_a_short_key_masks_fully_rather_than_reversing_the_mask():
    """A key shorter than the visible prefix+suffix would, unmasked, show
    the whole thing through the two "visible" slices meeting in the middle —
    must fall back to full masking instead."""
    short = ExchangeCredentials(api_key="ab", api_secret="cd")

    assert "ab" not in repr(short)
    assert "***" in repr(short)


def test_mutation_verify_removing_the_repr_override_would_leak_the_secret():
    """Proves this test class actually catches the regression it exists for
    — a plain `@dataclass` (the class as it would be with the `__repr__`/
    `__str__` overrides removed) DOES print every field verbatim, so the
    tests above are not vacuously passing."""

    @dataclasses.dataclass(frozen=True)
    class UnredactedCredentials:
        api_key: str
        api_secret: str

    leaky = UnredactedCredentials(api_key=_API_KEY, api_secret=_API_SECRET)
    assert _API_SECRET in repr(leaky)
