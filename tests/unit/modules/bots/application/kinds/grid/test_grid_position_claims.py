"""`BUG-250` - the runs of a venue that may own a position its account holds.

@details A claim names whose tagged history trading reads; it carries no figure, so the bot's file
never decides what the account may hold. A bot at rest (DRAFT, STOPPED), one that never started a
run, and one of another venue name nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_position_claims import (
    venue_position_claims,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position_claim import (
    OwnerPositionClaim,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

S = BotLifecycleState
_FUTURES = TradingVenue.FUTURES_TESTNET
_AT = datetime(2026, 10, 20, 8, 0, tzinfo=UTC)


def _bot(
    bot_id: str,
    state: BotLifecycleState,
    symbol: str = "ETHUSDT",
    venue: TradingVenue = _FUTURES,
    run_started_at: datetime | None = _AT,
) -> Bot:
    return Bot(
        BotId(bot_id),
        BotDefinition("grid", "grid", venue, symbol, {}),
        BotLifecycle(state, run_started_at),
        _AT,
    )


def test_a_claim_names_the_owner_the_tag_the_symbol_and_the_run_start() -> None:
    claims = venue_position_claims(_FUTURES, [_bot("6tszoz", S.RECOVERING)])

    assert claims == (OwnerPositionClaim("bot.6tszoz", "6tszoz", "ETHUSDT", _AT),)


@pytest.mark.parametrize(
    "state",
    [S.RECOVERING, S.HALTED, S.PAUSED, S.RUNNING, S.STOPPING, S.ERROR],
)
def test_every_bot_that_is_mid_run_claims(state: BotLifecycleState) -> None:
    assert len(venue_position_claims(_FUTURES, [_bot("aaaaaa", state)])) == 1


@pytest.mark.parametrize("state", [S.DRAFT, S.STOPPED])
def test_a_bot_at_rest_claims_nothing(state: BotLifecycleState) -> None:
    assert venue_position_claims(_FUTURES, [_bot("aaaaaa", state)]) == ()


def test_a_bot_that_never_started_a_run_claims_nothing() -> None:
    bot = _bot("aaaaaa", S.RECOVERING, run_started_at=None)

    assert venue_position_claims(_FUTURES, [bot]) == ()


def test_another_venues_bot_claims_nothing() -> None:
    bot = _bot("aaaaaa", S.RECOVERING, venue=TradingVenue.SPOT_TESTNET)

    assert venue_position_claims(_FUTURES, [bot]) == ()


def test_every_waiting_bot_of_the_venue_claims_in_the_order_given() -> None:
    claims = venue_position_claims(
        _FUTURES,
        [_bot("6tszoz", S.RECOVERING), _bot("6z20d2", S.RECOVERING, "BNBUSDT")],
    )

    assert [(c.tag, c.symbol) for c in claims] == [
        ("6tszoz", "ETHUSDT"),
        ("6z20d2", "BNBUSDT"),
    ]
