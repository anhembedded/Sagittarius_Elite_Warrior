"""`DatabaseStatusPanel` — the QtWidgets status table and its four actions.

`EPIC-025` PR 0.4b. What the deleted QML pair (`DatabaseStatusTable.qml` +
`DatabaseStatusRow.qml`) had tested through a loaded QML tree and 358 lines of
`findChild`/`qml_item` lookups is tested here against real widgets: the
selection decides which shard an action applies to, `set_actions_enabled`
still gates every one of them, and `Clear` asks first.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_widgets.database_status_panel import (
    CLEAR_SHARD,
    INSPECT_GAPS,
    INSPECT_KLINES,
    SYNC_SHARD,
    DatabaseStatusPanel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.database_status_table_model import (
    DatabaseStatusTableModel,
)

_HEALTHY = "OK"
_UNHEALTHY = "3 gaps found!"


@pytest.fixture
def model(qapp):
    return DatabaseStatusTableModel()


@pytest.fixture
def panel(qapp, model, request):
    """Built with a confirmation that always says yes, so a test that is not
    about the confirmation never blocks on a modal dialog."""
    widget = DatabaseStatusPanel(model, confirm_clear=lambda _row: True)
    request.addfinalizer(widget.deleteLater)
    return widget


def _upsert(
    model: DatabaseStatusTableModel,
    symbol: str = "BTCUSDT",
    status: str = _HEALTHY,
    interval: str = "1m",
    total: str = "100",
) -> None:
    model.upsert_row(
        symbol=symbol,
        first_record="2024-01-01 00:00",
        last_record="2024-01-02 00:00",
        total_candles=total,
        status_text=status,
        interval=interval,
    )


def _select(panel: DatabaseStatusPanel, row: int) -> None:
    index = panel._table.model().index(row, 0)
    panel._table.selectionModel().select(
        index,
        panel._table.selectionModel().SelectionFlag.ClearAndSelect
        | panel._table.selectionModel().SelectionFlag.Rows,
    )


def _emitted(panel: DatabaseStatusPanel) -> list[tuple[str, str, str]]:
    seen: list[tuple[str, str, str]] = []
    panel.rowActionRequested.connect(
        lambda action, symbol, interval: seen.append((action, symbol, interval))
    )
    return seen


# ---------------------------------------------------------------------------
# What the panel shows
# ---------------------------------------------------------------------------


def test_an_empty_vault_says_so_and_hides_the_table(panel):
    assert panel.visible_row_count() == 0
    assert panel._empty.isVisibleTo(panel) is True
    assert panel._table.isVisibleTo(panel) is False
    assert "Storage Vault is empty" in panel._empty.text()


def test_shards_on_disk_that_nobody_scanned_get_their_own_message(panel):
    """`BUG-087`: 0 rows and 4 files on disk is not an empty vault, and the
    message must not tell the user it is."""
    panel.set_known_shard_count(4)

    assert "4 local data file(s)" in panel._empty.text()


def test_a_row_replaces_the_empty_state_with_the_table(panel, model):
    _upsert(model)

    assert panel.visible_row_count() == 1
    assert panel._table.isVisibleTo(panel) is True
    assert panel._empty.isVisibleTo(panel) is False


def test_the_count_label_reports_the_visible_rows(panel, model):
    _upsert(model, symbol="BTCUSDT")
    assert panel._count_label.text() == "1 shard"

    _upsert(model, symbol="ETHUSDT")
    assert panel._count_label.text() == "2 shards"


def test_searching_narrows_both_the_table_and_the_count(panel, model):
    _upsert(model, symbol="BTCUSDT")
    _upsert(model, symbol="ETHUSDT")

    panel.set_search_text("eth")

    assert panel.visible_row_count() == 1
    assert panel._count_label.text() == "1 shard"


def test_typing_in_the_search_box_filters_the_table(panel, model):
    """Drives the widget, not `set_search_text()`. Those are two different
    code paths: the programmatic one calls the proxy itself, while typing
    reaches it only through `QLineEdit.textEdited`. Deleting that connection
    left the other 22 tests in this file green — this is the one that fails.
    """
    _upsert(model, symbol="BTCUSDT")
    _upsert(model, symbol="ETHUSDT")

    panel._search.setText("eth")
    panel._search.textEdited.emit("eth")

    assert panel.visible_row_count() == 1
    assert panel._count_label.text() == "1 shard"


def test_clearing_the_search_box_brings_every_shard_back(panel, model):
    _upsert(model, symbol="BTCUSDT")
    _upsert(model, symbol="ETHUSDT")
    panel._search.setText("eth")
    panel._search.textEdited.emit("eth")

    panel._search.clear()
    panel._search.textEdited.emit("")

    assert panel.visible_row_count() == 2


def test_a_search_matching_nothing_shows_the_empty_state(panel, model):
    _upsert(model, symbol="BTCUSDT")

    panel.set_search_text("nothing")

    assert panel._empty.isVisibleTo(panel) is True


# ---------------------------------------------------------------------------
# Which shard an action applies to
# ---------------------------------------------------------------------------


def test_no_selection_means_no_action_is_available(panel, model):
    _upsert(model)

    assert [action.isEnabled() for action in panel._actions.values()] == [False] * 4


def test_selecting_a_row_enables_the_actions_that_apply_to_it(panel, model):
    _upsert(model, status=_HEALTHY)
    _select(panel, 0)

    assert panel._actions[INSPECT_KLINES].isEnabled() is True
    assert panel._actions[SYNC_SHARD].isEnabled() is True
    assert panel._actions[CLEAR_SHARD].isEnabled() is True
    # Nothing to inspect: this shard reports no gaps.
    assert panel._actions[INSPECT_GAPS].isEnabled() is False


def test_inspect_gaps_is_enabled_on_a_shard_that_has_gaps(panel, model):
    _upsert(model, status=_UNHEALTHY)
    _select(panel, 0)

    assert panel._actions[INSPECT_GAPS].isEnabled() is True


def test_an_action_emits_the_selected_shard(panel, model):
    _upsert(model, symbol="ETHUSDT", interval="15m")
    _select(panel, 0)
    seen = _emitted(panel)

    panel._actions[SYNC_SHARD].trigger()

    assert seen == [(SYNC_SHARD, "ETHUSDT", "15m")]


def test_the_action_follows_the_selection_not_the_row_order(panel, model):
    """The QML row emitted its own symbol because the button was inside it.
    With one toolbar for every row, the wrong selection would act on the
    wrong shard — which is what this pins."""
    _upsert(model, symbol="AAAUSDT")
    _upsert(model, symbol="ZZZUSDT")
    _select(panel, 1)
    seen = _emitted(panel)

    panel._actions[INSPECT_KLINES].trigger()

    assert seen == [(INSPECT_KLINES, "ZZZUSDT", "1m")]


def test_double_clicking_a_row_inspects_its_candles(panel, model):
    """The Efficiency principle: the most common action on a row is one
    gesture away, not a trip to the toolbar."""
    _upsert(model)
    _select(panel, 0)
    seen = _emitted(panel)

    panel._table.doubleClicked.emit(panel._table.model().index(0, 0))

    assert seen == [(INSPECT_KLINES, "BTCUSDT", "1m")]


def test_nothing_is_emitted_when_no_row_is_selected(panel, model):
    _upsert(model)
    seen = _emitted(panel)

    panel._actions[SYNC_SHARD].trigger()

    assert seen == []


# ---------------------------------------------------------------------------
# The idle gate
# ---------------------------------------------------------------------------


def test_a_running_sync_disables_every_action(panel, model):
    _upsert(model, status=_UNHEALTHY)
    _select(panel, 0)

    panel.set_actions_enabled(False)

    assert [action.isEnabled() for action in panel._actions.values()] == [False] * 4


def test_a_disabled_action_cannot_be_triggered_anyway(panel, model):
    """`QAction.trigger()` on a disabled action is already a no-op, but a
    double-click reaches `_request` directly — so the gate is checked there
    too, not only on the action's enabled state."""
    _upsert(model)
    _select(panel, 0)
    seen = _emitted(panel)
    panel.set_actions_enabled(False)

    panel._table.doubleClicked.emit(panel._table.model().index(0, 0))

    assert seen == []


