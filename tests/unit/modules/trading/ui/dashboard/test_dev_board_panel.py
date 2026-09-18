"""EPIC-006D: `DevBoardPanel.qml` -> `DevBoardPanel` (QtWidgets).

Asserts displayed values match the ViewModel's source data, and that the
uiMode/controlsEnabled gating (BUG found building this: BaseQmlViewModel's
own set_ui_mode() ordering bug, fixed at the engine level) reaches every
control correctly.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dashboard_presenter import (
    _WS_STATUS_BY_MODE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dashboard_view_model import (
    DashboardQmlViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dev_board_panel import (
    DevBoardPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.ws_status_pill import (
    WsStatusPill,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.symbol_picker import (
    SymbolTableModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.time_range_picker import (
    RangePresetKind,
)


@pytest.fixture
def view_model(qapp):
    return DashboardQmlViewModel()


@pytest.fixture
def panel(qapp, view_model, request):
    """The controls, with every widget they own shown in a host of this
    fixture's own.

    `DevBoardPanel` stopped being a widget in `EPIC-025` PR 1.4c-3: it builds
    the cards and `DashboardView` places them — five docks, a dialog, a
    toolbar and the status bar. Several of these tests need their widget
    actually *shown* — the QML embeds this panel carried until `EPIC-025`
    PR 4.3l loaded their scene only then — so the fixture stands in for that
    placement with one plain host. Every test body below reaches the widgets
    through the panel's own attributes.
    """
    controls = DevBoardPanel(view_model)
    host = QWidget()
    layout = QVBoxLayout(host)
    for widget in (*controls.header_actions, *controls.status_tiles):
        layout.addWidget(widget)
    for _title, card in controls.dock_panels:
        layout.addWidget(card)
    layout.addWidget(controls.manual_order_card)
    layout.addWidget(controls.console_widget)
    host.resize(380, 700)
    host.show()
    qapp.processEvents()
    request.addfinalizer(host.deleteLater)
    return controls


def test_price_ticker_reflects_the_view_model(qapp, panel, view_model):
    view_model.set_price_ticker("ETHUSDT 2,450.12", "#0ECB81")
    qapp.processEvents()

    assert panel._price_ticker_label.text() == "ETHUSDT 2,450.12"
    assert "#0ECB81" in panel._price_ticker_label.styleSheet()


def _dot_colour(pill: WsStatusPill) -> str:
    return pill._dot.palette().color(QPalette.ColorRole.WindowText).name()


def _colour_for_tone(qtbot_free_parent: QWidget, tone: str) -> str:
    """What a pill asked for `tone` directly would paint its dot.

    A tone is no longer readable back off the widget the way a QML property
    was, so the assertion compares renderings: a second pill is told the tone
    the Presenter declared, and the panel's pill must have painted the same
    thing. The four tones `_WS_STATUS_BY_MODE` uses each resolve to a
    different colour (`test_ws_status_pill.py` pins that), so this fails if
    `_sync_ws_status()` passes the wrong one — which a hardcoded hex
    expectation here would not, since it would then be asserting
    `semantic_colour()`'s output rather than the wiring.
    """
    reference = WsStatusPill(qtbot_free_parent)
    reference.set_tone(tone)
    return _dot_colour(reference)


def test_ws_status_reflects_the_view_model(qapp, panel, view_model):
    """`EPIC-015` Phase 4 made the WS badge a pill driven by plain setters
    rather than an inline stylesheet; PR 4.3l makes that pill `WsStatusPill`
    (QtWidgets). Tone, not the raw `wsStatusColor` hex string, is what
    reaches it — see `dev_board_panel.py`'s `_sync_ws_status()` docstring."""
    view_model.set_ws_status("WS: LIVE", "#0ECB81", "success")
    qapp.processEvents()

    pill = panel._ws_status_pill
    assert pill._label.text() == "WS: LIVE"
    assert _dot_colour(pill) == _colour_for_tone(pill, "success")


