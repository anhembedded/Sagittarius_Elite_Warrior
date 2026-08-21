"""
BOT-044 regression guard: adding the `input_*()` mechanism to
BaseIndicatorScript must not change how any *shipped* script behaves.

BOT-048 converted the fixed-period scripts (ema_20/50/100/200, rsi_14,
macd_full) to declare their period(s) as input_int() — each with a default
equal to its old hardcoded value, so behavior is unchanged. Those six now
have their own schema assertions below (`INPUT_DECLARING_SCRIPTS`); the
remaining three (ema_ribbon, ema_cross, the dev showcase script) still
declare nothing and stay pinned by the original "no inputs yet" checks
(`NO_INPUT_SCRIPTS`).
"""

from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts import (
    DevIndicatorScript,
    Ema20Script,
    Ema50Script,
    Ema100Script,
    Ema200Script,
    EmaCrossScript,
    EmaRibbonScript,
    MacdFullScript,
    Rsi14Script,
)
from Sagittarius_Elite_Warrior.src.domain.scripting import InputKind

#: The nine scripts BinanceBotModule registers today.
SHIPPED_SCRIPTS = [
    Rsi14Script,
    Ema20Script,
    Ema50Script,
    Ema100Script,
    Ema200Script,
    MacdFullScript,
    EmaRibbonScript,
    EmaCrossScript,
    DevIndicatorScript,
]

#: Never declared any input — still pinned "nothing changed" (BOT-032
#: Phase 6 default fixed-period scripts, minus the six BOT-048 converted).
NO_INPUT_SCRIPTS = [EmaRibbonScript, EmaCrossScript, DevIndicatorScript]

#: BOT-048 — script class -> {input name: default value}, in declaration
#: order. Used both to assert `.inputs` and to build a valid override dict
#: for the "rejects an undeclared param" check below.
INPUT_DECLARING_SCRIPTS: dict[type, dict[str, int]] = {
    Rsi14Script: {"period": 14},
    Ema20Script: {"period": 20},
    Ema50Script: {"period": 50},
    Ema100Script: {"period": 100},
    Ema200Script: {"period": 200},
    MacdFullScript: {"fast_period": 12, "slow_period": 26, "signal_period": 9},
}


def _candle(close: float, index: int) -> MarketData:
    open_time = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(minutes=index)
    return MarketData(
        symbol="ETHUSDT",
        interval="1m",
        open_time=open_time,
        open_price=close,
        high_price=close + 1,
        low_price=close - 1,
        close_price=close,
        volume=10.0,
        close_time=open_time + timedelta(minutes=1),
        quote_asset_volume=1000.0,
        number_of_trades=5,
        taker_buy_base_asset_volume=5.0,
        taker_buy_quote_asset_volume=500.0,
    )


def _run(script, bar_count: int = 60) -> dict:
    """Feeds a rising-then-falling series and returns the final bar's lines."""
    last: dict = {}
    for index in range(bar_count):
        close = 100.0 + index if index < bar_count // 2 else 100.0 + bar_count - index
        last = script.compute(_candle(close, index))
    return last


@pytest.mark.parametrize("script_cls", NO_INPUT_SCRIPTS, ids=lambda c: c.__name__)
def test_every_no_input_script_declares_no_inputs(script_cls):
    assert script_cls().inputs == ()


@pytest.mark.parametrize("script_cls", NO_INPUT_SCRIPTS, ids=lambda c: c.__name__)
def test_every_no_input_script_constructs_with_explicit_empty_params(script_cls):
    """`create(key)` and `create(key, {})` must be interchangeable — an empty
    mapping is not the same object as None, and the code path differs."""
    assert script_cls({}).inputs == ()


@pytest.mark.parametrize("script_cls", SHIPPED_SCRIPTS, ids=lambda c: c.__name__)
def test_every_shipped_script_produces_identical_output_with_and_without_params(
    script_cls,
):
    """The real regression check: same inputs, same plotted values, whether
    constructed the old way or through the new params-aware path. Holds for
    all nine scripts, whether or not they declare inputs — `{}` always means
    "every declared default", same as `None`."""
    without = _run(script_cls())
    with_empty = _run(script_cls({}))

    assert without.keys() == with_empty.keys()
    for name, line in without.items():
        assert line.value == with_empty[name].value, f"line {name!r} changed"


@pytest.mark.parametrize("script_cls", NO_INPUT_SCRIPTS, ids=lambda c: c.__name__)
def test_no_input_script_rejects_any_param(script_cls):
    with pytest.raises(ValueError, match="never declares"):
        script_cls({"period": 99})


@pytest.mark.parametrize(
    "script_cls", INPUT_DECLARING_SCRIPTS.keys(), ids=lambda c: c.__name__
)
def test_converted_script_declares_its_period_inputs_with_the_old_hardcoded_default(
    script_cls,
):
    """BOT-048: each converted script's `.inputs` must report exactly the
    names it used to hardcode, defaulting to the value it used to hardcode —
    the whole point of this conversion is that nothing visibly changes."""
    expected_defaults = INPUT_DECLARING_SCRIPTS[script_cls]
    declared = {spec.name: spec for spec in script_cls().inputs}

    assert set(declared) == set(expected_defaults)
    for name, expected_default in expected_defaults.items():
        assert declared[name].default == expected_default
        assert declared[name].kind == InputKind.INT
        assert declared[name].minval is not None and declared[name].minval >= 1


@pytest.mark.parametrize(
    "script_cls", INPUT_DECLARING_SCRIPTS.keys(), ids=lambda c: c.__name__
)
def test_converted_script_rejects_a_truly_undeclared_param(script_cls):
    with pytest.raises(ValueError, match="never declares"):
        script_cls({"bogus_param_nobody_declares": 1})
