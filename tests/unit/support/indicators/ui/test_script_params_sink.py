from __future__ import annotations

import os
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_catalog import (
    IndicatorScriptCatalog,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_20_script import (
    Ema20Script,
)
from Sagittarius_Elite_Warrior.src.support.indicators.ui.script_params_sink import (
    IndicatorScriptParamsSink,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _sink(saved: dict | None = None) -> tuple[IndicatorScriptParamsSink, Mock]:
    registry = IndicatorScriptRegistry()
    registry.register("ema_20", Ema20Script)
    catalog = IndicatorScriptCatalog(registry)
    store = Mock()
    store.load_all.return_value = {"ema_20": saved} if saved else {}
    sink = IndicatorScriptParamsSink(catalog, store, "ema_20")
    return sink, store


def test_groups_show_the_saved_value_over_the_default(qapp):
    sink, _store = _sink(saved={"period": 77})

    fields = sink.botParamsGroups[0].fields
    period_field = next(f for f in fields if f.name == "period")
    assert period_field.value == 77
    assert period_field.default == 20


def test_save_with_a_valid_value_persists_and_clears_error(qapp):
    sink, store = _sink()

    sink.requestBotParamsSave({"period": "42"})

    assert sink.botParamsError == ""
    store.save.assert_called_once_with("ema_20", {"period": 42})


def test_save_with_an_invalid_value_sets_error_and_never_persists(qapp):
    sink, store = _sink()

    sink.requestBotParamsSave({"period": "not_a_number"})

    assert sink.botParamsError != ""
    store.save.assert_not_called()


def test_save_emits_bot_params_changed(qapp):
    sink, _store = _sink()
    received = []
    sink.botParamsChanged.connect(lambda: received.append(True))

    sink.requestBotParamsSave({"period": "42"})

    assert received == [True]


def test_step_bot_param_value_delegates_to_numeric_step(qapp):
    sink, _store = _sink()

    stepped = sink.step_bot_param_value("period", "20", 1)

    assert stepped == "21"


def test_step_bot_param_value_unknown_field_returns_raw(qapp):
    sink, _store = _sink()

    assert sink.step_bot_param_value("unknown_field", "20", 1) == "20"
