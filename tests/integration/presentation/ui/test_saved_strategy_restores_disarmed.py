"""`BOT-166` — a strategy the user armed in an earlier session comes back at
start as a saved selection, never as a running strategy.

@details The real composed app (both Testnet venues, the fake Binance
server, the shipped screens), started from a user configuration that already
holds a complete Futures arming. Four claims, each on the composed app
because the wiring is where a boot-time arm lives (`StrategyModule.boot()`):
nothing is armed at start, the Bots mode shows the saved selection as not
armed, no tick reaches a strategy engine, and one Arm action arms exactly
what was saved. The engine is observed at `StrategyEngine.on_tick`, the
first place a tick does anything, so a session that exists but holds no
engine cannot pass for a tick that was received.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen import bots_dialogs
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_presenter import (
    BotsPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.strategy_rows import (
    NOT_ARMED_TEXT,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_engine import (
    StrategyEngine,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_strategy_controls import (
    IVenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_strategy_controls import (
    VenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.trade_mode_boot import (
    Boot,
    TradeDesk,
    trade_mode_running,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus

_FUTURES = TradingVenue.FUTURES_TESTNET
_SAVED = {
    "trading.futures_testnet.live_strategy_key": "ema_crossover",
    "trading.futures_testnet.live_symbol": "ETHUSDT",
    "trading.futures_testnet.live_interval": "5m",
    "trading.futures_testnet.live_strategy_params": "{}",
    "trading.futures_testnet.live_sizing_percent": 15.0,
    "trading.futures_testnet.live_leverage": 3.0,
}


@pytest.fixture
def ticks_seen_by_engines(monkeypatch: pytest.MonkeyPatch) -> list[MarketData]:
    """Every candle a `StrategyEngine` is given, recorded and passed on."""
    seen: list[MarketData] = []
    real = StrategyEngine.on_tick

    def spy(self: StrategyEngine, candle: MarketData, *args: object, **kw: object):
        seen.append(candle)
        return real(self, candle, *args, **kw)

    monkeypatch.setattr(StrategyEngine, "on_tick", spy)
    return seen


@pytest.fixture
def arm_dialog_answers_arm(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """The Arm strategy… dialog answered Arm; records the form it was shown."""
    shown: list[object] = []

    def answer(_parent: object, _venue: TradingVenue, form: object) -> bool:
        shown.append(form)
        return True

    monkeypatch.setattr(bots_dialogs, "ask_arm_with_dialog", answer)
    return shown


@pytest.fixture
def app_with_saved_arming(request: pytest.FixtureRequest) -> Iterator[TradeDesk]:
    with trade_mode_running(Boot.from_request(request), _SAVED) as desk:
        desk.window.switch_screen(BOTS_ROUTE)
        yield desk


def _controls(desk: TradeDesk) -> VenueStrategyControls:
    return desk.container.resolve(IVenueStrategyControls).get(_FUTURES)


def _bots(desk: TradeDesk) -> BotsPresenter:
    presenter = desk.window.presenters[BOTS_ROUTE]
    assert isinstance(presenter, BotsPresenter)
    return presenter


def _tick(desk: TradeDesk, *, symbol: str = "ETHUSDT") -> None:
    opened = datetime(2026, 10, 6, tzinfo=UTC)
    candle = MarketData(
        symbol=symbol,
        interval="5m",
        open_time=opened,
        open_price=100.0,
        high_price=101.0,
        low_price=99.0,
        close_price=100.5,
        volume=1.0,
        close_time=opened + timedelta(minutes=5),
        quote_asset_volume=100.0,
        number_of_trades=1,
        taker_buy_base_asset_volume=0.5,
        taker_buy_quote_asset_volume=50.0,
        is_closed=True,
    )
    desk.container.resolve(IEventBus).emit(
        MarketTickEvent(market_data=candle, market_type=_FUTURES.market_type)
    )


def _select_futures_row(desk: TradeDesk) -> None:
    panel = _bots(desk).strategies._panel
    panel.table.select_first(lambda row: row.venue is _FUTURES)


def test_a_saved_arming_is_not_armed_at_start(
    app_with_saved_arming: TradeDesk,
) -> None:
    desk = app_with_saved_arming
    controls = _controls(desk)

    assert controls.armed.armed().config is None
    # What is saved is still saved: restoring is not clearing.
    saved = controls.arming.saved_selection()
    assert (saved.strategy_key, saved.symbol, saved.interval) == (
        "ema_crossover",
        "ETHUSDT",
        "5m",
    )


def test_the_bots_mode_shows_it_not_armed_with_its_saved_settings(
    app_with_saved_arming: TradeDesk,
) -> None:
    rows = {row.venue: row for row in _bots(app_with_saved_arming).strategies.rows()}

    futures = rows[_FUTURES]
    assert not futures.armed
    assert futures.summary == ""
    for fragment in ("ETHUSDT 5m", "15", "3"):
        assert fragment in futures.saved, futures.saved
    assert NOT_ARMED_TEXT == "Not armed"


def test_no_tick_reaches_an_engine_before_the_user_arms(
    app_with_saved_arming: TradeDesk, ticks_seen_by_engines: list[MarketData]
) -> None:
    _tick(app_with_saved_arming)

    assert ticks_seen_by_engines == []


def test_one_arm_action_arms_exactly_what_was_saved(
    app_with_saved_arming: TradeDesk,
    ticks_seen_by_engines: list[MarketData],
    arm_dialog_answers_arm: list[object],
) -> None:
    desk = app_with_saved_arming
    _tick(desk)
    assert ticks_seen_by_engines == []

    _select_futures_row(desk)
    _bots(desk).strategies.arm_selected()

    assert len(arm_dialog_answers_arm) == 1
    armed = _controls(desk).armed.armed().config
    assert armed is not None
    assert (armed.strategy_key, armed.symbol, armed.interval) == (
        "ema_crossover",
        "ETHUSDT",
        "5m",
    )
    assert (armed.sizing_percent, armed.leverage) == (15.0, 3.0)
    _tick(desk)
    assert len(ticks_seen_by_engines) == 1
