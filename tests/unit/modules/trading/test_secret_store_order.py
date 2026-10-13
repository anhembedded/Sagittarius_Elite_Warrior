"""`EPIC-038E` — the one place the order of the secret stores is written.

Environment first (the provider's own rule), then, here: systemd credentials,
the permission-checked file when the operator names a directory for it, and the
operating system's keyring last, the only one the app writes to.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.systemd_credential_store import (
    CREDENTIALS_DIRECTORY_ENV,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.secret_store_order import (
    SECRET_FILES_DIRECTORY_ENV,
    build_secret_stores,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
)


def _sources(environ: dict[str, str]) -> list[CredentialsSource]:
    return [b.source for b in build_secret_stores(environ).backends]


def test_the_default_order_is_systemd_credentials_then_the_keyring() -> None:
    assert _sources({}) == [
        CredentialsSource.SYSTEMD_CREDENTIAL,
        CredentialsSource.KEYRING,
    ]


def test_naming_a_secret_files_directory_adds_the_file_store_before_the_keyring(
    tmp_path: Path,
) -> None:
    assert _sources({SECRET_FILES_DIRECTORY_ENV: str(tmp_path)}) == [
        CredentialsSource.SYSTEMD_CREDENTIAL,
        CredentialsSource.SECRET_FILE,
        CredentialsSource.KEYRING,
    ]


def test_an_empty_secret_files_directory_variable_adds_nothing() -> None:
    assert CredentialsSource.SECRET_FILE not in _sources(
        {SECRET_FILES_DIRECTORY_ENV: ""}
    )


def test_only_the_keyring_is_writable() -> None:
    backends = build_secret_stores({SECRET_FILES_DIRECTORY_ENV: "/x"}).backends

    assert [b.source for b in backends if b.writable] == [CredentialsSource.KEYRING]


def test_the_stores_read_the_environment_they_were_built_from(tmp_path: Path) -> None:
    (tmp_path / "spot_mainnet_api_key").write_text("fake-key\n", encoding="utf-8")
    stores = build_secret_stores({CREDENTIALS_DIRECTORY_ENV: str(tmp_path)})

    (tmp_path / "spot_mainnet_api_secret").write_text("fake-secret\n", encoding="utf-8")

    pair = stores.read_pair("spot_mainnet_api_key", "spot_mainnet_api_secret")

    assert pair is not None
    assert (pair.first, pair.second, pair.source) == (
        "fake-key",
        "fake-secret",
        CredentialsSource.SYSTEMD_CREDENTIAL,
    )
