"""`BOT-171` — a draft bot's venue, on the fake exchange.

@details The composed app over the fake Binance server, real adapters over HTTP; no
order is placed and nothing leaves the machine. A draft bot is moved from Spot
Testnet to Spot Mainnet through the module's own command and the store holds it
there.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.change_bot_venue import (
    ChangeBotVenueCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.testnet.grid_testnet_app import (
    SPOT,
    SYMBOL,
    composed_on_spot_testnet,
    spot_testnet_config,
)

from .grid_fake_exchange import FakeExchange

_PLACING = ("POST", "PUT", "DELETE")


def _draft(app, venue: TradingVenue = SPOT) -> str:
    result = app.engine.dispatch(
        CreateBotCommand,
        CreateBotCommand(name="move me", kind="grid", venue=venue, symbol=SYMBOL),
    )
    assert isinstance(result, BotCommandResult) and result.accepted, result
    assert result.bot_id
    return result.bot_id


def test_a_draft_moves_to_spot_mainnet_and_the_store_holds_it_there(
    exchange: FakeExchange, tmp_path: Path
) -> None:
    with composed_on_spot_testnet(spot_testnet_config(tmp_path)) as app:
        bot_id = _draft(app)

        moved = app.engine.dispatch(
            ChangeBotVenueCommand,
            ChangeBotVenueCommand(bot_id, TradingVenue.SPOT_MAINNET),
        )

        assert moved.accepted, moved
        stored = app.store.load(BotId(bot_id)).bot
        assert stored.definition.venue is TradingVenue.SPOT_MAINNET
        assert not [r for r in exchange.urls.requests if r[0] in _PLACING]
