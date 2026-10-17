"""`BUG-215` — the detail of a HALTED Futures bot judges its Resume with the Futures rules.

@details `bot_detail._resume_blocked_by` built `ResumeInputs` without the bot's profile, which
defaulted to Spot's: the Spot judge was handed the Futures facts the screen read, raised
`WrongVenueFactsError`, and every Bots-screen detail refresh of the bot raised. No double stands in
for the judge: the real `detail_for` runs on a real HALTED Futures snapshot.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    FuturesFacts,
    FuturesLoaded,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import MarketView
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_detail import (
    DetailInputs,
    detail_for,
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
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    LAST_PRICE,
    TERMS,
)

_NOW = datetime(2026, 10, 15, 12, tzinfo=UTC)
_LONG = {**CONFIG, "direction": "LONG", "leverage": "3", "stop_loss": "price:50000"}


def _halted_futures_bot(state: S = S.HALTED) -> BotSnapshot:
    definition = BotDefinition(
        "Fu_test_net", "grid", TradingVenue.FUTURES_TESTNET, "BTCUSDT", _LONG
    )
    bot = Bot(BotId("a00001"), definition, BotLifecycle(state, _NOW), _NOW)
    return BotSnapshot.of(bot, None)


def _futures_facts(**changes: object) -> FuturesLoaded:
    base = FuturesFacts(
        venue_title="Futures Testnet",
        symbol="BTCUSDT",
        quote_asset="USDT",
        read_at=_NOW,
        available_margin=AVAILABLE_MARGIN,
        position=Decimal(0),
        position_mode=PositionMode.ONE_WAY,
        symbol_setting=FuturesSymbolSetting(
            "BTCUSDT", 3, MarginType.ISOLATED, Decimal(1_000_000)
        ),
        brackets=BRACKETS,
        own_open_orders=0,
        foreign_open_orders=0,
        can_trade=True,
    )
    return FuturesLoaded(replace(base, **changes))  # type: ignore[arg-type]


def _detail(exchange: FuturesLoaded, state: S = S.HALTED):
    market = PlannerMarket(TERMS, MarketView(LAST_PRICE), None, None)
    return detail_for(
        DetailInputs(_halted_futures_bot(state), None, market, _NOW, exchange=exchange)
    )


def test_the_detail_of_a_halted_futures_bot_with_futures_facts_is_built() -> None:
    detail = _detail(_futures_facts())

    assert detail.availability[BotAction.RESUME] is not None


def test_a_halted_futures_bot_in_hedge_mode_is_told_what_blocks_its_resume() -> None:
    """Positive proof the Futures judge ran: only its position-mode rule says this."""
    detail = _detail(_futures_facts(position_mode=PositionMode.HEDGE))

    resume = detail.availability[BotAction.RESUME]
    assert resume.enabled is False
    assert resume.reason.startswith("Resume is blocked: ")


def test_a_bot_waiting_to_recover_is_told_what_blocks_its_resume_like_a_halted_one() -> (
    None
):
    """`EPIC-042B`: the person's Resume in AWAITING_RECOVERY is judged by the same rules, so the
    button says why it is blocked instead of promising a ladder the Resume use case will refuse."""
    detail = _detail(
        _futures_facts(position_mode=PositionMode.HEDGE), S.AWAITING_RECOVERY
    )

    resume = detail.availability[BotAction.RESUME]
    assert resume.enabled is False
    assert resume.reason.startswith("Resume is blocked: ")
