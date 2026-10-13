"""`EPIC-039J` — the screen's read of the liquidation facts of a position venue.

@details The business promise: a loaded Futures snapshot gives the symbol's setting and
brackets, exactly as the venue read them; anything else says why there are none, because an
unknown bracket list is never an empty one."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_plan_risk_facts import (
    GetPlanRiskFactsQuery,
    GetPlanRiskFactsQueryHandler,
    PlanRiskUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeChecking,
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    FuturesFacts,
    FuturesLoaded,
    VenueSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_facts import (
    IVenueFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    PlanRiskFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.futures_world import (
    AVAILABLE_MARGIN,
    BRACKETS,
    SYMBOL,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.exchange_facts_fixtures import (
    loaded as spot_loaded,
)

from .helpers import seed

_SETTING = FuturesSymbolSetting(SYMBOL, 5, MarginType.ISOLATED, Decimal(1_000_000))
_FACTS = FuturesFacts(
    venue_title="Futures Testnet",
    symbol=SYMBOL,
    quote_asset="USDT",
    read_at=datetime(2026, 10, 13, 9, tzinfo=UTC),
    available_margin=AVAILABLE_MARGIN,
    position=Decimal(0),
    position_mode=PositionMode.ONE_WAY,
    symbol_setting=_SETTING,
    brackets=BRACKETS,
    own_open_orders=0,
    foreign_open_orders=0,
    can_trade=True,
)


class _Facts(IVenueFacts):
    def __init__(self, snapshot: VenueSnapshot) -> None:
        self._snapshot = snapshot

    def read(self, bot: Bot) -> VenueSnapshot:
        return self._snapshot


def _ask(snapshot: VenueSnapshot, bot_id: str = "a3f9c1"):  # type: ignore[no-untyped-def]
    store = FakeBotStore()
    seed(store, "a3f9c1", BotLifecycleState.DRAFT)
    handler = GetPlanRiskFactsQueryHandler(store, _Facts(snapshot))
    return handler.execute(GetPlanRiskFactsQuery(bot_id))


def test_a_loaded_futures_snapshot_gives_the_setting_and_the_brackets() -> None:
    answer = _ask(FuturesLoaded(_FACTS))

    assert answer == PlanRiskFacts(_SETTING, BRACKETS)


def test_an_unreadable_venue_says_why_and_gives_no_brackets() -> None:
    answer = _ask(ExchangeUnavailable("the key was refused"))

    assert answer == PlanRiskUnavailable("the key was refused")


def test_a_venue_still_being_read_is_not_an_empty_set_of_brackets() -> None:
    assert isinstance(_ask(ExchangeChecking()), PlanRiskUnavailable)


def test_a_spot_snapshot_carries_no_position_risk() -> None:
    answer = _ask(spot_loaded())

    assert isinstance(answer, PlanRiskUnavailable)
    assert "no position risk" in answer.reason


def test_a_bot_that_is_not_found_is_unavailable_in_the_commands_words() -> None:
    answer = _ask(FuturesLoaded(_FACTS), bot_id="nothere")

    assert isinstance(answer, PlanRiskUnavailable)
    assert answer.reason