@pytest.mark.parametrize("mode", list(_WS_STATUS_BY_MODE.keys()))
def test_ws_status_pill_reflects_every_ui_mode_row(qapp, panel, view_model, mode):
    """Screen-level wiring test: `_sync_ws_status()` must drive the pill with
    the exact text/tone `dashboard_presenter.py`'s `_WS_STATUS_BY_MODE`
    declares for every `UIMode`, not just the one state the older test above
    happened to pick. Reads the same dict the Presenter reads rather than a
    second hardcoded copy of the four rows, so this cannot drift from the
    real mapping.
    """
    text, _color, tone = _WS_STATUS_BY_MODE[mode]
    view_model.set_ws_status(text, _color, tone)
    qapp.processEvents()

    pill = panel._ws_status_pill
    assert pill._label.text() == text
    assert _dot_colour(pill) == _colour_for_tone(pill, tone)


def test_indicator_checkboxes_match_the_script_model(qapp, panel, view_model):
    view_model.script_model.set_available(
        {
            "ema": type("C", (), {"title": "EMA Cross", "default_enabled": True}),
            "rsi": type("C", (), {"title": "RSI", "default_enabled": False}),
        }
    )
    qapp.processEvents()

    assert set(panel._script_checkboxes.keys()) == {"ema", "rsi"}
    assert panel._script_checkboxes["ema"].objectName() == "chkScript_ema"
    assert panel._script_checkboxes["ema"].isChecked() is True
    assert panel._script_checkboxes["rsi"].isChecked() is False


def test_toggling_a_checkbox_writes_through_to_the_script_model(
    qapp, panel, view_model
):
    view_model.script_model.set_available(
        {"rsi": type("C", (), {"title": "RSI", "default_enabled": False})}
    )
    qapp.processEvents()

    panel._script_checkboxes["rsi"].click()
    qapp.processEvents()

    assert view_model.script_model.enabled_keys == ["rsi"]


def test_script_rows_rebuild_when_the_model_resets(qapp, panel, view_model):
    view_model.script_model.set_available(
        {"ema": type("C", (), {"title": "EMA Cross", "default_enabled": True})}
    )
    qapp.processEvents()
    assert set(panel._script_checkboxes.keys()) == {"ema"}

    view_model.script_model.set_available(
        {"rsi": type("C", (), {"title": "RSI", "default_enabled": False})}
    )
    qapp.processEvents()

    assert set(panel._script_checkboxes.keys()) == {"rsi"}


def test_controls_disabled_while_live(qapp, panel, view_model):
    assert panel._btn_start.isEnabled() is True
    assert panel._btn_stop.isEnabled() is False

    view_model.set_ui_mode("LIVE")
    qapp.processEvents()

    assert panel._btn_start.isEnabled() is False
    assert panel._btn_stop.isEnabled() is True
    assert panel._btn_symbol.isEnabled() is False
    assert panel._txt_start_date.isEnabled() is False


def test_controls_disabled_while_locked(qapp, panel, view_model):
    view_model.set_ui_mode("LOCKED")
    qapp.processEvents()

    assert panel._btn_start.isEnabled() is False
    assert panel._btn_load_history.isEnabled() is False


def test_stop_stays_enabled_while_locked_so_a_sync_in_progress_can_be_cancelled(
    qapp, panel, view_model
):
    """BOT-123: Start Live spends its first phase (`SyncMarketDataCommand`
    fetching missing candles from Binance) in `LOCKED`, before the websocket
    ever opens — reported live against a run where that phase alone took
    almost 10 seconds. Stop used to only be enabled in `LIVE`
    (`vm.uiMode == "LIVE"`), so a user watching a long LOCKED sync had no way
    to cancel it short of killing the app — the same cancellation
    `StreamLifecycleController._on_stop_stream` already wires through to the
    sync's `cancellation_requested` check either way."""
    view_model.set_ui_mode("LOCKED")
    qapp.processEvents()

    assert panel._btn_stop.isEnabled() is True


def test_controls_re_enable_back_to_idle(qapp, panel, view_model):
    view_model.set_ui_mode("LIVE")
    qapp.processEvents()
    view_model.set_ui_mode("IDLE")
    qapp.processEvents()

    assert panel._btn_start.isEnabled() is True
    assert panel._btn_stop.isEnabled() is False


def test_history_loading_disables_reload_and_changes_its_label(qapp, panel, view_model):
    view_model.set_history_loading(True)
    qapp.processEvents()

    assert panel._btn_reload.text() == "Loading…"
    assert panel._btn_reload.isEnabled() is False
    assert panel._btn_load_history.text() == "Loading…"


def test_clicking_load_history_emits_the_view_model_request(qapp, panel, view_model):
    requested = []
    view_model.loadHistoryRequested.connect(lambda: requested.append(True))

    panel._btn_load_history.click()
    qapp.processEvents()

    assert requested == [True]


