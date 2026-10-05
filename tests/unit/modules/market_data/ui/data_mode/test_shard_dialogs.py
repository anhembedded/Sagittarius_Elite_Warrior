"""Data → Sync history… and Import data… ask which shard (`EPIC-033J`)."""

from __future__ import annotations

from datetime import UTC, datetime

from PySide6.QtWidgets import QDialogButtonBox
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_widgets.shard_dialogs import (
    ImportDataDialog,
    ShardChoice,
    SyncChoice,
    SyncHistoryDialog,
)

_NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
_SYMBOLS = ("BTCUSDT", "ETHUSDT")
_INTERVALS = ("1m", "15m", "1h")


def _sync(qapp) -> SyncHistoryDialog:
    return SyncHistoryDialog(
        _SYMBOLS, _INTERVALS, ShardChoice("ETHUSDT", "15m"), now=_NOW
    )


def _ok(dialog) -> object:
    return dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)


def test_sync_history_opens_on_the_current_shard_with_no_range(qapp):
    dialog = _sync(qapp)

    assert dialog.windowTitle() == "Sync History"
    assert dialog.choice() == SyncChoice(ShardChoice("ETHUSDT", "15m"), None, None)
    assert not dialog.start.isEnabled()
    assert _ok(dialog).text() == "&Sync"


def test_a_typed_symbol_is_a_new_shard_to_fetch(qapp):
    dialog = _sync(qapp)

    dialog.fields.symbol.setCurrentText(" solusdt ")
    dialog.fields.interval.setCurrentText("1h")

    assert dialog.choice().shard == ShardChoice("SOLUSDT", "1h")


def test_a_checked_range_is_sent_in_the_coordinators_format_in_utc(qapp):
    dialog = _sync(qapp)

    dialog.only_range.setChecked(True)

    assert dialog.start.isEnabled()
    assert dialog.choice() == SyncChoice(
        ShardChoice("ETHUSDT", "15m"), "2026-09-28 12:00", "2026-10-05 12:00"
    )


def test_a_range_that_ends_before_it_starts_cannot_be_sent(qapp):
    dialog = _sync(qapp)
    dialog.only_range.setChecked(True)

    dialog.end.setDateTime(dialog.start.dateTime().addSecs(-60))

    assert not _ok(dialog).isEnabled()
    dialog.only_range.setChecked(False)
    assert _ok(dialog).isEnabled()


def test_import_asks_only_which_shard(qapp):
    dialog = ImportDataDialog(_SYMBOLS, _INTERVALS, ShardChoice("BTCUSDT", "1m"))

    dialog.fields.interval.setCurrentText("1h")

    assert dialog.windowTitle() == "Import Data"
    assert dialog.choice() == ShardChoice("BTCUSDT", "1h")
    assert _ok(dialog).text() == "&Choose file…"
