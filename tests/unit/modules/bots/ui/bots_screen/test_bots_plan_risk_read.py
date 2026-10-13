"""`EPIC-039J` — the liquidation facts of the selected bot on a position venue.

@details The screen asks for the symbol's brackets and setting when a bot at rest is
selected, as a read of its own; the answer is kept only for the bot still selected and only
if no newer ask replaced it (`async-ui-action-rule.md` §1). A venue with no position risk is
never asked. Every read is released by hand, so the order of the answers is the test's."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    PlanRiskFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.fenced_reads import (
    ReadKind,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sources import (
    FakeMarketDataSources,
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

from .bots_screen_fixtures import BotsScreen, stored
from .connect_screen_helpers import select


def _facts(leverage: int) -> FuturesFacts:
    return FuturesFacts(
        venue_title="Futures Testnet",
        symbol=SYMBOL,
        quote_asset="USDT",
        read_at=datetime(2026, 10, 13, 9, tzinfo=UTC),
        available_margin=AVAILABLE_MARGIN,
        position=Decimal(0),
        position_mode=PositionMode.ONE_WAY,
        symbol_setting=FuturesSymbolSetting(
            SYMBOL, leverage, MarginType.ISOLATED, Decimal(1_000_000)
        ),
        brackets=BRACKETS,
        own_open_orders=0,
        foreign_open_orders=0,
        can_trade=True,
    )


class _SaysLeverage(IVenueFacts):
    """The venue, answering the leverage a test names for the bot it is asked about."""

    def __init__(self) -> None:
        self.leverage = 3
        self.asked: list[str] = []

    def read(self, bot: Bot) -> VenueSnapshot:
        self.asked.append(bot.bot_id.value)
        if bot.definition.venue is not TradingVenue.FUTURES_TESTNET:
            return ExchangeUnavailable("this fake answers for the Futures venue only")
        return FuturesLoaded(_facts(self.leverage))


def _a_futures_bot(bot_id: str) -> object:
    stored_bot = stored(bot_id, S.DRAFT)
    definition = replace(stored_bot.bot.definition, venue=TradingVenue.FUTURES_TESTNET)
    return replace(stored_bot, bot=replace(stored_bot.bot, definition=definition))


def _venue_says(screen: BotsScreen, facts: IVenueFacts) -> None:
    futures = TradingVenue.FUTURES_TESTNET.market_data_venue
    screen.market_sources.serving(FakeMarketDataSources.ports(futures))
    screen.dispatcher._container.singleton(IVenueFacts, facts)  # type: ignore[attr-defined]


def _risk_reads(screen: BotsScreen) -> list[int]:
    return [
        index
        for index, (_, args) in enumerate(screen.pool.pending)
        if args[:1] == (ReadKind.RISK,)
    ]


def _run_the_others(screen: BotsScreen) -> None:
    while True:
        others = [
            index
            for index in range(len(screen.pool.pending))
            if index not in _risk_reads(screen)
        ]
        if not others:
            return
        screen.pool.run(others[0])


def test_selecting_a_futures_draft_reads_its_brackets_and_keeps_them(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([_a_futures_bot("a00001")])
    venue = _SaysLeverage()
    _venue_says(screen, venue)
    screen.settle()

    select(screen, "a00001")
    screen.settle()

    risk = screen.presenter._selected.risk
    assert risk == PlanRiskFacts(_facts(3).symbol_setting, BRACKETS)
    # The exchange check and the risk read both ask the venue's facts since `EPIC-039H` bound
    # `GetExchangeFactsQuery` to `IVenueFacts`.
    assert venue.asked == ["a00001", "a00001"]


def test_a_spot_draft_never_asks_for_position_risk(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    venue = _SaysLeverage()
    _venue_says(screen, venue)
    screen.settle()

    select(screen, "a00001")
    screen.settle()

    assert _risk_reads(screen) == []
    assert venue.asked == ["a00001"], (
        "only the exchange check asked: no position risk read"
    )
    assert screen.presenter._selected.risk is None


def test_a_stale_bracket_read_does_not_overwrite_a_newer_one(open_bots_screen) -> None:
    screen = open_bots_screen([_a_futures_bot("a00001")])
    venue = _SaysLeverage()
    _venue_says(screen, venue)
    screen.settle()
    select(screen, "a00001")
    _run_the_others(screen)
    (older,) = _risk_reads(screen)
    # The person refreshes while the first ask is still out.
    screen.presenter._exchange.refresh()
    _run_the_others(screen)
    (newer,) = [index for index in _risk_reads(screen) if index != older]

    venue.leverage = 7  # what the venue says when the newer ask is made
    screen.pool.run(newer)
    venue.leverage = 3  # the older ask reaches the venue late, and hears something else
    screen.pool.run(_risk_reads(screen)[0])

    risk = screen.presenter._selected.risk
    assert risk is not None
    assert risk.setting.leverage == 7


def test_an_answer_for_a_bot_no_longer_selected_is_dropped(open_bots_screen) -> None:
    screen = open_bots_screen([_a_futures_bot("a00001"), stored("a00002", S.DRAFT)])
    _venue_says(screen, _SaysLeverage())
    screen.settle()
    select(screen, "a00001")
    _run_the_others(screen)
    assert len(_risk_reads(screen)) == 1

    select(screen, "a00002")
    _run_the_others(screen)
    screen.settle()

    assert screen.presenter._selected.risk is None


def test_a_venue_that_cannot_answer_leaves_no_brackets_and_no_bar(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([_a_futures_bot("a00001")])

    class _Down(IVenueFacts):
        def read(self, bot: Bot) -> VenueSnapshot:
            return ExchangeUnavailable("the key was refused")

    _venue_says(screen, _Down())
    screen.settle()

    select(screen, "a00001")
    screen.settle()

    assert screen.presenter._selected.risk is None
    assert not [f for f in screen.notifier.failures if "risk" in f.cause]
