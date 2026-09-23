from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_catalog import (
    IndicatorScriptCatalog,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_20_script import (
    Ema20Script,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.macd_full_script import (
    MacdFullScript,
)


def _registry() -> IndicatorScriptRegistry:
    registry = IndicatorScriptRegistry()
    registry.register("ema_20", Ema20Script)
    registry.register("macd_full", MacdFullScript)
    return registry


def test_params_form_shows_the_declared_default_with_no_saved_values():
    catalog = IndicatorScriptCatalog(_registry())

    groups = catalog.params_form("ema_20", {})

    fields = groups[0].fields
    period_field = next(f for f in fields if f.name == "period")
    assert period_field.default == 20
    assert period_field.value == 20


def test_params_form_shows_a_saved_value_over_the_default():
    catalog = IndicatorScriptCatalog(_registry())

    groups = catalog.params_form("ema_20", {"period": 55})

    period_field = groups[0].fields[0]
    assert period_field.default == 20
    assert period_field.value == 55


def test_params_form_groups_macd_fields_together():
    catalog = IndicatorScriptCatalog(_registry())

    groups = catalog.params_form("macd_full", {})

    assert len(groups) == 1
    names = {field.name for field in groups[0].fields}
    assert names == {"fast_period", "slow_period", "signal_period"}


def test_validate_params_accepts_a_valid_period():
    catalog = IndicatorScriptCatalog(_registry())

    result = catalog.validate_params("ema_20", {"period": "42"})

    assert result.accepted
    assert result.values == {"period": 42}


def test_validate_params_rejects_a_period_below_the_scripts_own_minval():
    catalog = IndicatorScriptCatalog(_registry())

    result = catalog.validate_params("ema_20", {"period": "0"})

    assert not result.accepted


def test_validate_params_unknown_key_raises():
    catalog = IndicatorScriptCatalog(_registry())

    try:
        catalog.validate_params("no_such_script", {})
    except KeyError:
        return
    raise AssertionError("expected KeyError for an unregistered script key")
