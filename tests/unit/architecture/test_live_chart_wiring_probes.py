"""`EPIC-034I` — the checks of `test_every_live_chart_goes_through_the_live_chart.py`
do find what they are there to find: each probe feeds one a source it must catch
and one it must let by.

Retire when: `test_every_live_chart_goes_through_the_live_chart.py` is."""

from __future__ import annotations

import ast

import pytest

from .live_chart_wiring import live_chart_classes, live_sources, wiring_violations

_CHARTS = {"LiveCandleChart", "BotChart", "DeskChart", "MarketChart"}


def _found(source: str) -> list[str]:
    return wiring_violations(source, _CHARTS)


# -- what it must catch -------------------------------------------------------


def test_a_chart_card_built_beside_a_market_stream_is_caught() -> None:
    source = (
        "from m.market_data.contracts.i_market_stream import IMarketStream\n"
        "from s.support.charting.chart_card import ChartCard\n"
        "class Tab:\n"
        "    def __init__(self, stream: IMarketStream) -> None:\n"
        "        self.card = ChartCard('BTCUSDT')\n"
    )

    (hit,) = _found(source)

    assert "(R2)" in hit
    assert "IMarketStream" in hit


def test_a_candle_pushed_from_a_tick_handler_is_caught() -> None:
    source = (
        "from m.market_data.contracts.events import MarketTickEvent\n"
        "def on_tick(card, event: MarketTickEvent) -> None:\n"
        "    card.update_last_candle(1, 2, 3, 4, 5)\n"
    )

    (hit,) = _found(source)

    assert "(R1)" in hit


@pytest.mark.parametrize(
    "method", ["append_closed_candle", "update_last_volume", "append_closed_volume"]
)
def test_every_push_method_is_seen(method: str) -> None:
    source = f"from m import SpotCandleFeed\ndef f(card):\n    card.{method}(1, 2)\n"

    assert any("(R1)" in hit for hit in _found(source))


def test_a_new_feed_named_by_the_shape_is_caught_without_naming_it() -> None:
    source = (
        "from m import SpreadTickFeed\nfrom s import ChartCard\ncard = ChartCard('X')\n"
    )

    assert any("SpreadTickFeed" in hit for hit in _found(source))


def test_a_raw_websocket_beside_a_chart_is_caught() -> None:
    source = "import websockets\nfrom s import ChartCard\ncard = ChartCard('X')\n"

    assert any("websockets" in hit for hit in _found(source))


def test_a_binance_socket_manager_import_is_a_live_source() -> None:
    tree = ast.parse("from binance.ws.streams import ThreadedWebsocketManager\n")

    assert live_sources(tree) == ["binance.ws.streams"]


def test_starting_a_candle_stream_outside_the_coordinator_is_caught() -> None:
    source = "def go(feed):\n    feed.start_stream('owner', 'BTCUSDT', 1)\n"

    (hit,) = _found(source)

    assert "(R4)" in hit


def test_a_chart_built_on_something_that_merely_resembles_a_live_chart_is_caught() -> (
    None
):
    source = (
        "from m import IMarketStream\n"
        "from s import ChartCard, LiveChartLikeThing\n"
        "card = ChartCard('X')\n"
    )

    assert any("(R2)" in hit for hit in _found(source))


# -- what it must let by, by shape ---------------------------------------------


def test_a_chart_of_stored_candles_is_let_by_because_it_refers_to_no_live_source() -> (
    None
):
    """The backtest's shape: stored klines drawn once."""
    source = (
        "from m.market_data.contracts.i_historical_klines import IHistoricalKlines\n"
        "from s import ChartCard\n"
        "def draw(klines: IHistoricalKlines):\n"
        "    card = ChartCard('BTCUSDT')\n"
        "    card.render_historical_data(klines.load())\n"
    )

    assert _found(source) == []


def test_a_chart_of_equity_samples_is_let_by_because_it_refers_to_no_live_source() -> (
    None
):
    """The Desk equity chart's shape: samples pushed as they are taken."""
    source = (
        "from m import EquityCurve\n"
        "def on_sample(chart, sample):\n"
        "    chart.append_closed_candle(*sample_to_candle(sample))\n"
    )

    assert _found(source) == []


def test_a_chart_built_through_a_live_chart_is_let_by_beside_its_source() -> None:
    source = (
        "from m import ICandleFeed\n"
        "from s import ChartCard, BotChart\n"
        "card = ChartCard('X')\n"
        "chart = BotChart(card, ports)\n"
    )

    assert _found(source) == []


def test_a_file_with_a_source_and_no_chart_is_let_by() -> None:
    source = (
        "from m import IMarketStream\nclass Watchlist:\n    stream: IMarketStream\n"
    )

    assert _found(source) == []


def test_a_stream_name_that_only_looks_like_one_is_let_by() -> None:
    assert live_sources(ast.parse("from m import Streamline, MarketStreamer\n")) == []


# -- the subclass walk ----------------------------------------------------------


def test_the_walk_finds_a_chart_built_on_a_chart_built_on_the_live_chart() -> None:
    sources = [
        "class LiveCandleChart(QObject): ...",
        "class BotChart(LiveCandleChart): ...",
        "class GridBotChart(BotChart): ...",
        "class Other(QObject): ...",
    ]

    assert live_chart_classes(sources) == {
        "LiveCandleChart",
        "BotChart",
        "GridBotChart",
    }


def test_a_chart_built_on_a_subclass_found_by_the_walk_is_let_by() -> None:
    charts = live_chart_classes(
        ["class LiveCandleChart: ...", "class GridBotChart(LiveCandleChart): ..."]
    )
    source = (
        "from m import ICandleFeed\nfrom s import ChartCard, GridBotChart\n"
        "card = ChartCard('X')\nchart = GridBotChart(card)\n"
    )

    assert wiring_violations(source, charts) == []
