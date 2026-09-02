"""No-GUI tests for DatabaseStatusVM."""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101, PLR2004

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.qml.DatabaseStatusTable.database_status_table_model import (
    DatabaseStatusTableModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.DatabaseStatusTable.database_status_vm import (
    DatabaseStatusVM,
)


def _seeded_model() -> DatabaseStatusTableModel:
    model = DatabaseStatusTableModel()
    model.upsert_row(
        symbol="BTCUSDT",
        first_record="2026-07-23 15:41:05",
        last_record="2026-08-26 01:19:21",
        total_candles="2,885,897",
        status_text="OK",
        interval="1s",
    )
    return model


def test_row_count_reflects_the_wrapped_model():
    model = _seeded_model()
    vm = DatabaseStatusVM(model)

    assert vm.rowCount == 1


def test_rows_model_is_a_proxy_wrapping_the_real_model_not_a_copy():
    model = _seeded_model()
    vm = DatabaseStatusVM(model)

    assert vm.rowsModel is not model
    assert vm.rowsModel.sourceModel() is model


def test_row_count_changed_fires_when_the_model_gains_a_row():
    model = _seeded_model()
    vm = DatabaseStatusVM(model)
    changed: list[None] = []
    vm.rowCountChanged.connect(lambda: changed.append(None))

    model.upsert_row(
        symbol="ETHUSDT",
        first_record="2026-08-01 00:00:00",
        last_record="2026-08-26 00:00:00",
        total_candles="500",
        status_text="OK",
        interval="1h",
    )

    assert vm.rowCount == 2
    assert len(changed) == 1


def test_request_action_forwards_action_symbol_and_interval():
    vm = DatabaseStatusVM(_seeded_model())
    requests: list[tuple[str, str, str]] = []
    vm.rowActionRequested.connect(lambda a, s, i: requests.append((a, s, i)))

    vm.requestAction("sync", "BTCUSDT", "1s")

    assert requests == [("sync", "BTCUSDT", "1s")]


# --------------------------------------------------------------------------- #
# Search (EPIC-015 Phase 2)
# --------------------------------------------------------------------------- #


def _model_with_two_symbols() -> DatabaseStatusTableModel:
    model = _seeded_model()  # BTCUSDT / 1s
    model.upsert_row(
        symbol="ETHUSDT",
        first_record="2026-08-01 00:00:00",
        last_record="2026-08-26 00:00:00",
        total_candles="500",
        status_text="OK",
        interval="1h",
    )
    return model


def test_set_search_text_filters_rows_model_by_symbol():
    vm = DatabaseStatusVM(_model_with_two_symbols())
    assert vm.rowCount == 2

    vm.setSearchText("eth")

    assert vm.rowCount == 1
    role = vm.rowsModel.sourceModel().SymbolRole
    assert vm.rowsModel.data(vm.rowsModel.index(0, 0), role) == "ETHUSDT"


def test_set_search_text_filters_by_interval_too():
    vm = DatabaseStatusVM(_model_with_two_symbols())

    vm.setSearchText("1h")

    assert vm.rowCount == 1


def test_set_search_text_emits_row_count_changed_only_when_the_count_actually_changes():
    vm = DatabaseStatusVM(_model_with_two_symbols())
    changed: list[None] = []
    vm.rowCountChanged.connect(lambda: changed.append(None))

    vm.setSearchText("eth")
    assert len(changed) == 1

    # Same needle again (case difference only) — no visible change, no signal.
    vm.setSearchText("ETH")
    assert len(changed) == 1

    vm.setSearchText("")
    assert len(changed) == 2


def test_clearing_search_text_restores_the_full_row_count():
    vm = DatabaseStatusVM(_model_with_two_symbols())
    vm.setSearchText("eth")
    assert vm.rowCount == 1

    vm.setSearchText("")

    assert vm.rowCount == 2


# --------------------------------------------------------------------------- #
# Idle/busy toggle (EPIC-015 Phase 2)
# --------------------------------------------------------------------------- #


def test_actions_enabled_defaults_to_true():
    vm = DatabaseStatusVM(_seeded_model())

    assert vm.actionsEnabled is True


def test_set_actions_enabled_updates_the_property_and_notifies():
    vm = DatabaseStatusVM(_seeded_model())
    changed: list[None] = []
    vm.actionsEnabledChanged.connect(lambda: changed.append(None))

    vm.setActionsEnabled(False)

    assert vm.actionsEnabled is False
    assert len(changed) == 1


def test_set_actions_enabled_is_a_no_op_when_unchanged():
    vm = DatabaseStatusVM(_seeded_model())
    vm.setActionsEnabled(False)
    changed: list[None] = []
    vm.actionsEnabledChanged.connect(lambda: changed.append(None))

    vm.setActionsEnabled(False)

    assert len(changed) == 0


# --------------------------------------------------------------------------- #
# Known shard count (BUG-087 — BOT-120 follow-up)
#
# Once auto-discover stopped scanning the vault on screen open (BOT-120),
# `rowCount == 0` could mean two different things — a genuinely empty vault,
# or a vault with real local data nobody has scanned into a row yet — and the
# empty-state placeholder could no longer tell them apart. These tests pin
# the one new fact that lets it, independent of `rowCount`.
# --------------------------------------------------------------------------- #


def test_known_shard_count_defaults_to_zero():
    vm = DatabaseStatusVM(DatabaseStatusTableModel())

    assert vm.knownShardCount == 0


def test_setting_known_shard_count_notifies():
    vm = DatabaseStatusVM(DatabaseStatusTableModel())
    changed = []
    vm.knownShardCountChanged.connect(lambda: changed.append(vm.knownShardCount))

    vm.setKnownShardCount(2)

    assert vm.knownShardCount == 2
    assert changed == [2]


def test_setting_the_same_known_shard_count_does_not_renotify():
    vm = DatabaseStatusVM(DatabaseStatusTableModel())
    vm.setKnownShardCount(2)
    changed = []
    vm.knownShardCountChanged.connect(lambda: changed.append(vm.knownShardCount))

    vm.setKnownShardCount(2)

    assert changed == []


def test_known_shard_count_is_independent_of_row_count():
    """The two facts must stay separately settable — collapsing them back
    into one number is exactly the regression this VM exists to prevent."""
    vm = DatabaseStatusVM(_seeded_model())

    vm.setKnownShardCount(2)

    assert vm.rowCount == 1
    assert vm.knownShardCount == 2
