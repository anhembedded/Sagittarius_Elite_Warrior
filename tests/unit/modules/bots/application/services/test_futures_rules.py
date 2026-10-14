"""`EPIC-039E` — the Futures readiness rules, and which rules judge which venue.

@details Business promise: a Futures bot is not claimed ready when the account is in Hedge
Mode, when the symbol already holds a position, when the leverage it asked is above what the
symbol's bracket allows at the ladder's worst-case notional, or when the available margin is
below the ladder's initial margin; a snapshot that holds no facts is one item, never a flat
empty account; and the Spot rules never judge a Futures snapshot or the other way round.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.exchange_rules import (
    RunPurpose,
    judge_exchange,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.futures_rules import (
    FOREIGN_POSITION,
    FUTURES_RULES,
    LEVERAGE_ABOVE_BRACKET,
    MARGIN_SHORT,
    POSITION_MODE_NOT_ONE_WAY,
    judge_futures,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.venue_rules import (
    WrongVenueFactsError,
    judge_venue,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeChecking,
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    FuturesFacts,
    FuturesLoaded,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_needs import (
    FuturesNeeds,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.futures_world import (
    AVAILABLE_MARGIN,
    BRACKETS,
    SYMBOL,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.exchange_facts_fixtures import (
    loaded as spot_loaded,
)

START = RunPurpose.START
#: 20 000 of notional at 5x is 4 000 of margin, inside the first bracket (20x).
NEEDS = FuturesNeeds(Decimal(4_000), Decimal(20_000), 5)


def _facts(**changes: object) -> FuturesFacts:
    base = FuturesFacts(
        venue_title="Futures Testnet",
        symbol=SYMBOL,
        quote_asset="USDT",
        read_at=datetime(2026, 10, 13, 9, tzinfo=UTC),
        available_margin=AVAILABLE_MARGIN,
        position=Decimal(0),
        position_mode=PositionMode.ONE_WAY,
        symbol_setting=FuturesSymbolSetting(
            SYMBOL, 5, MarginType.ISOLATED, Decimal(1_000_000)
        ),
        brackets=BRACKETS,
        own_open_orders=0,
        foreign_open_orders=0,
        can_trade=True,
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def _codes(facts: FuturesFacts, needs: FuturesNeeds | None = NEEDS, purpose=START):  # type: ignore[no-untyped-def]
    outcome = judge_futures(FuturesLoaded(facts), needs, purpose)
    return [item.code for item in outcome.items]


def test_a_funded_flat_one_way_account_inside_the_bracket_has_nothing_left() -> None:
    assert _codes(_facts()) == []


def test_margin_short_for_the_ladder() -> None:
    assert _codes(_facts(available_margin=Decimal(3_999))) == [MARGIN_SHORT]
    assert _codes(_facts(available_margin=Decimal(4_000))) == []  # the boundary fits


def test_margin_short_names_what_is_needed_and_what_is_there() -> None:
    (item,) = judge_futures(
        FuturesLoaded(_facts(available_margin=Decimal(1_000))), NEEDS, START
    ).items

    assert "4000.00 USDT" in item.reason
    assert "1000.00 USDT" in item.reason


def test_foreign_position_is_a_readiness_refusal() -> None:
    (item,) = judge_futures(
        FuturesLoaded(_facts(position=Decimal("-0.5"))), NEEDS, START
    ).items

    assert item.code == FOREIGN_POSITION
    assert "short position of 0.5" in item.reason


def test_a_resume_does_not_call_the_standing_position_foreign() -> None:
    """Whether a resume's position is the bot's own needs the exposure book (039D)."""
    facts = _facts(position=Decimal("0.5"))

    assert _codes(facts, purpose=RunPurpose.RESUME) == []


def test_leverage_above_the_bracket_for_the_worst_case_notional() -> None:
    inside = FuturesNeeds(Decimal(2_000), Decimal(20_000), 20)
    above = FuturesNeeds(Decimal(2_000), Decimal(20_000), 21)
    deeper = FuturesNeeds(Decimal(3_000), Decimal(60_000), 11)  # second bracket: 10x

    assert _codes(_facts(), inside) == []
    assert _codes(_facts(), above) == [LEVERAGE_ABOVE_BRACKET]
    assert _codes(_facts(), deeper) == [LEVERAGE_ABOVE_BRACKET]


def test_position_mode_not_one_way_is_an_item() -> None:
    assert _codes(_facts(position_mode=PositionMode.HEDGE)) == [
        POSITION_MODE_NOT_ONE_WAY
    ]


def test_without_a_plan_the_plan_rules_are_silent() -> None:
    assert _codes(_facts(available_margin=Decimal(0)), needs=None) == []


def test_a_snapshot_with_no_facts_is_one_item_not_an_empty_account() -> None:
    checking = judge_futures(ExchangeChecking(), NEEDS, START)
    unavailable = judge_futures(ExchangeUnavailable("no key"), NEEDS, START)

    assert [i.code for i in checking.items] == ["RUN_EXCHANGE_CHECKING"]
    assert [i.code for i in unavailable.items] == ["RUN_EXCHANGE_UNAVAILABLE"]
    assert "no key" in unavailable.items[0].reason


def test_the_rules_are_one_function_each_in_the_table() -> None:
    assert len(FUTURES_RULES) == len({rule.__name__ for rule in FUTURES_RULES}) == 4


def test_the_profile_picks_the_rules_and_the_other_rules_never_run() -> None:
    spot = venue_profile_of(TradingVenue.SPOT_TESTNET)
    futures = venue_profile_of(TradingVenue.FUTURES_TESTNET)
    assert spot is not None and futures is not None
    short = _facts(available_margin=Decimal(0))

    on_futures = judge_venue(futures, FuturesLoaded(short), NEEDS, START)
    assert [i.code for i in on_futures.items] == [MARGIN_SHORT]

    spot_snapshot = spot_loaded()
    assert judge_venue(spot, spot_snapshot, None, START) == judge_exchange(
        spot_snapshot, None, START
    )
    with pytest.raises(WrongVenueFactsError):
        judge_venue(spot, FuturesLoaded(short), None, START)
    with pytest.raises(WrongVenueFactsError):
        judge_venue(futures, spot_snapshot, None, START)
