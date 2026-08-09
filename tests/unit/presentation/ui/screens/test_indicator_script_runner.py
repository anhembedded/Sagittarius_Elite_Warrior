"""
Tests for IndicatorScriptRunner (BOT-032 Phase 2) — the collaborator that runs
custom indicator scripts and puts their lines on the chart.

No Qt needed: the runner reports through plain callbacks, which is exactly the
property that lets the presenter use it from both threads. Real scripts and a
real registry are used (they are pure state with no I/O); only the chart card
is a mock, because it is the genuine external boundary here.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from Binace_Bot.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.indicator_scripts import EmaRibbonScript, MacdFullScript
from Binace_Bot.src.presentation.ui.screens.dashboard.indicator_script_runner import (
    IndicatorScriptRunner,
    qualified_line_name,
    split_line_name,
)


def make_candle(close: float, index: int) -> MarketData:
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


@pytest.fixture
def emitted() -> list:
    return []


@pytest.fixture
def errors() -> list:
    return []


@pytest.fixture
def runner(emitted, errors) -> IndicatorScriptRunner:
    registry = IndicatorScriptRegistry()
    registry.register("ema_ribbon", EmaRibbonScript)
    registry.register("macd_full", MacdFullScript)
    return IndicatorScriptRunner(
        registry=registry,
        emit_line=lambda name, x, y: emitted.append((name, list(x), list(y))),
        on_error=errors.append,
    )


# ---------------------------------------------------------------------------
# Curve naming
# ---------------------------------------------------------------------------


def test_curve_names_are_namespaced_by_script_key():
    assert qualified_line_name("ema_ribbon", "EMA 20") == "ema_ribbon:EMA 20"


def test_a_bare_name_is_recognised_as_a_built_in_indicator():
    """Built-in RSI/EMA/MACD curves have no separator — that is the only thing
    keeping the two systems apart, so it must not be ambiguous."""
    assert split_line_name("EMA(20)") is None
    assert split_line_name("ema_ribbon:EMA 20") == ("ema_ribbon", "EMA 20")


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def test_rebuild_instantiates_only_the_enabled_scripts(runner):
    runner.rebuild(["ema_ribbon"])

    assert set(runner.active) == {"ema_ribbon"}
    assert runner.active["ema_ribbon"].overlay is True


def test_rebuild_with_nothing_enabled_runs_nothing(runner):
    runner.rebuild([])

    assert runner.active == {}


def test_rebuild_hands_out_a_fresh_instance_each_time(runner):
    """Indicators keep warm-up state and have no reset(), so reusing an
    instance across runs would carry stale history into the new one."""
    runner.rebuild(["ema_ribbon"])
    first = runner.active["ema_ribbon"].script
    runner.rebuild(["ema_ribbon"])

    assert runner.active["ema_ribbon"].script is not first


def test_unknown_key_is_reported_without_aborting_the_rest(runner, errors):
    runner.rebuild(["does_not_exist", "ema_ribbon"])

    assert set(runner.active) == {"ema_ribbon"}
    assert any("does_not_exist" in message for message in errors)


def test_clear_removes_every_registered_curve_from_the_chart(runner):
    card = MagicMock()
    runner.rebuild(["ema_ribbon"])
    runner.active["ema_ribbon"].registered_lines = {"EMA 20", "EMA 50"}

    runner.clear_from_chart(card)

    removed = {call.args[0] for call in card.remove_indicator.call_args_list}
    assert removed == {"ema_ribbon:EMA 20", "ema_ribbon:EMA 50"}


# ---------------------------------------------------------------------------
# Feeding bars
# ---------------------------------------------------------------------------


def test_feeding_bars_emits_each_line_under_its_namespaced_name(runner, emitted):
    runner.rebuild(["ema_ribbon"])

    runner.feed_all(make_candle(100.0 + index, index) for index in range(30))

    names = {name for name, _, _ in emitted}
    assert "ema_ribbon:EMA 20" in names
    assert all(name.startswith("ema_ribbon:") for name in names)


def test_slow_lines_emit_nothing_until_warmed_up(runner, emitted):
    """EMA(200) needs 200 bars; emitting a placeholder would draw a fake line."""
    runner.rebuild(["ema_ribbon"])

    runner.feed_all(make_candle(100.0 + index, index) for index in range(30))

    assert not any(name.endswith("EMA 200") for name, _, _ in emitted)


def test_each_emission_carries_the_full_series_so_far(runner, emitted):
    """ChartCard.update_indicator_data() replaces the curve's data rather than
    appending, so a partial series would truncate the drawn line."""
    runner.rebuild(["ema_ribbon"])

    runner.feed_all(make_candle(100.0 + index, index) for index in range(25))

    ema20 = [(x, y) for name, x, y in emitted if name == "ema_ribbon:EMA 20"]
    assert len(ema20[-1][0]) == len(ema20)
    assert len(ema20[-1][0]) > len(ema20[0][0])


def test_feeding_nothing_enabled_emits_nothing(runner, emitted):
    runner.rebuild([])

    runner.feed(make_candle(100.0, 0))

    assert emitted == []


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------


def test_draw_adds_an_overlay_curve_once_then_only_updates(runner):
    card = MagicMock()
    runner.rebuild(["ema_ribbon"])
    runner.feed(make_candle(100.0, 0))  # populates line colours

    assert runner.draw(card, "ema_ribbon:EMA 20", [1.0], [100.0]) is True
    assert runner.draw(card, "ema_ribbon:EMA 20", [1.0, 2.0], [100.0, 101.0]) is True

    assert card.add_overlay_indicator.call_count == 1
    assert card.update_indicator_data.call_count == 2


def test_a_non_overlay_script_draws_on_its_own_subplot(runner):
    card = MagicMock()
    runner.rebuild(["macd_full"])
    # MACD(12/26/9) needs ~35 bars before it produces anything at all, so a
    # single bar would leave it with no lines and nothing to colour.
    runner.feed_all(make_candle(100.0 + index, index) for index in range(60))

    runner.draw(card, "macd_full:MACD", [1.0], [0.5])

    card.add_subplot_indicator.assert_called_once()
    card.add_overlay_indicator.assert_not_called()


def test_draw_declines_a_built_in_indicator_curve(runner):
    """Returning False is how the presenter knows to fall through to its own
    built-in indicator handling."""
    card = MagicMock()
    runner.rebuild(["ema_ribbon"])

    assert runner.draw(card, "EMA(20)", [1.0], [100.0]) is False
    card.add_overlay_indicator.assert_not_called()


def test_draw_declines_a_script_that_is_no_longer_active(runner):
    """A line can still be in flight from a background load after the user
    disabled its script — it must be dropped, not drawn."""
    card = MagicMock()
    runner.rebuild([])

    assert runner.draw(card, "ema_ribbon:EMA 20", [1.0], [100.0]) is False


def test_draw_declines_before_the_script_has_produced_a_colour(runner):
    """Colours only exist after the first bar; drawing earlier would need a
    made-up colour."""
    card = MagicMock()
    runner.rebuild(["ema_ribbon"])

    assert runner.draw(card, "ema_ribbon:EMA 20", [1.0], [100.0]) is False
