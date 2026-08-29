"""No-GUI tests for DatabaseStatusVM."""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101, PLR2004

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.qml.DatabaseStatusTable.database_status_vm import (
    DatabaseStatusVM,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.database_status_table_model import (
    DatabaseStatusTableModel,
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


def test_rows_model_is_the_same_instance_not_a_copy():
    model = _seeded_model()
    vm = DatabaseStatusVM(model)

    assert vm.rowsModel is model


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
