"""The Run setup panel's drop-down fields (`EPIC-033L` stage 3).

Restated from the picker dialogs they replace (`StrategyPickerDialog`,
`TimezonePickerDialog`, the Backtest timeframe picker): what each field
offers, that the current value is the one selected, that a person's choice
writes the view model, and that a view model change moves the field. A
fifth promise is new: the range field's "Custom…" asks for the dates
instead of applying a range nobody chose.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.time_range_preset import (
    TimeRangePreset,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.run_setup_panel import (
    RunSetupPanel,
)

_STRATEGIES = [
    {"key": "ema_pullback", "name": "EMA trend pullback"},
    {"key": "macd_cross", "name": "MACD cross"},
    {"key": "buy_hold", "name": "Buy & hold"},
]


@pytest.fixture
def view_model() -> BackTestViewModel:
    vm = BackTestViewModel()
    # The Presenter fills the catalogue from the registry; a bare view model
    # offers none, and a test over an empty list covers nothing.
    vm.strategy_params.set_strategy_options(list(_STRATEGIES))
    return vm


def _items(combo) -> list[tuple[str, str]]:
    return [(combo.itemText(i), combo.itemData(i)) for i in range(combo.count())]


def _choose(combo, value: str) -> None:
    """What a person's pick does: the item becomes current and `activated`
    fires with it, even when it was already current."""
    index = combo.findData(value)
    assert index >= 0, value
    combo.setCurrentIndex(index)
    combo.activated.emit(index)


# --- strategy ---------------------------------------------------------------


def test_the_strategy_field_offers_the_catalogue_by_name(qapp, view_model):
    panel = RunSetupPanel(view_model)

    assert _items(panel.strategy) == [
        ("EMA trend pullback", "ema_pullback"),
        ("MACD cross", "macd_cross"),
        # Verbatim: a combo box item has no access key to escape.
        ("Buy & hold", "buy_hold"),
    ]


def test_choosing_a_strategy_writes_its_key(qapp, view_model):
    panel = RunSetupPanel(view_model)

    _choose(panel.strategy, "macd_cross")

    assert view_model.strategy_params.selectedStrategyKey == "macd_cross"


def test_the_strategy_field_follows_the_view_model(qapp, view_model):
    panel = RunSetupPanel(view_model)

    view_model.strategy_params.selectedStrategyKey = "buy_hold"

    assert panel.strategy.currentData() == "buy_hold"


def test_a_catalogue_that_changes_is_offered(qapp, view_model):
    """The registry is read after the view is built, and read again; a new
    catalogue keeps the selected strategy, so only the catalogue's own
    signal can tell the field."""
    panel = RunSetupPanel(view_model)

    view_model.strategy_params.set_strategy_options(_STRATEGIES[:1])

    assert _items(panel.strategy) == [("EMA trend pullback", "ema_pullback")]


# --- timeframe --------------------------------------------------------------


def test_the_timeframe_field_offers_every_timeframe(qapp, view_model):
    """`EPIC-014`: all sixteen the domain declares, not the chart toolbar's
    five; the real number too, so a regression to the short list fails."""
    panel = RunSetupPanel(view_model)

    codes = [code for _text, code in _items(panel.timeframe)]
    assert codes == list(view_model.timeframeOptions)
    assert len(codes) == 16


def test_choosing_a_timeframe_writes_it_and_a_change_moves_the_field(qapp, view_model):
    panel = RunSetupPanel(view_model)

    _choose(panel.timeframe, "4h")
    assert view_model.selectedTimeframe == "4h"

    view_model.selectedTimeframe = "15m"
    assert panel.timeframe.currentData() == "15m"


# --- time zone --------------------------------------------------------------


def test_the_time_zone_field_offers_every_supported_zone(qapp, view_model):
    panel = RunSetupPanel(view_model)

    zones = [zone for _text, zone in _items(panel.timezone)]
    assert zones == [
        option["id"] for option in view_model.time_range.displayTimezoneOptions
    ]


def test_choosing_a_time_zone_writes_it_and_a_change_moves_the_field(qapp, view_model):
    panel = RunSetupPanel(view_model)

    _choose(panel.timezone, "Asia/Tokyo")
    assert view_model.time_range.displayTimezone == "Asia/Tokyo"

    view_model.setDisplayTimezone("UTC")
    assert panel.timezone.currentData() == "UTC"


# --- range ------------------------------------------------------------------


def test_the_range_field_offers_the_presets_and_custom_last(qapp, view_model):
    panel = RunSetupPanel(view_model)

    items = _items(panel.time_range)
    assert [value for _text, value in items] == [
        option["value"] for option in view_model.time_range.presetOptions
    ]
    assert items[-1] == ("Custom…", TimeRangePreset.CUSTOM.value)


def test_choosing_a_preset_applies_it(qapp, view_model):
    panel = RunSetupPanel(view_model)
    asked = []
    view_model.openTimeRangePickerRequested.connect(lambda: asked.append(True))

    _choose(panel.time_range, TimeRangePreset.LAST_30_DAYS.value)

    assert view_model.time_range.preset == TimeRangePreset.LAST_30_DAYS.value
    assert asked == []


def test_choosing_custom_asks_for_the_dates_and_keeps_the_range_in_effect(
    qapp, view_model
):
    """Nothing changes until dates are applied, so the field goes back to the
    range a run would still use: a "Custom…" shown over an unchanged preset
    would be a range nobody chose."""
    view_model.time_range.preset = TimeRangePreset.LAST_90_DAYS.value
    panel = RunSetupPanel(view_model)
    asked = []
    view_model.openTimeRangePickerRequested.connect(lambda: asked.append(True))

    _choose(panel.time_range, TimeRangePreset.CUSTOM.value)

    assert asked == [True]
    assert view_model.time_range.preset == TimeRangePreset.LAST_90_DAYS.value
    assert panel.time_range.currentData() == TimeRangePreset.LAST_90_DAYS.value


def test_an_applied_custom_range_shows_as_custom_with_its_dates(qapp, view_model):
    panel = RunSetupPanel(view_model)

    view_model.time_range.customStartText = "2026-01-01 00:00"
    view_model.time_range.customEndText = "2026-02-01 00:00"
    view_model.time_range.preset = TimeRangePreset.CUSTOM.value

    assert panel.time_range.currentData() == TimeRangePreset.CUSTOM.value
    assert panel.time_range.toolTip() == "2026-01-01 00:00 to 2026-02-01 00:00"


def test_choosing_custom_again_asks_again(qapp, view_model):
    """The way to change the dates of a custom range is to choose it again:
    `activated` fires even for the item already current."""
    view_model.time_range.preset = TimeRangePreset.CUSTOM.value
    panel = RunSetupPanel(view_model)
    asked = []
    view_model.openTimeRangePickerRequested.connect(lambda: asked.append(True))

    _choose(panel.time_range, TimeRangePreset.CUSTOM.value)

    assert asked == [True]
