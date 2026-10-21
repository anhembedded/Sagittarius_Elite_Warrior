"""`EPIC-039E` — a Futures venue's facts about one bot, read over the venue's ports.

@details The reader never raises and never turns a failed read into a flat, empty account:
a read that did not answer is `ExchangeUnavailable` with the reason in words. Every
collaborator is its verified fake.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.futures_facts_reader import (
    FuturesFactsReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.venue_facts_by_profile import (
    VenueFactsByProfile,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.venue_profiles_by_market import (
    VenueProfilesByMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeLoaded,
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    FuturesFacts,
    FuturesLoaded,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AssetMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    MarginType,
    PositionMode,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.futures_world import (
    AVAILABLE_MARGIN,
    BRACKETS,
    FuturesWorld,
    a_futures_status,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.readiness_world import (
    readiness_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
)

OTHER_BOT = "zzz999"


def _facts(world: FuturesWorld) -> FuturesFacts:
    snapshot = FuturesFactsReader(world.ports, world.clock).read(world.bot)
    assert isinstance(snapshot, FuturesLoaded), snapshot
    return snapshot.facts


def test_margin_mode_settings_brackets_and_a_flat_symbol_are_read() -> None:
    world = FuturesWorld(leverage=4, margin_type=MarginType.ISOLATED)

    facts = _facts(world)

    assert facts.available_margin == AVAILABLE_MARGIN
    assert facts.position_mode is PositionMode.ONE_WAY
    assert (facts.symbol_setting.leverage, facts.symbol_setting.margin_type) == (
        4,
        MarginType.ISOLATED,
    )
    assert facts.brackets == BRACKETS
    assert facts.position == 0
    assert facts.can_trade is True
    assert facts.read_at == world.clock.now()


def test_the_accounts_asset_mode_is_read_from_its_summary() -> None:
    """`BUG-260`: Multi-Assets mode reached no readiness rule."""
    single, multi = FuturesWorld(), FuturesWorld()
    multi.account.answer_with(
        replace(
            a_futures_status(),
            summary=replace(
                a_futures_status().summary, asset_mode=AssetMode.MULTI_ASSETS
            ),
        )
    )

    assert _facts(single).asset_mode is AssetMode.SINGLE_ASSET
    assert _facts(multi).asset_mode is AssetMode.MULTI_ASSETS


def test_the_signed_position_on_the_symbol_is_read() -> None:
    world = FuturesWorld()
    world.holds_a_position("-0.25")

    assert _facts(world).position == Decimal("-0.25")


def test_the_bots_tag_counts_as_its_own_and_another_tag_as_foreign() -> None:
    mine, theirs = FuturesWorld(), FuturesWorld()
    mine.rests_an_order(tag=mine.bot.bot_id.value)
    theirs.rests_an_order(tag=OTHER_BOT)

    assert (_facts(mine).own_open_orders, _facts(mine).foreign_open_orders) == (1, 0)
    assert (_facts(theirs).own_open_orders, _facts(theirs).foreign_open_orders) == (
        0,
        1,
    )


def test_hedge_mode_is_unavailable_in_the_connect_steps_words() -> None:
    world = FuturesWorld()
    world.account.answer_with(
        replace(
            a_futures_status(PositionMode.HEDGE),
            failure=ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED,
            reachable=False,
        )
    )

    snapshot = FuturesFactsReader(world.ports, world.clock).read(world.bot)

    assert isinstance(snapshot, ExchangeUnavailable)
    assert "Hedge" in snapshot.reason


def test_an_unreadable_setting_is_unavailable_never_a_default() -> None:
    world = FuturesWorld()
    world.terms.unreadable = True

    snapshot = FuturesFactsReader(world.ports, world.clock).read(world.bot)

    assert isinstance(snapshot, ExchangeUnavailable)
    assert "settings were not read" in snapshot.reason


def test_open_orders_that_cannot_be_read_are_unavailable() -> None:
    world = FuturesWorld()
    world.activity.open_orders_raise(RuntimeError("rate limited"))

    snapshot = FuturesFactsReader(world.ports, world.clock).read(world.bot)

    assert isinstance(snapshot, ExchangeUnavailable)
    assert "rate limited" in snapshot.reason


def test_the_profile_picks_the_adapter_and_spot_is_unchanged() -> None:
    futures = FuturesWorld()
    spot = readiness_world()
    spot_bot = spot.store.load(BotId(BOT)).bot
    facts = VenueFactsByProfile(
        VenueProfilesByMarket(),
        {
            ExposureKind.INVENTORY: spot.facts,
            ExposureKind.POSITION: FuturesFactsReader(futures.ports, futures.clock),
        },
    )

    assert isinstance(facts.read(futures.bot), FuturesLoaded)
    assert isinstance(facts.read(spot_bot), ExchangeLoaded)
    assert facts.read(spot_bot) == spot.facts.read(spot_bot)


@pytest.mark.parametrize("leverage", [1, 125])
def test_the_leverage_bounds_a_symbol_can_hold_are_read_as_they_are(
    leverage: int,
) -> None:
    assert _facts(FuturesWorld(leverage=leverage)).symbol_setting.leverage == leverage
