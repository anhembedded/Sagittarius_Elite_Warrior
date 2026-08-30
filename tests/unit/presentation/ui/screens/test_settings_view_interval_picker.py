"""`DEFAULT_INTERVAL` on Settings, after `EPIC-014`.

It was a free-text field, and a wrong value in it failed *silently*:
`BackTestPresenter` checked the config value against a list and simply ignored
anything not in it, so a typo left the app on `1m` with no message anywhere.
Until this epic the list it checked against was the chart toolbar's five-pill
tuple, so `"4h"` — a perfectly valid timeframe — was among the values dropped.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_view import (
    SettingsView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_view_model import (
    SettingsViewModel,
)


@pytest.fixture
def view_model():
    vm = SettingsViewModel()
    vm.defaultInterval = "1m"
    return vm


@pytest.fixture
def view(qapp, view_model):
    widget = SettingsView()
    widget.set_view_model(view_model)
    qapp.processEvents()
    return widget


def test_the_field_shows_the_current_default(view):
    assert view._btn_default_interval.text() == "1m"


def test_the_field_follows_the_view_model(qapp, view, view_model):
    view_model.defaultInterval = "4h"
    qapp.processEvents()

    assert view._btn_default_interval.text() == "4h"


def test_choosing_a_timeframe_writes_through(qapp, view, view_model):
    view._btn_default_interval.click()
    qapp.processEvents()

    view._interval_picker._widget_vm.choose("4h")
    qapp.processEvents()

    assert view_model.defaultInterval == "4h"
    assert view._btn_default_interval.text() == "4h"


def test_every_domain_timeframe_is_a_legal_default(qapp, view):
    """The config key accepts what the domain declares — no longer a subset
    decided by a constant that sizes a chart header."""
    view._btn_default_interval.click()
    qapp.processEvents()

    codes = [
        row["code"]
        for group in view._interval_picker._widget_vm.groups
        for row in group["rows"]
    ]
    assert sorted(codes) == sorted(member.value for member in TimeFrame)
    view._interval_picker.close()