def test_clicking_start_and_stop_emit_the_view_model_requests(qapp, panel, view_model):
    started = []
    stopped = []
    view_model.startStreamRequested.connect(lambda: started.append(True))
    view_model.stopStreamRequested.connect(lambda: stopped.append(True))

    panel._btn_start.click()
    qapp.processEvents()
    assert started == [True]

    view_model.set_ui_mode("LIVE")
    qapp.processEvents()
    panel._btn_stop.click()
    qapp.processEvents()
    assert stopped == [True]


def test_date_fields_edit_writes_through_to_the_view_model(qapp, panel, view_model):
    panel._txt_start_date.setText("2024-01-01 00:00")
    panel._txt_start_date.textEdited.emit("2024-01-01 00:00")
    qapp.processEvents()

    assert view_model.startDate == "2024-01-01 00:00"


def test_view_model_date_change_syncs_the_field(qapp, panel, view_model):
    view_model.startDate = "2024-06-01 00:00"
    qapp.processEvents()

    assert panel._txt_start_date.text() == "2024-06-01 00:00"


def test_symbol_button_starts_at_the_view_model_default(qapp, panel, view_model):
    assert panel._btn_symbol.text() == view_model.symbol


def test_symbol_button_follows_the_view_model(qapp, panel, view_model):
    """EPIC-014 — the direction the old combo silently lacked: it was seeded
    once and never re-read, so a remembered symbol restored into the
    ViewModel left the widget showing the default."""
    view_model.symbol = "ETHBTC"
    qapp.processEvents()

    assert panel._btn_symbol.text() == "ETHBTC"


# ---------------------------------------------------------------------- #
# Progress banner (BOT-123) — Start Live's sync-from-Binance phase used to
# show no progress at all. Same `kit.ProgressBanner` component/wiring shape
# as `test_database_progress_cancel_widget.py`'s own tests.
# ---------------------------------------------------------------------- #


def test_progress_banner_hidden_until_a_sync_is_visible(qapp, panel, view_model):
    assert panel._progress_banner.isVisible() is False


def test_progress_banner_reflects_the_view_model(qapp, panel, view_model):
    view_model.set_progress(25, 100, True, "Syncing ETHUSDT 5m (25/100 candles)")
    qapp.processEvents()

    assert panel._progress_banner.isVisible() is True
    banner = panel._progress_banner
    assert banner._status.text() == "Syncing ETHUSDT 5m (25/100 candles)"
    assert banner._bar.text() == "25%"

    view_model.hide_progress()
    qapp.processEvents()
    assert panel._progress_banner.isVisible() is False


def _progress_cancel_button(panel: DevBoardPanel) -> QPushButton:
    button = panel._progress_banner.findChild(QPushButton, "progressBannerCancel")
    assert button is not None
    return button


def test_clicking_the_progress_banners_cancel_button_requests_stop(
    qapp, panel, view_model
):
    """The banner's own Cancel control is how a user stops a sync running
    in `LOCKED` (see `test_stop_stays_enabled_while_locked_...` above for
    why `LOCKED` needed a way to cancel at all) — it must drive the exact
    same `stopStreamRequested` request the top-level Stop button does, not a
    second, separate cancellation path."""
    view_model.set_progress(0, 0, True, "Syncing data from Binance...")
    qapp.processEvents()

    stopped = []
    view_model.stopStreamRequested.connect(lambda: stopped.append(True))

    _progress_cancel_button(panel).click()
    qapp.processEvents()

    assert stopped == [True]


def test_opening_the_symbol_picker_asks_the_presenter_for_the_list(
    qapp, panel, view_model
):
    """The exchange list costs a round trip, so it is fetched on the first
    open rather than at screen construction — the picker is what asks."""
    requested = []
    view_model.symbolOptionsRequested.connect(lambda: requested.append(True))

    panel._btn_symbol.click()
    qapp.processEvents()

    assert requested == [True]
    assert panel._symbol_picker is not None
    assert panel._symbol_picker.objectName() == "symbolPickerModal"
    panel._symbol_picker.close()