def test_the_actions_come_back_when_the_screen_goes_idle_again(panel, model):
    _upsert(model)
    _select(panel, 0)
    panel.set_actions_enabled(False)

    panel.set_actions_enabled(True)

    assert panel._actions[SYNC_SHARD].isEnabled() is True


# ---------------------------------------------------------------------------
# Clear asks first
# ---------------------------------------------------------------------------


def test_clear_does_nothing_when_the_user_declines(qapp, model, request):
    asked: list[str] = []

    def decline(row):
        asked.append(row.symbol)
        return False

    panel = DatabaseStatusPanel(model, confirm_clear=decline)
    request.addfinalizer(panel.deleteLater)
    _upsert(model, symbol="BTCUSDT")
    _select(panel, 0)
    seen = _emitted(panel)

    panel._actions[CLEAR_SHARD].trigger()

    assert asked == ["BTCUSDT"], "the user must be asked before a delete"
    assert seen == [], "declining must not reach the Presenter"


def test_clear_proceeds_when_the_user_confirms(panel, model):
    _upsert(model, symbol="BTCUSDT")
    _select(panel, 0)
    seen = _emitted(panel)

    panel._actions[CLEAR_SHARD].trigger()

    assert seen == [(CLEAR_SHARD, "BTCUSDT", "1m")]


def test_only_clear_asks(panel, model):
    """A confirmation on a read-only action would be noise, and the
    User-Control principle asks for one on the destructive action only."""
    asked: list[str] = []

    def record(row):
        asked.append(row.symbol)
        return True

    panel._confirm_clear = record
    _upsert(model, status=_UNHEALTHY)
    _select(panel, 0)

    for action_id in (INSPECT_KLINES, INSPECT_GAPS, SYNC_SHARD):
        panel._actions[action_id].trigger()

    assert asked == []


# ---------------------------------------------------------------------------
# The desktop rules this panel is meant to satisfy
# ---------------------------------------------------------------------------


def test_every_action_is_on_the_table_itself_so_a_right_click_finds_it(panel):
    """`Qt.ContextMenuPolicy.ActionsContextMenu` renders a widget's own
    actions as its context menu — one list of actions, two ways in."""
    assert panel._table.contextMenuPolicy() == Qt.ContextMenuPolicy.ActionsContextMenu
    assert len(panel._table.actions()) == len(panel._actions)


def test_the_table_selects_whole_rows_one_at_a_time(panel):
    """A shard is a row; half a row is not a thing any of the four actions
    could act on."""
    assert panel._table.selectionBehavior().name == "SelectRows"
    assert panel._table.selectionMode().name == "SingleSelection"


def test_the_user_can_sort_the_table(panel):
    assert panel._table.isSortingEnabled() is True
