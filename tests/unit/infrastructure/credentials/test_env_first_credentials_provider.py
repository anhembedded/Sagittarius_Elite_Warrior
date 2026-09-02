"""`EPIC-021B` — precedence: env var > file > none. Closes `BUG-080`'s
credentials-never-reach-anything half for the resolution side."""

from __future__ import annotations

import os

from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    CredentialsSource,
)
from Sagittarius_Elite_Warrior.src.infrastructure.credentials.env_first_credentials_provider import (
    ENV_API_KEY,
    ENV_API_SECRET,
    EnvFirstCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.infrastructure.credentials.secrets_file_source import (
    SecretsFileSource,
)


def _provider(tmp_path) -> EnvFirstCredentialsProvider:
    return EnvFirstCredentialsProvider(
        SecretsFileSource(str(tmp_path / "secrets.local.json"))
    )


def test_resolves_to_none_when_nothing_is_configured(tmp_path):
    resolution = _provider(tmp_path).resolve()

    assert resolution.credentials is None
    assert resolution.source is CredentialsSource.NONE


def test_resolves_from_the_file_when_no_env_var_is_set(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_API_KEY, raising=False)
    monkeypatch.delenv(ENV_API_SECRET, raising=False)
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
    monkeypatch.setenv(ENV_API_KEY, "env-key")
    monkeypatch.setenv(ENV_API_SECRET, "env-secret")

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
    monkeypatch.setenv(ENV_API_KEY, "env-key")
    monkeypatch.delenv(ENV_API_SECRET, raising=False)

    resolution = provider.resolve()

    assert resolution.source is CredentialsSource.FILE


def test_a_malformed_secrets_file_degrades_to_none_not_a_crash(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_API_KEY, raising=False)
    monkeypatch.delenv(ENV_API_SECRET, raising=False)
    secrets_path = tmp_path / "secrets.local.json"
    secrets_path.write_text("{not valid json", encoding="utf-8")
    provider = EnvFirstCredentialsProvider(SecretsFileSource(str(secrets_path)))

    resolution = provider.resolve()

    assert resolution.source is CredentialsSource.NONE
    assert resolution.credentials is None


def test_save_to_file_does_not_touch_the_environment(tmp_path, monkeypatch):
    """`save_to_file` only ever writes the file fallback — it must never
    reach into `os.environ`, which would be a much stranger and more
    surprising side effect than "the write did nothing while ENV wins"."""
    monkeypatch.delenv(ENV_API_KEY, raising=False)
    monkeypatch.delenv(ENV_API_SECRET, raising=False)
    provider = _provider(tmp_path)

    provider.save_to_file("file-key", "file-secret")

    assert ENV_API_KEY not in os.environ
    assert ENV_API_SECRET not in os.environ
