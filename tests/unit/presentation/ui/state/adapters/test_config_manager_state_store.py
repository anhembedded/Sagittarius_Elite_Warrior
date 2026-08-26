"""`ConfigManagerStateStore` — the persistent store.

Every test here runs against a real `ConfigManager` and a real file on disk
(via `tmp_path`), not a mock — the whole point of `010A` is that the store's
hardest guarantees (`010A`'s design §5.6.6 rows 1-3) come from the engine's
own `ConfigManager`, so the only honest way to prove them is to exercise the
real thing, the same way `scripts/ui_state_store_feasibility_probe.py`
already did as a feasibility probe. This file is that probe promoted to a
permanent, CI-run regression test.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.state.adapters.config_manager_state_store import (
    ConfigManagerStateStore,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.ports.i_state_store_locator import (
    IStateStoreLocator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import StateScope


class _FixedLocator(IStateStoreLocator):
    """A locator pointed at one fixed path — the only double this suite needs,
    since the locator's own behaviour is covered by
    `test_repo_state_store_locator.py`."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def state_file(self) -> Path:
        return self._path

    def reset(self) -> None:
        self._path.unlink(missing_ok=True)


def _store(tmp_path: Path, name: str = "ui_state.json") -> ConfigManagerStateStore:
    return ConfigManagerStateStore(_FixedLocator(tmp_path / name))


# --------------------------------------------------------------------------- #
# Failure mode #8 / #9 — missing and corrupt files must never block boot
# --------------------------------------------------------------------------- #


def test_read_on_a_missing_file_returns_an_empty_slice(tmp_path: Path):
    store = _store(tmp_path)

    assert store.read(StateScope(key="dashboard")) == {}


def test_truncated_file_yields_empty_slices_without_raising(tmp_path: Path):
    """Locks the accepted cost from `EPIC-010` design §4.1.3: `save()` is not
    atomic, so a crash mid-write truncates the file — and the next launch
    MUST fall back to defaults, not raise. `architecture-rule.md` §7.1
    requires an accepted cost to be locked by a test, not left as a comment.
    """
    path = tmp_path / "ui_state.json"
    path.write_text('{"dashboard": {"symbol": "BTC', encoding="utf-8")  # cut mid-write

    store = _store(tmp_path)

    assert store.read(StateScope(key="dashboard")) == {}  # no raise


# --------------------------------------------------------------------------- #
# Failure mode #10 — a document from a newer build must be ignored wholesale
# --------------------------------------------------------------------------- #


def test_a_newer_schema_version_is_ignored_wholesale(tmp_path: Path):
    path = tmp_path / "ui_state.json"
    path.write_text(
        json.dumps({"schema_version": 999, "dashboard": {"symbol": "BTCUSDT"}}),
        encoding="utf-8",
    )

    store = _store(tmp_path)

    assert store.read(StateScope(key="dashboard")) == {}


def test_a_document_with_no_schema_version_at_all_is_readable(tmp_path: Path):
    """A hand-edited or pre-`010A` file with no `schema_version` key must not
    be treated as "from the future" — a missing version means "old enough to
    trust", not "newer than we understand"."""
    path = tmp_path / "ui_state.json"
    path.write_text(json.dumps({"dashboard": {"symbol": "BTCUSDT"}}), encoding="utf-8")

    store = _store(tmp_path)

    assert store.read(StateScope(key="dashboard")) == {"symbol": "BTCUSDT"}


# --------------------------------------------------------------------------- #
# D2 — writing one slice must never disturb another
# --------------------------------------------------------------------------- #


def test_writing_one_slice_leaves_every_other_slice_intact(tmp_path: Path):
    """The lazy-presenter guarantee: a session that only opened the Dev Board
    must not erase the Backtest slice a previous session wrote."""
    first = _store(tmp_path)
    first.write(StateScope(key="backtest"), {"strategy_key": "ema_pullback"})

    second = _store(tmp_path)  # a fresh process, fresh ConfigManager instance
    second.write(StateScope(key="dashboard"), {"symbol": "SOLUSDT"})

    third = _store(tmp_path)  # read back with yet another fresh instance
    assert third.read(StateScope(key="dashboard")) == {"symbol": "SOLUSDT"}
    assert third.read(StateScope(key="backtest")) == {"strategy_key": "ema_pullback"}


