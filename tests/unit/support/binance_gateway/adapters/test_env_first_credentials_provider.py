"""`EPIC-021B` — precedence: env var > file > none. Closes `BUG-080`'s
credentials-never-reach-anything half for the resolution side.
`EPIC-027G` — the env var pair is looked up per `TradingVenue`, so a
Futures Testnet key can never leak into a Spot Testnet resolution."""

from __future__ import annotations

import os

from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    FUTURES_ENV_API_KEY,
    FUTURES_ENV_API_SECRET,
    SPOT_ENV_API_KEY,
    SPOT_ENV_API_SECRET,
    EnvFirstCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.secrets_file_source import (
    SecretsFileSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def _provider(
    tmp_path, trading_venue: TradingVenue = TradingVenue.FUTURES_TESTNET
) -> EnvFirstCredentialsProvider:
    return EnvFirstCredentialsProvider(
        SecretsFileSource(str(tmp_path / "secrets.local.json")), trading_venue
    )


def _clear_all_venue_env_vars(monkeypatch) -> None:
    for name in (
        FUTURES_ENV_API_KEY,
        FUTURES_ENV_API_SECRET,
        SPOT_ENV_API_KEY,
        SPOT_ENV_API_SECRET,
    ):
        monkeypatch.delenv(name, raising=False)


def test_resolves_to_none_when_nothing_is_configured(tmp_path):
    resolution = _provider(tmp_path).resolve()

    assert resolution.credentials is None
    assert resolution.source is CredentialsSource.NONE


def test_resolves_from_the_file_when_no_env_var_is_set(tmp_path, monkeypatch):
    _clear_all_venue_env_vars(monkeypatch)
    provider = _provider(tmp_path)
    provider.save_to_file("file-key", "file-secret")

    resolution = provider.resolve()

    assert resolution.source is CredentialsSource.FILE
    assert resolution.credentials.api_key == "file-key"
    assert resolution.credentials.api_secret == "file-secret"  # noqa: S105 - test fixture data


def test_an_env_var_wins_over_a_configured_file(tmp_path, monkeypatch):
    """`EPIC-021B` §2.1 — env must win outright, so a machine already
    configured correctly is never silently overridden by a stale file."""
    provider = _provider(tmp_path)
    provider.save_to_file("file-key", "file-secret")
    monkeypatch.setenv(FUTURES_ENV_API_KEY, "env-key")
    monkeypatch.setenv(FUTURES_ENV_API_SECRET, "env-secret")

    resolution = provider.resolve()

    assert resolution.source is CredentialsSource.ENV
    assert resolution.credentials.api_key == "env-key"
    assert resolution.credentials.api_secret == "env-secret"  # noqa: S105 - test fixture data


def test_a_partial_env_var_pair_falls_back_to_the_file_rather_than_half_resolving(
    tmp_path, monkeypatch
):
    """Only the key set, secret missing — must not resolve to a credentials
    object with an empty secret; falls through to the next source instead."""
    provider = _provider(tmp_path)
    provider.save_to_file("file-key", "file-secret")
    monkeypatch.setenv(FUTURES_ENV_API_KEY, "env-key")
    monkeypatch.delenv(FUTURES_ENV_API_SECRET, raising=False)

    resolution = provider.resolve()

    assert resolution.source is CredentialsSource.FILE


def test_a_malformed_secrets_file_degrades_to_none_not_a_crash(tmp_path, monkeypatch):
    _clear_all_venue_env_vars(monkeypatch)
    secrets_path = tmp_path / "secrets.local.json"
    secrets_path.write_text("{not valid json", encoding="utf-8")
    provider = EnvFirstCredentialsProvider(
        SecretsFileSource(str(secrets_path)), TradingVenue.FUTURES_TESTNET
    )

    resolution = provider.resolve()

    assert resolution.source is CredentialsSource.NONE
    assert resolution.credentials is None


def test_save_to_file_does_not_touch_the_environment(tmp_path, monkeypatch):
    """`save_to_file` only ever writes the file fallback — it must never
    reach into `os.environ`, which would be a much stranger and more
    surprising side effect than "the write did nothing while ENV wins"."""
    _clear_all_venue_env_vars(monkeypatch)
    provider = _provider(tmp_path)

    provider.save_to_file("file-key", "file-secret")

    assert FUTURES_ENV_API_KEY not in os.environ
    assert FUTURES_ENV_API_SECRET not in os.environ


def test_spot_testnet_reads_its_own_env_var_pair(tmp_path, monkeypatch):
    """`EPIC-027G` — Spot Testnet resolves from its own env vars, not the
    Futures Testnet pair."""
    _clear_all_venue_env_vars(monkeypatch)
    monkeypatch.setenv(SPOT_ENV_API_KEY, "spot-env-key")
    monkeypatch.setenv(SPOT_ENV_API_SECRET, "spot-env-secret")
    provider = _provider(tmp_path, TradingVenue.SPOT_TESTNET)

    resolution = provider.resolve()

    assert resolution.source is CredentialsSource.ENV
    assert resolution.credentials.api_key == "spot-env-key"
    assert resolution.credentials.api_secret == "spot-env-secret"  # noqa: S105 - test fixture data


def test_a_futures_testnet_env_var_never_resolves_for_spot_testnet(
    tmp_path, monkeypatch
):
    """`EPIC-027G` — the whole point of venue isolation: a Futures Testnet
    key sitting in the environment must never be picked up while resolving
    for Spot Testnet."""
    _clear_all_venue_env_vars(monkeypatch)
    monkeypatch.setenv(FUTURES_ENV_API_KEY, "futures-env-key")
    monkeypatch.setenv(FUTURES_ENV_API_SECRET, "futures-env-secret")
    provider = _provider(tmp_path, TradingVenue.SPOT_TESTNET)

    resolution = provider.resolve()

    assert resolution.source is not CredentialsSource.ENV


def test_an_env_var_with_a_trailing_newline_is_stripped_before_use(
    tmp_path, monkeypatch
):
    """`BUG-137` — a value pasted into a shell (PowerShell `$env:X="…"` with
    an accidental Enter before the closing quote, a `.env` file's trailing
    line ending) commonly carries a trailing `\\n`. Embedded verbatim in the
    `X-MBX-APIKEY` HTTP header, that newline makes `requests` reject the
    header outright — surfacing as a generic, misleading `NETWORK` failure
    (`spot_account_reader._classify_exception`'s catch-all) instead of
    naming the actual credentials problem. `resolve()` must strip
    surrounding whitespace from both env var values before they ever reach
    a signed request."""
    _clear_all_venue_env_vars(monkeypatch)
    monkeypatch.setenv(FUTURES_ENV_API_KEY, "env-key\n")
    monkeypatch.setenv(FUTURES_ENV_API_SECRET, " env-secret \t\n")
    provider = _provider(tmp_path)

    resolution = provider.resolve()

    assert resolution.source is CredentialsSource.ENV
    assert resolution.credentials.api_key == "env-key"
    assert resolution.credentials.api_secret == "env-secret"  # noqa: S105 - test fixture data


def test_an_env_var_that_is_only_whitespace_falls_back_to_the_file(
    tmp_path, monkeypatch
):
    """A key set to whitespace-only (a shell variable exported but emptied)
    must not resolve to an empty-string credential — same "no half
    resolution" contract as the partial-pair case above."""
    provider = _provider(tmp_path)
    provider.save_to_file("file-key", "file-secret")
    monkeypatch.setenv(FUTURES_ENV_API_KEY, "   ")
    monkeypatch.setenv(FUTURES_ENV_API_SECRET, "env-secret")

    resolution = provider.resolve()

    assert resolution.source is CredentialsSource.FILE


def test_disabled_venue_has_no_env_vars_and_falls_back_to_the_file(
    tmp_path, monkeypatch
):
    """`EPIC-027G` — `DISABLED` has no env var pair of its own; `resolve()`
    must degrade to the file fallback rather than crash on a missing
    mapping entry."""
    _clear_all_venue_env_vars(monkeypatch)
    provider = _provider(tmp_path, TradingVenue.DISABLED)
    provider.save_to_file("file-key", "file-secret")

    resolution = provider.resolve()

    assert resolution.source is CredentialsSource.FILE
