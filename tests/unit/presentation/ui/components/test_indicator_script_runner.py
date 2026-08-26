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
from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts import (
    BaseIndicatorScript,
    DevIndicatorScript,
    EmaCrossScript,
    EmaRibbonScript,
    MacdFullScript,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.indicator_scripts.runner import (
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
def regions() -> list:
    return []


@pytest.fixture
def infos() -> list:
    return []


@pytest.fixture
def markers() -> list:
    return []


@pytest.fixture
def errors() -> list:
    return []


class _CrossMarkerScript(BaseIndicatorScript):
    """
    Test-only double for exercising the runner's marker accumulation/plumbing.
    Production scripts no longer mark Buy/Sell on an EMA cross themselves
    (BOT-026 moved that decision to `EmaCrossoverStrategy`) — this stands in
    with the same EMA(12)/EMA(26) shape `EmaCrossScript` used to have, purely
    so `_reversal_candles()` below still produces a marker to observe.
    """

    title = "Test — cross marker"
    overlay = True
    min_warmup_bars = 26

    def setup(self) -> None:
        self.fast = self.ema(12)
        self.slow = self.ema(26)

    def execute(self, candle: MarketData) -> None:
        fast = self.fast(candle.close_price)
        self.slow(candle.close_price)
        if self.crossed_above(self.fast, self.slow):
            self.mark(fast, "Buy", color="#0ECB81", direction="up")
        elif self.crossed_below(self.fast, self.slow):
            self.mark(fast, "Sell", color="#F6465D", direction="down")


@pytest.fixture
def runner(emitted, regions, infos, markers, errors) -> IndicatorScriptRunner:
    registry = IndicatorScriptRegistry()
    registry.register("ema_ribbon", EmaRibbonScript)
    registry.register("macd_full", MacdFullScript)
    registry.register("dev_showcase", DevIndicatorScript)
    registry.register("ema_cross", EmaCrossScript)
    registry.register("cross_marker", _CrossMarkerScript)
    return IndicatorScriptRunner(
        registry=registry,
        emit_line=lambda name, x, y: emitted.append((name, list(x), list(y))),
        emit_region=lambda key, spans: regions.append((key, list(spans))),
        emit_info=lambda key, fields: infos.append((key, list(fields))),
        emit_markers=lambda key, points: markers.append((key, list(points))),
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
    runner.feed(make_candle(100.0, 0), emit=False)  # populates line_colors()
    active = runner.active["ema_ribbon"]
    for line_name in active.script.line_colors():
        runner.draw(card, qualified_line_name("ema_ribbon", line_name), [], [])

    runner.clear_from_chart(card)

    removed = {call.args[0] for call in card.remove_indicator.call_args_list}
    assert removed == {
        "ema_ribbon:EMA 20",
        "ema_ribbon:EMA 50",
        "ema_ribbon:EMA 100",
        "ema_ribbon:EMA 200",
    }


def test_repeated_rebuild_clear_cycles_never_leave_stale_curves_registered(runner):
    """BOT-067 regression (`5a063b5`): clicking Run repeatedly used to leave
    every prior run's curves un-removed — 10 EMA lines survived instead of 4
    after 3 clicks — because clearing walked `registered_lines` by hand.
    ResourceScope makes each run's teardown a property of that run's own
    ActiveScript, so a click can only ever clear its own curves, never a
    stale or already-replaced set. This test must fail if ResourceScope is
    ever removed from clear_from_chart()/draw()."""
    card = MagicMock()
    candle = make_candle(100.0, 0)

    for _ in range(3):
        runner.clear_from_chart(card)  # what _rebuild_scripts() always does first
        runner.rebuild(["ema_ribbon"])
        runner.feed(candle, emit=False)
        active = runner.active["ema_ribbon"]
        for line_name in active.script.line_colors():
            runner.draw(card, qualified_line_name("ema_ribbon", line_name), [], [])

    card.remove_indicator.reset_mock()
    runner.clear_from_chart(card)  # the 4th click's clear — only run 3's lines

    removed = [call.args[0] for call in card.remove_indicator.call_args_list]
    assert len(removed) == 4
    assert len(set(removed)) == 4


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


def test_the_batched_emission_carries_the_full_series(runner, emitted):
    """ChartCard.update_indicator_data() replaces the curve's data rather than
    appending, so a partial series would truncate the drawn line. BOT-036 made
    feed_all() emit once at the end instead of once per bar — that single
    emission must therefore carry every warmed-up point."""
    runner.rebuild(["ema_ribbon"])

    runner.feed_all(make_candle(100.0 + index, index) for index in range(25))

    ema20 = [(x, y) for name, x, y in emitted if name == "ema_ribbon:EMA 20"]
    assert len(ema20) == 1
    x_data, y_data = ema20[0]
    assert len(x_data) == len(y_data)
    assert len(x_data) > 1  # a real series, not a lone point


@pytest.mark.parametrize("candle_count", [50, 500])
def test_feed_all_emits_each_line_exactly_once(runner, emitted, candle_count):
    """BOT-036 regression guard: emissions must be O(1) per line, not O(N) per
    bar. Reintroducing a per-bar emit inside feed_all() fails this immediately,
    at any history size."""
    runner.rebuild(["ema_ribbon"])

    runner.feed_all(make_candle(100.0 + i, i) for i in range(candle_count))

    names = [name for name, _, _ in emitted]
    assert len(names) == len(set(names))


def test_a_live_bar_still_emits_immediately(runner, emitted):
    """feed()'s default emit=True is what DashboardPresenter._on_ui_chart_update
    relies on — batching history must not silently mute the real-time path."""
    runner.rebuild(["ema_ribbon"])
    runner.feed_all(make_candle(100.0 + i, i) for i in range(30))
    before = len(emitted)

    runner.feed(make_candle(200.0, 30))

    assert len(emitted) > before


def test_feed_all_with_no_candles_emits_nothing(runner, emitted):
    """_on_history_prepended can legitimately call feed_all([]) when the DB has
    no older data — that must stay silent, exactly as before BOT-036."""
    runner.rebuild(["ema_ribbon"])

    runner.feed_all([])

    assert emitted == []


def test_feed_all_flushes_all_secondary_channels_exactly_once(
    runner, emitted, regions, infos, markers
):
    """Sanity check: feed_all() must not just batch lines, but also regions,
    info panels, and markers, exactly once per script to avoid O(N) emissions
    on any of those secondary channels."""
    # dev_showcase is known to produce all 4 output types
    runner.rebuild(["dev_showcase"])

    runner.feed_all(make_candle(100.0 + i, i) for i in range(50))

    # Lines: O(1) per line, dev_showcase has multiple lines
    assert len(emitted) > 0
    # Secondary channels: exactly 1 emission per script
    assert len(regions) == 1
    assert len(infos) == 1
    assert len(markers) <= 1


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


def test_a_multi_line_subplot_script_tags_every_line_with_the_same_group(runner):
    """
    Regression test for BUG-053: MacdFullScript fans one reading out into
    three lines (MACD/Signal/Histogram) meant to share a single subplot row
    (see its own docstring: "on their own subplot row" — singular). draw()
    used to call add_subplot_indicator() once per NEW line name with no
    group tag, and ChartPlotLayout.add_subplot() unconditionally creates a
    brand new row on every call — so a 3-line script ended up with 3 stacked
    subplot rows instead of 1, squeezing the main candlestick plot and
    double/triple-registering its crosshair. Tagging every line from the
    same script with a shared `group=key` is what lets ChartCard's
    IndicatorManager reuse one row for the whole script (see
    test_chart_card.py's equivalent row-count regression test for the
    ChartCard-level half of this).
    """
    card = MagicMock()
    runner.rebuild(["macd_full"])
    runner.feed_all(make_candle(100.0 + index, index) for index in range(60))

    runner.draw(card, "macd_full:MACD", [1.0], [0.5])
    runner.draw(card, "macd_full:Signal", [1.0], [0.4])
    runner.draw(card, "macd_full:Histogram", [1.0], [0.1])

    assert card.add_subplot_indicator.call_count == 3
    groups = {
        call.kwargs.get("group") for call in card.add_subplot_indicator.call_args_list
    }
    assert groups == {"macd_full"}


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


# ---------------------------------------------------------------------------
# Regions & info (BOT-032 — background tint / status panel)
# ---------------------------------------------------------------------------


def test_feeding_emits_a_region_snapshot_every_bar(runner, regions):
    """Even bars with no tint must emit — an empty list is how a chart clears
    a span that no longer applies, not a reason to skip the callback."""
    runner.rebuild(["dev_showcase"])

    runner.feed(make_candle(100.0, 0))

    assert any(key == "dev_showcase" for key, _ in regions)


def test_confirmed_trend_produces_a_growing_region_span(runner, regions):
    runner.rebuild(["dev_showcase"])

    runner.feed_all(make_candle(100.0 + index, index) for index in range(40))

    _, last_spans = regions[-1]
    assert len(last_spans) >= 1


def test_feeding_emits_an_info_snapshot_every_bar(runner, infos):
    runner.rebuild(["dev_showcase"])

    runner.feed(make_candle(100.0, 0))

    _, fields = infos[-1]
    labels = {field.label for field in fields}
    assert "Trend" in labels
    assert "Bars confirming" in labels


def test_disabled_script_emits_no_region_or_info(runner, regions, infos):
    runner.rebuild([])

    runner.feed(make_candle(100.0, 0))

    assert regions == []
    assert infos == []


def test_draw_region_forwards_to_the_chart_for_an_active_script(runner):
    card = MagicMock()
    runner.rebuild(["dev_showcase"])

    runner.draw_region(card, "dev_showcase", [(1.0, 61.0, "#0ECB81", 0.08)])

    card.set_script_regions.assert_called_once_with(
        "dev_showcase", [(1.0, 61.0, "#0ECB81", 0.08)]
    )


def test_draw_region_is_a_no_op_for_an_inactive_script(runner):
    card = MagicMock()
    runner.rebuild([])

    runner.draw_region(card, "dev_showcase", [(1.0, 61.0, "#0ECB81", 0.08)])

    card.set_script_regions.assert_not_called()


def test_draw_info_forwards_to_the_chart_for_an_active_script(runner):
    card = MagicMock()
    runner.rebuild(["dev_showcase"])

    runner.draw_info(card, "dev_showcase", [])

    card.set_script_info.assert_called_once_with("dev_showcase", [])


def test_draw_info_is_a_no_op_for_an_inactive_script(runner):
    card = MagicMock()
    runner.rebuild([])

    runner.draw_info(card, "dev_showcase", [])

    card.set_script_info.assert_not_called()


# ---------------------------------------------------------------------------
# Markers (BOT-032 Phase 4a — Buy/Sell labels)
# ---------------------------------------------------------------------------


def _reversal_candles(count: int = 80):
    """A decline then a rally — guarantees at least one EMA(12)/EMA(26) cross."""
    for index in range(count):
        close = (
            200.0 - index
            if index < count // 2
            else 200.0 - (count // 2) + (index - count // 2)
        )
        yield make_candle(close, index)


def test_a_crossover_produces_an_accumulated_marker(runner, markers):
    runner.rebuild(["cross_marker"])

    runner.feed_all(_reversal_candles())

    assert markers, "expected at least one emit_markers call"
    _, last_points = markers[-1]
    assert any(text in ("Buy", "Sell") for _, _, text, _, _ in last_points)


def test_bars_with_no_new_marker_do_not_re_emit(runner, markers):
    """Markers only ever grow — a quiet bar must not resend the same list."""
    runner.rebuild(["cross_marker"])

    runner.feed_all(_reversal_candles())
    emit_count_after_run = len(markers)
    runner.feed(make_candle(500.0, 999))  # one more quiet bar, no new cross

    assert len(markers) == emit_count_after_run


def test_draw_markers_forwards_to_the_chart_for_an_active_script(runner):
    card = MagicMock()
    runner.rebuild(["ema_cross"])

    runner.draw_markers(card, "ema_cross", [(1.0, 100.0, "Buy", "#0ECB81", "up")])

    card.set_script_markers.assert_called_once_with(
        "ema_cross", [(1.0, 100.0, "Buy", "#0ECB81", "up")]
    )


def test_draw_markers_is_a_no_op_for_an_inactive_script(runner):
    card = MagicMock()
    runner.rebuild([])

    runner.draw_markers(card, "ema_cross", [(1.0, 100.0, "Buy", "#0ECB81", "up")])

    card.set_script_markers.assert_not_called()


# ---------------------------------------------------------------------------
# Dynamic Script Add / Remove (BOT-095F)
# ---------------------------------------------------------------------------


def test_add_script_dynamically_registers_and_feeds_candles(runner, emitted):
    runner.rebuild([])
    assert "ema_cross" not in runner.active

    candles = [make_candle(100.0 + i, i) for i in range(30)]
    runner.add_script("ema_cross", candles)

    assert "ema_cross" in runner.active
    assert any(qualified.startswith("ema_cross:") for qualified, _, _ in emitted)


def test_add_script_ignores_duplicate_key(runner, emitted):
    runner.rebuild(["ema_cross"])
    assert "ema_cross" in runner.active

    emitted_count_before = len(emitted)
    runner.add_script("ema_cross", [make_candle(100.0, 0)])

    assert len(emitted) == emitted_count_before


def test_add_script_handles_unknown_key_gracefully(runner, errors):
    runner.rebuild([])
    runner.add_script("non_existent_script")

    assert "non_existent_script" not in runner.active
    assert errors, "expected error callback for unknown script"


def test_remove_script_disposes_resources_and_clears_chart(runner):
    card = MagicMock()
    runner.rebuild(["ema_cross"])
    runner.feed(make_candle(100.0, 0), emit=False)
    runner.draw(card, "ema_cross:EMA 12", [1.0], [100.0])

    assert "ema_cross" in runner.active

    runner.remove_script("ema_cross", card)

    assert "ema_cross" not in runner.active
    card.remove_indicator.assert_called_once_with("ema_cross:EMA 12")
    card.clear_script_regions.assert_called_once_with("ema_cross")
    card.clear_script_info.assert_called_once_with("ema_cross")
    card.clear_script_markers.assert_called_once_with("ema_cross")
