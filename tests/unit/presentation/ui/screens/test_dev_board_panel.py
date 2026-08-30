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

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view_model import (
    DashboardQmlViewModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dev_board_panel import (
    DevBoardPanel,
)


@pytest.fixture
def view_model(qapp):
    return DashboardQmlViewModel()


@pytest.fixture
def panel(qapp, view_model, request):
    widget = DevBoardPanel(view_model)
    widget.resize(380, 700)
    widget.show()
    qapp.processEvents()
    request.addfinalizer(widget.deleteLater)
    return widget


def test_price_ticker_reflects_the_view_model(qapp, panel, view_model):
    view_model.set_price_ticker("ETHUSDT 2,450.12", "#0ECB81")
    qapp.processEvents()

    assert panel._price_ticker_label.text() == "ETHUSDT 2,450.12"
    assert "#0ECB81" in panel._price_ticker_label.styleSheet()


def test_ws_status_reflects_the_view_model(qapp, panel, view_model):
    view_model.set_ws_status("WS: LIVE", "#0ECB81")
    qapp.processEvents()

    assert panel._ws_status_label.text() == "WS: LIVE"
    assert "#0ECB81" in panel._ws_status_label.styleSheet()
    assert "#0ECB81" in panel._ws_dot.styleSheet()


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

    card = next(c for c in panel._symbol_picker._cards if c.entry.symbol == "ETHBTC")
    card.clicked.emit()
    qapp.processEvents()

    assert view_model.symbol == "ETHBTC"
    assert panel._btn_symbol.text() == "ETHBTC"
    assert panel._symbol_preferences.recents == ("ETHBTC",)


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

    assert panel._time_range_dialog._widget_vm.fromText == "2026-07-01 00:00"
    assert panel._time_range_dialog._widget_vm.toText == "2026-07-08 00:00"
    panel._time_range_dialog.close()


def test_the_picker_falls_back_to_a_1m_summary(qapp, panel):
    """`DashboardQmlViewModel` exposes no per-timeframe concept this panel
    can read (unlike Data Management's `selectedInterval`) — see the
    `_FALLBACK_TIMEFRAME_*` constants in `dev_board_panel.py`."""
    panel._btn_pick_range.click()
    qapp.processEvents()

    dialog = panel._time_range_dialog
    assert dialog._widget_vm._get_timeframe_seconds() == 60
    assert dialog._widget_vm._get_timeframe_label() == "1m"
    dialog.close()


def test_applying_writes_both_fields_and_the_view_model(qapp, panel, view_model):
    panel._btn_pick_range.click()
    qapp.processEvents()

    dialog = panel._time_range_dialog
    dialog._widget_vm.choosePreset("7d")
    qapp.processEvents()
    dialog._widget_vm.apply()
    qapp.processEvents()

    assert view_model.startDate == panel._txt_start_date.text()
    assert view_model.endDate == panel._txt_end_date.text()
    assert view_model.startDate != ""
    assert view_model.endDate != ""
    assert not dialog.isVisible()
