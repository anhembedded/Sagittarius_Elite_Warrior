"""Data Management's "Chọn lịch" button, after `EPIC-015`.

Replaces `pick_date_range()` (`components/date_range_picker.py`, now
deleted) with the standalone `TimeRangePicker.qml` behind
`TimeRangeCardWidget._on_pick_range()`. `TimeRangeCardWidget` itself holds
no ViewModel reference (every other setter on it is the same push-down
shape — see its docstring), so these tests exercise it the way
`DataManagementView` actually wires it: through `set_view_model()`.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view import (
    DataManagementView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view_model import (
    DataManagementViewModel,
)


@pytest.fixture
def view_model():
    vm = DataManagementViewModel()
    vm.selectedInterval = "5m"
    vm.useCustomTime = True
    vm.fromDateTime = "2026-07-01 00:00"
    vm.toDateTime = "2026-07-08 00:00"
    return vm


@pytest.fixture
def view(qapp, view_model, request):
    widget = DataManagementView()
    widget.set_view_model(view_model)
    qapp.processEvents()
    request.addfinalizer(widget.deleteLater)
    return widget


def test_the_active_interval_drives_the_pickers_timeframe_summary(view):
    """`selectedInterval` is a real, live timeframe concept on this screen
    (unlike Dev Board's) — the picker must read it, not a hardcoded default."""
    card = view._time_range

    assert card._get_timeframe_seconds() == 300
    assert card._get_timeframe_label() == "5m"


def test_the_timeframe_source_follows_later_interval_changes(qapp, view, view_model):
    view_model.selectedInterval = "1h"
    qapp.processEvents()

    assert view._time_range._get_timeframe_seconds() == 3600
    assert view._time_range._get_timeframe_label() == "1h"


def test_opening_the_dialog_seeds_from_the_current_fields(qapp, view):
    card = view._time_range
    card._btn_pick_range.click()
    qapp.processEvents()

    assert card._range_dialog._widget_vm.fromText == "2026-07-01 00:00"
    assert card._range_dialog._widget_vm.toText == "2026-07-08 00:00"
    card._range_dialog.close()


def test_applying_writes_both_fields_and_the_view_model(qapp, view, view_model):
    card = view._time_range
    card._btn_pick_range.click()
    qapp.processEvents()

    card._range_dialog._widget_vm.choosePreset("7d")
    qapp.processEvents()
    card._range_dialog._widget_vm.apply()
    qapp.processEvents()

    assert view_model.fromDateTime == card._from_field.text()
    assert view_model.toDateTime == card._to_field.text()
    assert view_model.fromDateTime != ""
    assert view_model.toDateTime != ""


def test_a_bare_widget_with_no_view_model_falls_back_to_a_1m_summary(qapp):
    """No `DataManagementView` around it — the fallback this widget ships
    with before `set_timeframe_source()` is ever called."""
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_widgets import (
        TimeRangeCardWidget,
    )

    card = TimeRangeCardWidget()

    assert card._get_timeframe_seconds() == 60
    assert card._get_timeframe_label() == "1m"
