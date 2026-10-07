"""`BUG-181` — a fills read the exchange refuses is the venue's refusal, on the fake exchange.

@details The composed app over the fake Binance server, the real history reader over
HTTP; no order is placed and nothing leaves the machine. A fills read refused with
`-2015` comes back as `BotFills.refused` carrying `ConnectionFailureKind.KEY_REJECTED`,
the same kind the connection check reports, which is what lets the Bots screen tell
the refusal once instead of raising a second bar.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills import (
    BotFills,
    GetBotFillsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.tests.testnet.grid_testnet_app import (
    SPOT,
    SYMBOL,
    composed_on_spot_testnet,
    spot_testnet_config,
)

from .grid_fake_exchange import FakeExchange

_PLACING = ("POST", "PUT", "DELETE")


def _draft(app, venue=SPOT) -> str:
    result = app.engine.dispatch(
        CreateBotCommand,
        CreateBotCommand(name="move me", kind="grid", venue=venue, symbol=SYMBOL),
    )
    assert isinstance(result, BotCommandResult) and result.accepted, result
    assert result.bot_id
    return result.bot_id


def test_a_fills_read_the_exchange_refuses_is_the_venues_refusal(
    exchange: FakeExchange, tmp_path: Path
) -> None:
    exchange.urls.keys.known = {"fake-key"}
    exchange.urls.keys.refused = {"fake-key"}
    with composed_on_spot_testnet(spot_testnet_config(tmp_path)) as app:
        bot_id = _draft(app)

        fills = app.engine.dispatch(GetBotFillsQuery, GetBotFillsQuery(bot_id))

        assert isinstance(fills, BotFills)
        assert fills.refused is not None, fills
        assert fills.refused.kind is ConnectionFailureKind.KEY_REJECTED
        assert fills.fills == ()
        assert not [r for r in exchange.urls.requests if r[0] in _PLACING]
