"""
Tests for the param-schema core (BOT-044) — the `input_*()` mechanism that
lets a script declare its own parameters so a UI can build a form from them,
equivalent to Pine Script's input().

Exercised through a real BaseIndicatorScript subclass rather than
InputDeclarations directly, because the declaration API on the base class is
what script authors actually touch.
"""

import pytest
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts import BaseIndicatorScript
from Sagittarius_Elite_Warrior.src.domain.scripting import InputKind


class _ParameterisedScript(BaseIndicatorScript):
    """Declares one of every input kind, including group/suffix/options."""

    title = "Parameterised"
    overlay = True

    def setup(self) -> None:
        self.period = self.input_int(
            "period",
            20,
            label="EMA Period",
            minval=1,
            maxval=200,
            group="Chỉ số Kỹ thuật",
        )
        self.threshold = self.input_float(
            "threshold", 1.5, label="Ngưỡng", minval=0.0, maxval=100.0, suffix="%"
        )
        self.enabled = self.input_bool("enabled", True, label="Bật")
        self.mode = self.input_string(
            "mode", "fast", options=["fast", "slow"], label="Chế độ"
        )
        self.line = self.ema(self.period)

    def execute(self, candle: MarketData) -> None:
        self.plot(self.line(candle.close_price), "LINE", color="#ffffff")


class _NoInputScript(BaseIndicatorScript):
    """A script written the pre-BOT-044 way — declares nothing."""

    title = "No inputs"
    overlay = True

    def setup(self) -> None:
        self.line = self.ema(10)

    def execute(self, candle: MarketData) -> None:
        self.plot(self.line(candle.close_price), "LINE", color="#ffffff")


# --------------------------------------------------------------------------
# Declaration / schema
# --------------------------------------------------------------------------


def test_a_script_declaring_no_inputs_has_an_empty_schema():
    """Every script written before BOT-044 falls in this case — the whole
    point is that they keep working untouched."""
    assert _NoInputScript().inputs == ()


def test_schema_preserves_declaration_order():
    names = [spec.name for spec in _ParameterisedScript().inputs]

    assert names == ["period", "threshold", "enabled", "mode"]


def test_schema_carries_everything_a_form_needs():
    period, threshold, enabled, mode = _ParameterisedScript().inputs

    assert (period.kind, period.label, period.default) == (
        InputKind.INT,
        "EMA Period",
        20,
    )
    assert (period.minval, period.maxval, period.group) == (1, 200, "Chỉ số Kỹ thuật")
    assert (threshold.kind, threshold.suffix) == (InputKind.FLOAT, "%")
    assert (enabled.kind, enabled.default) == (InputKind.BOOL, True)
    assert (mode.kind, mode.options) == (InputKind.STRING, ("fast", "slow"))


def test_label_falls_back_to_the_name_when_not_given():
    class _Script(_NoInputScript):
        def setup(self) -> None:
            self.input_int("fast_period", 12)

    (spec,) = _Script().inputs
    assert spec.label == "fast_period"


def test_declaring_the_same_name_twice_raises():
    class _Script(_NoInputScript):
        def setup(self) -> None:
            self.input_int("period", 10)
            self.input_int("period", 20)

    with pytest.raises(ValueError, match="declared twice"):
        _Script()


# --------------------------------------------------------------------------
# Resolving values
# --------------------------------------------------------------------------


def test_no_params_uses_every_declared_default():
    script = _ParameterisedScript()

    assert (script.period, script.threshold, script.enabled, script.mode) == (
        20,
        1.5,
        True,
        "fast",
    )


def test_supplied_params_override_the_defaults():
    script = _ParameterisedScript(
        {"period": 50, "threshold": 2.5, "enabled": False, "mode": "slow"}
    )

    assert (script.period, script.threshold, script.enabled, script.mode) == (
        50,
        2.5,
        False,
        "slow",
    )


def test_defaults_survive_in_the_schema_after_an_override():
    """ "Khôi phục Mặc định" reads the default off the declaration, so an
    overridden instance must still report the original."""
    script = _ParameterisedScript({"period": 50})

    period = script.inputs[0]
    assert script.period == 50
    assert period.default == 20


def test_an_overridden_period_actually_reaches_the_indicator():
    """Proves the value is used, not just recorded: EMA(2) warms up on the
    2nd bar where the default EMA(20) would still be None."""

    class _Script(_NoInputScript):
        def setup(self) -> None:
            self.line = self.ema(self.input_int("period", 20, minval=1))

        def execute(self, candle: MarketData) -> None:
            self.plot(self.line(candle.close_price), "LINE", color="#ffffff")

    script = _Script({"period": 2})
    script.compute(_candle(100.0, 0))
    last = script.compute(_candle(102.0, 1))

    assert last["LINE"].value == pytest.approx(101.0)


def test_a_param_the_script_never_declares_raises():
    """A typo or a stale saved preset must fail loudly — silently ignoring it
    would leave the user believing a setting took effect."""
    with pytest.raises(ValueError, match="never declares"):
        _ParameterisedScript({"perod": 50})


# --------------------------------------------------------------------------
# Validation — bad values raise instead of being clamped
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"period": 0}, "must be >= 1"),
        ({"period": 500}, "must be <= 200"),
        ({"threshold": -1.0}, "must be >= 0"),
        ({"period": 1.5}, "whole number"),
        ({"period": "20"}, "expects a number"),
        ({"period": True}, "expects a number"),
        ({"enabled": 1}, "expects a bool"),
        ({"mode": "medium"}, "must be one of"),
        ({"mode": 3}, "expects a string"),
    ],
)
def test_invalid_values_raise_rather_than_being_silently_clamped(params, message):
    """A clamped period produces a backtest whose numbers look plausible and
    are wrong — far worse than an error."""
    with pytest.raises(ValueError, match=message):
        _ParameterisedScript(params)


def test_an_int_is_accepted_for_a_float_input():
    script = _ParameterisedScript({"threshold": 2})

    assert script.threshold == 2.0
    assert isinstance(script.threshold, float)


def test_boundary_values_are_accepted():
    assert _ParameterisedScript({"period": 1}).period == 1
    assert _ParameterisedScript({"period": 200}).period == 200


def _candle(close: float, index: int) -> MarketData:
    from datetime import UTC, datetime, timedelta

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
