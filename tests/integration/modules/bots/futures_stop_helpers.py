"""`EPIC-039L` - what the protective-stop journeys share: start a bot, read the stops that stand.

@details Plain functions over the composed Futures world (`futures_bots_world`); no double.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)

from .futures_bots_world import GRID, BootedFuturesBots
from .futures_fake_exchange import FUTURES, SYMBOL

#: The stop loss of `GRID` (`price:50000`), under the range and far from liquidation.
STOP_LOSS = Decimal(50000)


def started(app: BootedFuturesBots, config: dict[str, str] | None = None) -> str:
    """Create and start a Futures grid bot; its id."""
    created = app.engine.dispatch(
        CreateBotCommand,
        CreateBotCommand("futures grid", "grid", FUTURES, SYMBOL, config or GRID),
    )
    assert isinstance(created, BotCommandResult)
    assert created.bot_id is not None, created.message
    result = app.engine.dispatch(StartBotCommand, StartBotCommand(created.bot_id))
    assert isinstance(result, BotCommandResult)
    assert result.accepted, result.message
    return created.bot_id


def stops(app: BootedFuturesBots) -> list[dict[str, object]]:
    """The conditional orders standing on the exchange, as the fake holds them."""
    return app.exchange.urls.futures_book.algo.open_orders(SYMBOL)
