from __future__ import annotations

import stat
import sys

import pytest
from Sagittarius_Elite_Warrior.src.infrastructure.credentials.secrets_file_source import (
    SecretsFileSource,
)


def test_read_returns_none_when_the_file_does_not_exist(tmp_path):
    source = SecretsFileSource(str(tmp_path / "missing.json"))
    assert source.read() is None


def test_write_then_read_round_trips(tmp_path):
    source = SecretsFileSource(str(tmp_path / "secrets.local.json"))

    source.write("key-1", "secret-1")

    assert source.read() == ("key-1", "secret-1")


def test_write_creates_parent_directories(tmp_path):
    source = SecretsFileSource(str(tmp_path / "nested" / "dir" / "secrets.local.json"))

    source.write("key-1", "secret-1")

    assert source.read() == ("key-1", "secret-1")


def test_a_second_write_overwrites_the_first(tmp_path):
    source = SecretsFileSource(str(tmp_path / "secrets.local.json"))
    source.write("old-key", "old-secret")

    source.write("new-key", "new-secret")

    assert source.read() == ("new-key", "new-secret")


def test_malformed_json_reads_as_none_rather_than_raising(tmp_path):
    path = tmp_path / "secrets.local.json"
    path.write_text("{not valid json", encoding="utf-8")
    source = SecretsFileSource(str(path))

    assert source.read() is None


def test_a_file_missing_one_field_reads_as_none(tmp_path):
    path = tmp_path / "secrets.local.json"
    path.write_text('{"API_KEY": "only-the-key"}', encoding="utf-8")
    source = SecretsFileSource(str(path))

    assert source.read() is None


def test_a_file_with_an_empty_field_reads_as_none(tmp_path):
    path = tmp_path / "secrets.local.json"
    path.write_text('{"API_KEY": "", "API_SECRET": "s"}', encoding="utf-8")
    source = SecretsFileSource(str(path))

    assert source.read() is None


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX permission bits don't map the same way on Windows",
)
def test_write_hardens_the_file_to_owner_only(tmp_path):
    """`BUG-097` — a plain `open(..., 'w')` leaves the file at the process
    umask's default, typically world-readable; on a shared machine (a VPS,
    this repo's own deploy target) any other local user could read the
    API key/secret straight off disk."""
    path = tmp_path / "secrets.local.json"
    source = SecretsFileSource(str(path))

    source.write("key-1", "secret-1")

    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600
