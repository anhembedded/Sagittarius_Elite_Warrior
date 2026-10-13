"""`EPIC-038E` — the permission-checked file store: a file per secret under one
directory, read only when every check accepts it, refused once in the log."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import (
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.permission_checked_file_store import (
    PermissionCheckedFileStore,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_secret_file_check import (
    ISecretFileCheck,
    SecretFileVerdict,
)

FAKE = "fake-file-secret-5678"


class _Says(ISecretFileCheck):
    def __init__(self, verdict: SecretFileVerdict) -> None:
        self._verdict = verdict
        self.inspected: list[Path] = []

    def inspect(self, path: Path, descriptor: int) -> SecretFileVerdict:
        self.inspected.append(path)
        return self._verdict


ACCEPT = SecretFileVerdict()
REFUSE = SecretFileVerdict(
    problem="group and other users can read it", fix="chmod 600 THE-PATH"
)


def test_a_file_every_check_accepts_is_read(tmp_path: Path) -> None:
    (tmp_path / "name").write_text(f"{FAKE}\n", encoding="utf-8")

    assert PermissionCheckedFileStore(tmp_path, (_Says(ACCEPT),)).read("name") == FAKE


def test_a_missing_file_reads_none_without_asking_the_checks(tmp_path: Path) -> None:
    check = _Says(REFUSE)

    assert PermissionCheckedFileStore(tmp_path, (check,)).read("name") is None
    assert check.inspected == []


def test_a_group_readable_secret_file_is_refused_without_logging_its_value(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "name").write_text(FAKE, encoding="utf-8")
    store = PermissionCheckedFileStore(tmp_path, (_Says(REFUSE),))

    with caplog.at_level(logging.DEBUG):
        assert store.read("name") is None

    refusals = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(refusals) == 1
    assert "chmod 600" in refusals[0].getMessage()  # the command that fixes it
    assert "group and other users can read it" in refusals[0].getMessage()
    assert FAKE not in caplog.text


def test_a_refusal_is_logged_once_per_file_however_often_it_is_read(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "a").write_text(FAKE, encoding="utf-8")
    (tmp_path / "b").write_text(FAKE, encoding="utf-8")
    store = PermissionCheckedFileStore(tmp_path, (_Says(REFUSE),))

    with caplog.at_level(logging.DEBUG):
        for _ in range(3):
            store.read("a")
            store.read("b")

    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 2


def test_the_first_refusing_check_decides_and_later_ones_are_not_asked(
    tmp_path: Path,
) -> None:
    (tmp_path / "name").write_text(FAKE, encoding="utf-8")
    later = _Says(ACCEPT)

    store = PermissionCheckedFileStore(tmp_path, (_Says(REFUSE), later))

    assert store.read("name") is None
    assert later.inspected == []


def test_a_file_is_checked_at_each_read_not_once(tmp_path: Path) -> None:
    (tmp_path / "name").write_text(FAKE, encoding="utf-8")
    check = _Says(ACCEPT)
    store = PermissionCheckedFileStore(tmp_path, (check,))

    store.read("name")
    store.read("name")

    assert len(check.inspected) == 2


def test_write_and_delete_refuse_because_the_operator_provisions_the_file(
    tmp_path: Path,
) -> None:
    store = PermissionCheckedFileStore(tmp_path, (_Says(ACCEPT),))

    with pytest.raises(SecretStoreUnavailableError, match="provisioned"):
        store.write("name", FAKE)
    with pytest.raises(SecretStoreUnavailableError, match="provisioned"):
        store.delete("name")
    assert list(tmp_path.iterdir()) == []


def test_a_file_that_is_not_text_reads_none_without_its_bytes_in_the_log(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "name").write_bytes(b"\xff\xfeCANARY-BYTES\xff")

    with caplog.at_level(logging.DEBUG):
        assert (
            PermissionCheckedFileStore(tmp_path, (_Says(ACCEPT),)).read("name") is None
        )

    assert "CANARY-BYTES" not in caplog.text


@pytest.mark.skipif(sys.platform == "win32", reason="symbolic links and O_NOFOLLOW")
def test_a_symbolic_link_to_a_file_the_service_owns_is_never_followed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    target = tmp_path / "somewhere_else"
    target.write_text(FAKE, encoding="utf-8")
    target.chmod(0o600)
    directory = tmp_path / "secrets"
    directory.mkdir()
    (directory / "name").symlink_to(target)
    check = _Says(ACCEPT)

    with caplog.at_level(logging.DEBUG):
        assert PermissionCheckedFileStore(directory, (check,)).read("name") is None

    assert check.inspected == []  # refused at the open, before any check
    assert [r for r in caplog.records if r.levelno == logging.WARNING]
    assert FAKE not in caplog.text


@pytest.mark.skipif(sys.platform == "win32", reason="replacing an open file")
def test_the_file_read_is_the_file_inspected_even_if_the_path_is_swapped_between(
    tmp_path: Path,
) -> None:
    """Check-then-use: the checks and the read share one descriptor, so a path
    replaced after the checks cannot change which file is read."""
    path = tmp_path / "name"
    path.write_text("the-inspected-file", encoding="utf-8")
    impostor = tmp_path / "impostor"
    impostor.write_text("the-impostor-file", encoding="utf-8")

    class _SwapsThePathAfterInspecting(ISecretFileCheck):
        def inspect(self, path: Path, descriptor: int) -> SecretFileVerdict:
            impostor.replace(path)
            return SecretFileVerdict()

    store = PermissionCheckedFileStore(tmp_path, (_SwapsThePathAfterInspecting(),))

    assert store.read("name") == "the-inspected-file"


def test_the_checks_are_given_the_open_descriptor_of_the_file(tmp_path: Path) -> None:
    (tmp_path / "name").write_text(FAKE, encoding="utf-8")
    seen: list[int] = []

    class _Records(ISecretFileCheck):
        def inspect(self, path: Path, descriptor: int) -> SecretFileVerdict:
            seen.append(descriptor)
            return SecretFileVerdict()

    PermissionCheckedFileStore(tmp_path, (_Records(),)).read("name")

    assert len(seen) == 1
    assert seen[0] >= 0


def test_a_byte_order_mark_is_not_part_of_the_secret(tmp_path: Path) -> None:
    """Notepad saves UTF-8 with a mark; left in, it is the first character of the key."""
    (tmp_path / "name").write_bytes(b"\xef\xbb\xbf" + f"{FAKE}\r\n".encode())

    assert PermissionCheckedFileStore(tmp_path, (_Says(ACCEPT),)).read("name") == FAKE