def test_choosing_from_the_picker_writes_through_to_the_view_model(
    qapp, panel, view_model
):
    view_model.set_symbol_options(["BTCUSDT", "ETHBTC"])
    panel._btn_symbol.click()
    qapp.processEvents()

    # Through the view's own `clicked` signal since `EPIC-025` PR 4.3b: the
    # QML view model's `choose()` is gone with `SymbolPicker.qml`, and what
    # decides between starring and choosing is now the column the user hit.
    picker = panel._symbol_picker
    row = [entry.symbol for entry in picker._model.rows].index("ETHBTC")
    picker._table.clicked.emit(picker._model.index(row, SymbolTableModel.SYMBOL_COLUMN))
    qapp.processEvents()

    assert view_model.symbol == "ETHBTC"
    assert panel._btn_symbol.text() == "ETHBTC"
    assert panel._symbol_preferences.recents == ("ETHBTC",)
    panel._symbol_picker.close()


def test_symbol_picker_handles_large_symbol_list_without_freezing(
    qapp, panel, view_model
):
    """`BUG-066`: 1,358 Binance symbols must not freeze the UI.

    The docstring used to end *"SymbolPicker.qml virtualizes items"*, and that
    file is deleted (ADR D21, `EPIC-025` PR 4.3b). What virtualises now is a
    `QTableView` on `SymbolTableModel` inside the **shared** overlay — PR 4.3a's
    work, done precisely so this promise survived the deletion instead of
    reverting to the card grid that caused `BUG-066`.

    Two assertions, and the second is the one that cannot flake: the elapsed
    time is the user's own promise from `BUG-066` and is kept, while "no widget
    per symbol" is the *mechanism* that makes it true and is deterministic on
    any machine.
    """
    large_list = [f"SYM{i}USDT" for i in range(1358)]
    view_model.set_symbol_options(large_list)

    import time

    start = time.perf_counter()
    panel._btn_symbol.click()
    qapp.processEvents()
    elapsed = time.perf_counter() - start

    assert panel._symbol_picker is not None
    # Must open in well under 1 second (previously froze for >5.0s)
    assert elapsed < 1.0
    assert len(panel._symbol_picker._model.rows) == 1358, "all of them are listed"
    assert len(panel._symbol_picker.findChildren(QWidget)) < 100, (
        "1,358 symbols must not mean 1,358 widgets — the view is virtualised"
    )
    panel._symbol_picker.close()


def test_log_panel_is_bound_to_the_view_model_log_model(qapp, panel, view_model):
    assert panel._log_panel.objectName() == "monitorLogPanel"
    view_model.log_model.append("test entry")
    qapp.processEvents()
    assert view_model.log_model.rowCount() == 1


# ------------------------------------------------------------------ #
# Time range picker (EPIC-015) — replaces `pick_date_range()`
# ------------------------------------------------------------------ #


def test_opening_the_range_picker_seeds_from_the_current_fields(qapp, panel):
    panel._txt_start_date.setText("2026-07-01 00:00")
    panel._txt_end_date.setText("2026-07-08 00:00")

    panel._btn_pick_range.click()
    qapp.processEvents()

    dialog = panel._time_range_dialog
    assert dialog._from_field.dateTime().toString("yyyy-MM-dd HH:mm") == (
        "2026-07-01 00:00"
    )
    assert dialog._to_field.dateTime().toString("yyyy-MM-dd HH:mm") == (
        "2026-07-08 00:00"
    )
    dialog.close()


def test_the_picker_falls_back_to_a_1m_summary(qapp, panel):
    """`DashboardQmlViewModel` exposes no per-timeframe concept this panel
    can read (unlike Data Management's `selectedInterval`) — see the
    `_FALLBACK_TIMEFRAME_*` constants in `dev_board_panel.py`."""
    panel._btn_pick_range.click()
    qapp.processEvents()

    dialog = panel._time_range_dialog
    assert dialog._get_timeframe_seconds() == 60
    assert dialog._get_timeframe_label() == "1m"
    assert "candles 1m" in dialog._summary_label.text()
    dialog.close()


def test_applying_writes_both_fields_and_the_view_model(qapp, panel, view_model):
    panel._btn_pick_range.click()
    qapp.processEvents()

    dialog = panel._time_range_dialog
    dialog._choose_preset(RangePresetKind.LAST_7_DAYS)
    qapp.processEvents()
    dialog._btn_apply.click()
    qapp.processEvents()

    assert view_model.startDate == panel._txt_start_date.text()
    assert view_model.endDate == panel._txt_end_date.text()
    assert view_model.startDate != ""
    assert view_model.endDate != ""
    assert not dialog.isVisible()
