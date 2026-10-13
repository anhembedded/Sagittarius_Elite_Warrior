"""`EPIC-038E` (O3) — systemd credentials: a file per secret under
`$CREDENTIALS_DIRECTORY`, provisioned by the unit file and read-only for the app."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import (
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.systemd_credential_store import (
    CREDENTIALS_DIRECTORY_ENV,
    SystemdCredentialStore,
)

FAKE = "fake-systemd-secret-1234"


def _store(directory: Path) -> SystemdCredentialStore:
    return SystemdCredentialStore({CREDENTIALS_DIRECTORY_ENV: str(directory)})


def test_systemd_credentials_read_from_the_credentials_directory(
    tmp_path: Path,
) -> None:
    (tmp_path / "spot_mainnet_api_key").write_text(FAKE, encoding="utf-8")

    assert _store(tmp_path).read("spot_mainnet_api_key") == FAKE


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (f"{FAKE}\n", FAKE),
        (f"{FAKE}\r\n", FAKE),
        (
            f"{FAKE}\n\n",
            f"{FAKE}\n",
        ),  # one trailing newline, as systemd's own docs read it
        (FAKE, FAKE),
    ],
)
def test_one_trailing_newline_is_stripped_and_no_more(
    tmp_path: Path, content: str, expected: str
) -> None:
    (tmp_path / "name").write_bytes(content.encode("utf-8"))

    assert _store(tmp_path).read("name") == expected


def test_a_missing_credentials_directory_variable_reads_none_quietly(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        assert SystemdCredentialStore({}).read("name") is None
        assert SystemdCredentialStore({CREDENTIALS_DIRECTORY_ENV: ""}).read("n") is None

    assert not [r for r in caplog.records if r.levelno >= logging.INFO]


def test_a_missing_credentials_directory_reads_none(tmp_path: Path) -> None:
    assert _store(tmp_path / "does-not-exist").read("name") is None


def test_a_missing_credential_file_reads_none(tmp_path: Path) -> None:
    assert _store(tmp_path).read("name") is None


def test_a_directory_where_a_credential_should_be_reads_none(tmp_path: Path) -> None:
    (tmp_path / "name").mkdir()

    assert _store(tmp_path).read("name") is None


def test_a_credential_that_is_not_text_reads_none_without_its_bytes_in_the_log(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "name").write_bytes(b"\xff\xfeCANARY-BYTES\xff")

    with caplog.at_level(logging.DEBUG):
        assert _store(tmp_path).read("name") is None

    assert "CANARY-BYTES" not in caplog.text
    assert "CANARY-BYTES" not in repr(caplog.records)


def test_an_oversized_credential_reads_none(tmp_path: Path) -> None:
    (tmp_path / "name").write_text("x" * 100_000, encoding="utf-8")

    assert _store(tmp_path).read("name") is None


def test_write_and_delete_say_credentials_are_provisioned_by_the_unit_file(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)

    for attempt in (lambda: store.write("n", FAKE), lambda: store.delete("n")):
        with pytest.raises(SecretStoreUnavailableError, match="unit file"):
            attempt()

    assert list(tmp_path.iterdir()) == []


def test_the_store_reads_the_directory_at_each_read(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.read("name") is None

    (tmp_path / "name").write_text(FAKE, encoding="utf-8")

    assert store.read("name") == FAKE


def test_a_byte_order_mark_is_not_part_of_the_secret(tmp_path: Path) -> None:
    (tmp_path / "name").write_bytes(b"\xef\xbb\xbf" + f"{FAKE}\r\n".encode())

    assert _store(tmp_path).read("name") == FAKE
