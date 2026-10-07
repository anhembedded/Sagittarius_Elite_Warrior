"""`BUG-172` — the chart a desk shows is the market of the venue it trades on.

@details Until this bug was fixed every desk read one process-wide market-data
venue (`exchange.market_data_venue`, default `mainnet_public`), so Spot Testnet
and Futures Testnet charted mainnet prices while their orders filled on the
testnet. These tests compose the real app over the fake Binance server and
ask each of the four venues' desk chart ports for candles; nothing is
substituted but the network.

The fake server has no notion of "mainnet" or "testnet": both families of
`python-binance` URLs point at it. To tell which family a read used, only one
family is live at a time and the other points at a closed port, so a read that
went to the wrong environment cannot be answered and the store stays empty.
No request here ever leaves the machine, and none places an order.
"""

from __future__ import annotations

import asyncio
import json
import socket
import sys
from collections.abc import Callable, Iterator
from contextlib import ExitStack, closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from binance.client import Client
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    MarketDataSyncRequest,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_chart_ports import (
    DeskChartPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_dependencies import (
    desk_dependencies_for,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    FUTURES_ENV_API_KEY,
    FUTURES_ENV_API_SECRET,
    FUTURES_MAINNET_ENV_API_KEY,
    FUTURES_MAINNET_ENV_API_SECRET,
    SPOT_ENV_API_KEY,
    SPOT_ENV_API_SECRET,
    SPOT_MAINNET_ENV_API_KEY,
    SPOT_MAINNET_ENV_API_SECRET,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    CandlesUnavailableError,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sanity"))
from binance_fake_server import FakeServerUrls, run_binance_fake_server

_CONFIG_DIR = Path(__file__).resolve().parents[4] / "src" / "config"
_SYMBOL = "BTCUSDT"
#: The fake's one kline opens at 2023-01-01T00:00Z (`fake_exchange/spot_routes.py`).
_SINCE = datetime(2023, 1, 1, tzinfo=UTC)
_UNTIL = datetime(2023, 1, 2, tzinfo=UTC)
#: What the fake's fixed row says per market: `spot_routes.py` / `futures_routes.py`.
_FAKE_OPEN = {"spot": 111.0, "futures_usd_m": 222.0}
_GET_LOOP_BINDINGS = (
    "binance.base_client.get_loop",
    "binance.async_client.get_loop",
    "binance.ws.reconnecting_websocket.get_loop",
    "binance.ws.streams.get_loop",
    "binance.ws.threaded_stream.get_loop",
    "binance.ws.depthcache.get_loop",
)
_KEYS = (
    (SPOT_ENV_API_KEY, SPOT_ENV_API_SECRET),
    (FUTURES_ENV_API_KEY, FUTURES_ENV_API_SECRET),
    (SPOT_MAINNET_ENV_API_KEY, SPOT_MAINNET_ENV_API_SECRET),
    (FUTURES_MAINNET_ENV_API_KEY, FUTURES_MAINNET_ENV_API_SECRET),
)
_VENUES = [
    TradingVenue.SPOT_TESTNET,
    TradingVenue.FUTURES_TESTNET,
    TradingVenue.SPOT_MAINNET,
    TradingVenue.FUTURES_MAINNET,
]
#: What `exchange.market_data_venue` may say; it must change nothing for a venue.
_GLOBAL_SETTINGS = ["mainnet_public", "futures_testnet"]


def _closed_port_url(family: str) -> str:
    with closing(socket.socket()) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    return f"http://127.0.0.1:{port}/{family}"


@dataclass
class Exchange:
    """The composed app, with one environment answering and the other not."""

    urls: FakeServerUrls
    desk_chart: Callable[[TradingVenue], DeskChartPorts]


def _sync_and_load(ports: DeskChartPorts, venue: TradingVenue) -> tuple[object, ...]:
    market = venue.market_type
    assert market is not None
    ports.market_data_sync.sync(
        MarketDataSyncRequest(
            symbols=(_SYMBOL,),
            interval=TimeFrame.ONE_MINUTE,
            market=market,
            start_time=_SINCE,
            end_time=_UNTIL,
        )
    )
    return ports.historical_klines.load(market, _SYMBOL, TimeFrame.ONE_MINUTE)


@pytest.fixture
def composed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, request: pytest.FixtureRequest
) -> Iterator[Callable[[str, bool], Exchange]]:
    """`composed(global_setting, testnet_is_live)` -> the booted app's desk charts."""
    for key, secret in _KEYS:
        monkeypatch.setenv(key, "fake-key")
        monkeypatch.setenv(secret, "fake-secret")
    loop = asyncio.new_event_loop()
    stack = ExitStack()
    request.addfinalizer(stack.close)
    request.addfinalizer(loop.close)

    def build(global_setting: str, testnet_is_live: bool) -> Exchange:
        user_json = tmp_path / "user_config.json"
        user_json.write_text(json.dumps({}))
        config = ConfigManager()
        config.load_json(str(_CONFIG_DIR / "app_config.json"))
        config.load_json(str(user_json), writable=True)
        config.load_dict(
            {
                "exchange.market_data_venue": global_setting,
                "database.dir": str(tmp_path / "database"),
                "bots.state_dir": str(tmp_path / "bots"),
            }
        )
        urls = stack.enter_context(run_binance_fake_server())
        dead_spot, dead_futures = _closed_port_url("api"), _closed_port_url("fapi")
        live_testnet = testnet_is_live
        for name, live, dead in (
            ("API_TESTNET_URL", urls.spot, dead_spot),
            ("FUTURES_TESTNET_URL", urls.futures, dead_futures),
        ):
            stack.enter_context(
                patch.object(Client, name, live if live_testnet else dead)
            )
        for name, live, dead in (
            ("API_URL", urls.spot, dead_spot),
            ("FUTURES_URL", urls.futures, dead_futures),
        ):
            stack.enter_context(
                patch.object(Client, name, dead if live_testnet else live)
            )
        for binding in _GET_LOOP_BINDINGS:
            stack.enter_context(patch(binding, lambda: loop))
        engine = create_app(config)
        engine.boot()
        stack.callback(engine.stop)
        container = engine.context.container
        return Exchange(
            urls, lambda venue: desk_dependencies_for(container, venue).chart
        )

    return build


@pytest.mark.parametrize("global_setting", _GLOBAL_SETTINGS)
@pytest.mark.parametrize("venue", _VENUES)
def test_a_venues_chart_is_read_from_the_environment_its_orders_go_to(
    composed: Callable[[str, bool], Exchange],
    venue: TradingVenue,
    global_setting: str,
) -> None:
    # Only the venue's own environment answers: a read that went anywhere else
    # finds a closed port, and the sync raises instead of storing a candle.
    exchange = composed(global_setting, venue.is_testnet)

    candles = _sync_and_load(exchange.desk_chart(venue), venue)

    assert [c.open_price for c in candles] == [_FAKE_OPEN[venue.market_type.value]]  # type: ignore[union-attr, attr-defined]


@pytest.mark.parametrize("global_setting", _GLOBAL_SETTINGS)
def test_testnet_candles_are_never_served_as_mainnet_ones(
    composed: Callable[[str, bool], Exchange], global_setting: str
) -> None:
    """The store is keyed by the market-data source as well as the symbol and
    the interval: Spot Testnet's `BTCUSDT` and Spot Mainnet's are two series."""
    exchange = composed(global_setting, True)
    testnet, mainnet = TradingVenue.SPOT_TESTNET, TradingVenue.SPOT_MAINNET

    assert _sync_and_load(exchange.desk_chart(testnet), testnet)

    mainnet_ports = exchange.desk_chart(mainnet)
    assert (
        mainnet_ports.historical_klines.load(
            mainnet.market_type,
            _SYMBOL,
            TimeFrame.ONE_MINUTE,  # type: ignore[arg-type]
        )
        == ()
    )


def test_futures_testnets_missing_one_second_klines_is_a_readable_refusal(
    composed: Callable[[str, bool], Exchange],
) -> None:
    """`BUG-172` — the exchange answers -1120 ("Invalid interval") for `1s` on
    USDⓈ-M Futures. It reaches the chart's feed as a sentence a person can read,
    through the real client, handler and dispatcher, instead of a raw API error."""
    exchange = composed("mainnet_public", True)
    venue = TradingVenue.FUTURES_TESTNET
    ports = exchange.desk_chart(venue)
    feed = MarketDataCandleFeed(
        ports.market_data_sync,
        ports.historical_klines,
        ports.market_stream,
        MarketType.FUTURES_USD_M,
    )

    with pytest.raises(CandlesUnavailableError) as refused:
        feed.sync("BTCUSDT", TimeFrame.ONE_SECOND, lambda: False)

    assert refused.value.reason == (
        "This exchange has no 1s candles for its USDⓈ-M Futures market."
    )
    assert (
        ports.historical_klines.load(
            MarketType.FUTURES_USD_M, "BTCUSDT", TimeFrame.ONE_SECOND
        )
        == ()
    )


def test_a_short_history_on_spot_testnet_is_an_ordinary_sync(
    composed: Callable[[str, bool], Exchange],
) -> None:
    """`BUG-172` — Spot Testnet keeps little history (the fake answers one candle
    for any period): the sync succeeds and the chart reads what it stored."""
    exchange = composed("mainnet_public", True)
    venue = TradingVenue.SPOT_TESTNET
    ports = exchange.desk_chart(venue)
    feed = MarketDataCandleFeed(
        ports.market_data_sync,
        ports.historical_klines,
        ports.market_stream,
        MarketType.SPOT,
    )

    feed.sync("BTCUSDT", TimeFrame.ONE_MINUTE, lambda: False)

    assert len(feed.load_history("BTCUSDT", TimeFrame.ONE_MINUTE, 500)) == 1
