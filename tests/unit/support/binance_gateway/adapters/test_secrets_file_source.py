from __future__ import annotations

import json
import stat
import sys

import pytest
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.secrets_file_source import (
    SecretsFileSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_FUTURES = TradingVenue.FUTURES_TESTNET
_SPOT = TradingVenue.SPOT_TESTNET


def test_read_returns_none_when_the_file_does_not_exist(tmp_path):
    source = SecretsFileSource(str(tmp_path / "missing.json"))
    assert source.read(_FUTURES) is None


def test_write_then_read_round_trips(tmp_path):
    source = SecretsFileSource(str(tmp_path / "secrets.local.json"))

    source.write(_FUTURES, "key-1", "secret-1")

    assert source.read(_FUTURES) == ("key-1", "secret-1")


def test_write_creates_parent_directories(tmp_path):
    source = SecretsFileSource(str(tmp_path / "nested" / "dir" / "secrets.local.json"))

    source.write(_FUTURES, "key-1", "secret-1")

    assert source.read(_FUTURES) == ("key-1", "secret-1")


def test_a_second_write_overwrites_the_first(tmp_path):
    source = SecretsFileSource(str(tmp_path / "secrets.local.json"))
    source.write(_FUTURES, "old-key", "old-secret")

    source.write(_FUTURES, "new-key", "new-secret")

    assert source.read(_FUTURES) == ("new-key", "new-secret")


def test_each_venue_has_its_own_pair(tmp_path):
    """`BUG-176` — writing one venue's key reads back unchanged for the others."""
    source = SecretsFileSource(str(tmp_path / "secrets.local.json"))
    source.write(_FUTURES, "futures-key", "futures-secret")

    source.write(_SPOT, "spot-key", "spot-secret")

    assert source.read(_FUTURES) == ("futures-key", "futures-secret")
    assert source.read(_SPOT) == ("spot-key", "spot-secret")


def test_remove_forgets_one_venue_and_keeps_the_other(tmp_path):
    source = SecretsFileSource(str(tmp_path / "secrets.local.json"))
    source.write(_FUTURES, "futures-key", "futures-secret")
    source.write(_SPOT, "spot-key", "spot-secret")

    source.remove(_FUTURES)

    assert source.read(_FUTURES) is None
    assert source.read(_SPOT) == ("spot-key", "spot-secret")


def test_removing_a_venue_with_no_pair_changes_nothing(tmp_path):
    source = SecretsFileSource(str(tmp_path / "secrets.local.json"))
    source.write(_SPOT, "spot-key", "spot-secret")

    source.remove(_FUTURES)

    assert source.read(_SPOT) == ("spot-key", "spot-secret")


def test_a_pair_written_before_the_file_had_venues_is_read_for_both_testnets(tmp_path):
    path = tmp_path / "secrets.local.json"
    path.write_text('{"API_KEY": "old-key", "API_SECRET": "old-secret"}')
    source = SecretsFileSource(str(path))

    assert source.read(_FUTURES) == ("old-key", "old-secret")
    assert source.read(_SPOT) == ("old-key", "old-secret")


def test_a_mainnet_venue_never_reads_the_old_shared_pair(tmp_path):
    path = tmp_path / "secrets.local.json"
    path.write_text('{"API_KEY": "old-key", "API_SECRET": "old-secret"}')
    source = SecretsFileSource(str(path))

    assert source.read(TradingVenue.SPOT_MAINNET) is None
    assert source.read(TradingVenue.FUTURES_MAINNET) is None


def test_changing_one_venue_keeps_the_old_shared_pair_for_the_other(tmp_path):
    """The old pair served both testnets: replacing one venue's key must not take
    the other's with it, and removing one must not let the old pair come back."""
    path = tmp_path / "secrets.local.json"
    path.write_text('{"API_KEY": "old-key", "API_SECRET": "old-secret"}')
    source = SecretsFileSource(str(path))

    source.write(_FUTURES, "new-key", "new-secret")
    assert source.read(_FUTURES) == ("new-key", "new-secret")
    assert source.read(_SPOT) == ("old-key", "old-secret")

    source.remove(_SPOT)
    assert source.read(_SPOT) is None
    assert source.read(_FUTURES) == ("new-key", "new-secret")
    assert "API_KEY" not in json.loads(path.read_text())


def test_malformed_json_reads_as_none_rather_than_raising(tmp_path):
    path = tmp_path / "secrets.local.json"
    path.write_text("{not valid json", encoding="utf-8")
    source = SecretsFileSource(str(path))

    assert source.read(_FUTURES) is None


def test_a_venue_entry_missing_one_field_reads_as_none(tmp_path):
    path = tmp_path / "secrets.local.json"
    path.write_text('{"venues": {"futures_testnet": {"API_KEY": "only-the-key"}}}')
    source = SecretsFileSource(str(path))

    assert source.read(_FUTURES) is None


def test_a_file_with_an_empty_field_reads_as_none(tmp_path):
    path = tmp_path / "secrets.local.json"
    path.write_text('{"API_KEY": "", "API_SECRET": "s"}', encoding="utf-8")
    source = SecretsFileSource(str(path))

    assert source.read(_FUTURES) is None


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

    source.write(_FUTURES, "key-1", "secret-1")

    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600


def test_changing_an_unreadable_file_keeps_it_aside_instead_of_overwriting_it(tmp_path):
    """The reviewer's finding on PR #423: rewriting a file that could not be read
    would destroy every other venue's key in it."""
    path = tmp_path / "secrets.local.json"
    path.write_text('{"venues": {"spot_testnet": {"API_KEY": "k", ', encoding="utf-8")
    source = SecretsFileSource(str(path))

    source.write(_FUTURES, "new-key", "new-secret")

    assert source.read(_FUTURES) == ("new-key", "new-secret")
    assert "spot_testnet" in (tmp_path / "secrets.local.json.corrupt").read_text()


def test_a_write_leaves_no_temporary_file_behind(tmp_path):
    source = SecretsFileSource(str(tmp_path / "secrets.local.json"))

    source.write(_FUTURES, "key-1", "secret-1")

    assert [p.name for p in tmp_path.iterdir()] == ["secrets.local.json"]


@pytest.mark.parametrize(
    "venue", [TradingVenue.SPOT_MAINNET, TradingVenue.FUTURES_MAINNET]
)
def test_a_mainnet_secret_is_refused_by_the_file(tmp_path, venue):
    source = SecretsFileSource(str(tmp_path / "secrets.local.json"))

    with pytest.raises(ValueError, match="keyring"):
        source.write(venue, "key", "secret")
    with pytest.raises(ValueError, match="keyring"):
        source.remove(venue)
    assert not (tmp_path / "secrets.local.json").exists()
