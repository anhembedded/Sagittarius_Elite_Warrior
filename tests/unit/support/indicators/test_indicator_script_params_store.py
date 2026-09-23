from __future__ import annotations

import json
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_params_store import (
    IndicatorScriptParamsStore,
)


def _config(initial: str = "") -> Mock:
    """`spec=["get", "set"]` — a bare `IConfig` port has no `.save()`
    (`LiveStrategyConfigStore`'s own docstring: that method belongs to
    `ConfigManager`), so a plain unrestricted `Mock()` would silently
    exercise a code path no real minimal `IConfig` implementation has."""
    state = {ConfigKeys.DASHBOARD_INDICATOR_SCRIPT_PARAMS.value: initial}
    config = Mock(spec=["get", "set"])
    config.get.side_effect = lambda key, default="": state.get(key, default)
    config.set.side_effect = lambda key, value: state.__setitem__(key, value)
    return config


def test_load_all_is_empty_with_nothing_saved():
    store = IndicatorScriptParamsStore(_config())

    assert store.load_all() == {}


def test_save_then_load_all_round_trips():
    config = _config()
    store = IndicatorScriptParamsStore(config)

    store.save("ema_20", {"period": 55})

    assert store.load_all() == {"ema_20": {"period": 55}}


def test_saving_a_second_key_does_not_clobber_the_first():
    config = _config()
    store = IndicatorScriptParamsStore(config)

    store.save("ema_20", {"period": 55})
    store.save("macd_full", {"fast_period": 10})

    assert store.load_all() == {
        "ema_20": {"period": 55},
        "macd_full": {"fast_period": 10},
    }


def test_saving_the_same_key_again_overwrites_only_that_key():
    config = _config()
    store = IndicatorScriptParamsStore(config)

    store.save("ema_20", {"period": 55})
    store.save("ema_20", {"period": 77})

    assert store.load_all() == {"ema_20": {"period": 77}}


def test_malformed_json_is_treated_as_empty():
    store = IndicatorScriptParamsStore(_config(initial="{not json"))

    assert store.load_all() == {}


def test_a_non_dict_entry_is_dropped():
    store = IndicatorScriptParamsStore(
        _config(initial=json.dumps({"ema_20": {"period": 55}, "bad": "not_a_dict"}))
    )

    assert store.load_all() == {"ema_20": {"period": 55}}


def test_save_never_raises_when_the_config_has_no_save_method():
    """`_config()`'s `spec=["get", "set"]` has no `.save` at all — this
    documents that `getattr(self._config, "save", None)` is load-bearing,
    not just defensive dead code."""
    store = IndicatorScriptParamsStore(_config())

    store.save("ema_20", {"period": 55})  # must not raise


def test_save_persists_when_the_config_supports_it():
    state = {ConfigKeys.DASHBOARD_INDICATOR_SCRIPT_PARAMS.value: ""}
    config = Mock(spec=["get", "set", "save"])
    config.get.side_effect = lambda key, default="": state.get(key, default)
    config.set.side_effect = lambda key, value: state.__setitem__(key, value)
    store = IndicatorScriptParamsStore(config)

    store.save("ema_20", {"period": 55})

    config.save.assert_called_once()
