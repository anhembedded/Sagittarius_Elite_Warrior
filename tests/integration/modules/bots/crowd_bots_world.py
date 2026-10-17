"""`EPIC-029J` J1b - helpers for several bots on one venue of the two-venue composed app.

@details The world is `two_venues_bots_world.booted_two_venues` (the composed app, real adapters
over the one fake server). A Futures bot's symbol is one of `futures_market.CROWD_SYMBOLS` or
`BTCUSDT` / `ETHUSDT`: they all trade at the one mark, so the same grid fits every symbol and a
bot's client order id tag (its id) is what tells whose an order or a fill is.
"""

from __future__ import annotations

import sys
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .two_venues_bots_world import GRIDS, BootedTwoVenues

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sanity"))
from fake_exchange.futures_market import CROWD_SYMBOLS

#: Twenty Futures symbols that trade at the one mark, the most any measurement here asks for.
FUTURES_SYMBOLS: tuple[str, ...] = ("BTCUSDT", *CROWD_SYMBOLS)

#: A grid for `ETHUSDT` (mark 3,200), the owner's second symbol: the same shape as the BTC grid at
#: a twentieth of the price, its stop above the worst case's liquidation price (O3).
ETH_GRID = {
    "lower": "3000",
    "upper": "3400",
    "grid_count": "4",
    "spacing": "ARITHMETIC",
    "capital_quote": "600",
    "direction": "LONG",
    "leverage": "3",
    "stop_loss": "price:2500",
    "take_profit": "price:4000",
}


#: A grid for Spot Testnet's `ETHUSDT` (mark 3,000): five levels 100 apart around it, 1,600 USDT
#: over four orders, under trading's 500 an order.
ETH_SPOT_GRID = {
    "lower": "2800",
    "upper": "3200",
    "grid_count": "4",
    "spacing": "ARITHMETIC",
    "capital_quote": "1600",
    "stop_loss": "price:2000",
    "take_profit": "price:4000",
}


def create_bot(
    app: BootedTwoVenues,
    venue: TradingVenue,
    symbol: str,
    name: str | None = None,
    params: dict[str, str] | None = None,
) -> str:
    created = app.engine.dispatch(
        CreateBotCommand,
        CreateBotCommand(
            name or f"grid {symbol}", "grid", venue, symbol, params or GRIDS[venue]
        ),
    )
    assert isinstance(created, BotCommandResult)
    assert created.bot_id is not None, created.message
    return created.bot_id


def start_bot(app: BootedTwoVenues, bot_id: str) -> BotCommandResult:
    started = app.engine.dispatch(
        StartBotCommand, StartBotCommand(bot_id, real_money_confirmed=True)
    )
    assert isinstance(started, BotCommandResult)
    return started


def run_bots(
    app: BootedTwoVenues, venue: TradingVenue, symbols: tuple[str, ...]
) -> dict[str, str]:
    """Create and start one bot per symbol; @return `symbol -> bot id`. Each start must be accepted."""
    bots: dict[str, str] = {}
    for symbol in symbols:
        bot_id = create_bot(app, venue, symbol)
        started = start_bot(app, bot_id)
        assert started.accepted, f"{symbol}: {started.message}"
        bots[symbol] = bot_id
    return bots