def test_a_nested_slice_round_trips_through_a_restart(tmp_path: Path):
    data = {"symbol": "BTCUSDT", "enabled_scripts": ["ema_20", "rsi_14"]}
    _store(tmp_path).write(StateScope(key="dashboard"), data)

    reopened = _store(tmp_path)

    assert reopened.read(StateScope(key="dashboard")) == data


# --------------------------------------------------------------------------- #
# discard() and per-instance identity
# --------------------------------------------------------------------------- #


def test_discard_empties_the_slice_but_not_the_file(tmp_path: Path):
    store = _store(tmp_path)
    store.write(StateScope(key="dashboard"), {"symbol": "BTCUSDT"})
    store.write(StateScope(key="backtest"), {"strategy_key": "ema_pullback"})

    store.discard(StateScope(key="dashboard"))

    assert store.read(StateScope(key="dashboard")) == {}
    assert store.read(StateScope(key="backtest")) == {"strategy_key": "ema_pullback"}


def test_two_instances_of_one_owner_occupy_distinct_slices(tmp_path: Path):
    """`StateScope.storage_key` is what makes multiplicity safe — see
    `test_state_scope.py`. This proves it end-to-end through a real store."""
    store = _store(tmp_path)
    scope_a = StateScope(key="dashboard", instance_id="7f3a")
    scope_b = StateScope(key="dashboard", instance_id="9c1e")

    store.write(scope_a, {"symbol": "BTCUSDT"})
    store.write(scope_b, {"symbol": "ETHUSDT"})

    assert store.read(scope_a) == {"symbol": "BTCUSDT"}
    assert store.read(scope_b) == {"symbol": "ETHUSDT"}


# --------------------------------------------------------------------------- #
# Failure mode #7 — write failure must never propagate
# --------------------------------------------------------------------------- #


def test_write_failure_is_swallowed_not_raised(tmp_path: Path):
    """A path whose parent cannot be created (`NotADirectoryError`, an
    `OSError` subclass) stands in for "disk full" / "read-only" / "permission
    denied" — all reach `ConfigManager.save()` the same way. This is the
    `BUG-048` lesson applied to this store: the shutdown path must not throw.
    """
    blocked = tmp_path / "not_a_directory"
    blocked.write_text("occupied by a file, not a dir", encoding="utf-8")
    store = _store(tmp_path / "not_a_directory" / "nested", "ui_state.json")

    store.write(StateScope(key="dashboard"), {"symbol": "BTCUSDT"})  # must not raise


def test_write_failure_logs_once_not_once_per_call(tmp_path: Path, caplog):
    blocked = tmp_path / "not_a_directory"
    blocked.write_text("occupied by a file, not a dir", encoding="utf-8")
    store = _store(tmp_path / "not_a_directory" / "nested", "ui_state.json")

    with caplog.at_level("WARNING", logger="App.UiState"):
        store.write(StateScope(key="dashboard"), {"symbol": "BTCUSDT"})
        store.write(StateScope(key="backtest"), {"strategy_key": "x"})
        store.flush()

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1


# --------------------------------------------------------------------------- #
# Failure mode #4 — a non-JSON-safe value must fail loudly, immediately
# --------------------------------------------------------------------------- #


def test_a_non_json_safe_value_raises_at_write_time_not_at_shutdown(tmp_path: Path):
    """`write()` flushes synchronously, so a bad value fails on the same call
    stack as the mistake — not silently deferred to `teardown()`, where
    `BUG-048` already showed an exception on that path used to hang the
    process instead of reporting."""
    store = _store(tmp_path)

    with pytest.raises(TypeError):
        store.write(StateScope(key="dashboard"), {"when": object()})


# --------------------------------------------------------------------------- #
# Probe H4, promoted — the store must never see or touch real credentials
# --------------------------------------------------------------------------- #


def test_never_shares_a_file_or_data_with_user_config(tmp_path: Path):
    user_config = tmp_path / "user_config.json"
    user_config.write_text(json.dumps({"API_KEY": "do-not-touch"}), encoding="utf-8")

    store = _store(tmp_path, "ui_state.json")
    store.write(StateScope(key="dashboard"), {"symbol": "BTCUSDT"})

    assert json.loads(user_config.read_text(encoding="utf-8")) == {
        "API_KEY": "do-not-touch"
    }
    assert store.read(StateScope(key="API_KEY")) == {}
