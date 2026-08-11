"""
Tests for DatabaseStatusTableModel (BOT-030 Phase 3) — the first
QAbstractItemModel in this codebase, backing the Database screen's QML
TableView.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QModelIndex

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.database_status_table_model import (
    DatabaseStatusTableModel,
)


@pytest.fixture
def model(qapp):
    return DatabaseStatusTableModel()


def _upsert(model, symbol="BTCUSDT", interval="1m", status="OK", total="100"):
    model.upsert_row(
        symbol=symbol,
        interval=interval,
        first_record="2024-01-01",
        last_record="2024-01-02",
        total_candles=total,
        status_text=status,
    )


def _role_value(model, row, role):
    return model.data(model.index(row, 0), role)


# ---------------------------------------------------------------------------
# Upsert-by-key behavior
# ---------------------------------------------------------------------------


def test_first_upsert_appends_a_row(model):
    _upsert(model)

    assert model.rowCount() == 1
    assert _role_value(model, 0, DatabaseStatusTableModel.SymbolRole) == "BTCUSDT"
    assert _role_value(model, 0, DatabaseStatusTableModel.IntervalRole) == "1m"


def test_re_upserting_same_key_updates_in_place_without_duplicating(model):
    """Re-scanning the same symbol/interval must refresh its line, not stack
    a second one — the behavior DatabaseStatusCard._find_row provided."""
    _upsert(model, status="3 gaps found!", total="90")
    _upsert(model, status="OK", total="120")

    assert model.rowCount() == 1
    assert _role_value(model, 0, DatabaseStatusTableModel.StatusTextRole) == "OK"
    assert _role_value(model, 0, DatabaseStatusTableModel.TotalCandlesRole) == "120"


def test_different_interval_for_same_symbol_is_a_separate_row(model):
    _upsert(model, symbol="BTCUSDT", interval="1m")
    _upsert(model, symbol="BTCUSDT", interval="1h")

    assert model.rowCount() == 2


def test_in_place_update_emits_data_changed_not_insert(model, qapp):
    _upsert(model)
    changed = []
    inserted = []
    model.dataChanged.connect(lambda tl, br, roles: changed.append(tl.row()))
    model.rowsInserted.connect(lambda *_: inserted.append(True))

    _upsert(model, status="5 gaps found!")

    assert changed == [0]
    assert inserted == []


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


def test_role_names_are_exposed_for_qml_binding(model):
    names = set(model.roleNames().values())

    assert {b"symbol", b"interval", b"statusText", b"isHealthy"} <= names


@pytest.mark.parametrize(
    "status, expected_healthy",
    [
        ("OK", True),
        ("0 gaps found!", True),
        ("3 gaps found!", False),
        ("", False),
    ],
)
def test_is_healthy_role_reflects_status_text(model, status, expected_healthy):
    """QML colors the status cell off this role, so the interpretation lives
    here rather than being re-derived in the delegate."""
    _upsert(model, status=status)

    assert (
        _role_value(model, 0, DatabaseStatusTableModel.IsHealthyRole)
        is expected_healthy
    )


def test_data_for_invalid_index_returns_none(model):
    _upsert(model)

    assert model.data(QModelIndex(), DatabaseStatusTableModel.SymbolRole) is None
    assert model.data(model.index(99, 0), DatabaseStatusTableModel.SymbolRole) is None


# ---------------------------------------------------------------------------
# Clearing and derived queries
# ---------------------------------------------------------------------------


def test_clear_removes_every_row(model):
    _upsert(model, symbol="BTCUSDT")
    _upsert(model, symbol="ETHUSDT")

    model.clear()

    assert model.rowCount() == 0


def test_clear_then_reinsert_does_not_reuse_stale_key_index(model):
    """Regression guard: the key->row index must be reset by clear(), or a
    re-scan after clearing would write into a row that no longer exists."""
    _upsert(model, symbol="BTCUSDT", status="OK")
    model.clear()
    _upsert(model, symbol="BTCUSDT", status="7 gaps found!")

    assert model.rowCount() == 1
    assert (
        _role_value(model, 0, DatabaseStatusTableModel.StatusTextRole)
        == "7 gaps found!"
    )


def test_gap_targets_lists_only_unhealthy_rows(model):
    _upsert(model, symbol="BTCUSDT", interval="1m", status="OK")
    _upsert(model, symbol="ETHUSDT", interval="1m", status="4 gaps found!")
    _upsert(model, symbol="SOLUSDT", interval="1h", status="1 gaps found!")

    assert model.gap_targets() == [("ETHUSDT", "1m"), ("SOLUSDT", "1h")]


def test_symbol_and_interval_at_row_are_qml_callable(model):
    _upsert(model, symbol="ETHUSDT", interval="15m")

    assert model.symbolAt(0) == "ETHUSDT"
    assert model.intervalAt(0) == "15m"


def test_row_accessors_are_bounds_safe(model):
    """QML delegates can momentarily hold a stale row index while the model
    resets, so out-of-range lookups must return empty rather than raise."""
    assert model.symbolAt(0) == ""
    assert model.intervalAt(-1) == ""
