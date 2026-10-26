"""`EPIC-042G` — `bot show` reads the bot's effective recovery table from the same policy the
director resolves, with the attempts the bot's record holds counted against each window."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
    GetBotStatusReportQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FAKE_CLOCK_START,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    recovery_policy_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot, BotLifecycle
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_KIND_ID,
    GRID_RECOVERY_LAYER,
    GridKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    PRICE_FEED_STALE,
    RATE_LIMITED,
    USER_STREAM_DOWN,
    RecoveryLayer,
    RuleChange,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.recovery_ledger import (
    RecoveryAttempt,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.helpers import (
    definition,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.status_world import (
    BotQueryDispatcher,
)

_ID = "aaaaaa"


class _TunedGrid(GridKind):
    """A kind whose own layer changes a common rule: a report that did its own merge would miss it."""

    def recovery_layer(self) -> RecoveryLayer:
        return RecoveryLayer(
            "tuned", changes={PRICE_FEED_STALE: RuleChange(dwell=timedelta(minutes=5))}
        )


def _dispatcher(
    venue: TradingVenue,
    attempts: tuple[RecoveryAttempt, ...] = (),
    kind: GridKind | None = None,
) -> BotQueryDispatcher:
    store = FakeBotStore()
    bot = Bot(
        BotId(_ID),
        replace(definition(), venue=venue),
        BotLifecycle(BotLifecycleState.HALTED, recovery_attempts=attempts),
        FAKE_CLOCK_START,
    )
    store.save(StoredBot(bot, {"cycles": 1}))
    grid = kind or GridKind(None, GridThresholds())  # type: ignore[arg-type]
    return BotQueryDispatcher(store, kinds=BotKindCatalog([grid]))


def _shown(dispatcher: BotQueryDispatcher) -> BotStatusEntry:
    report = dispatcher.dispatch(GetBotStatusReportQuery, GetBotStatusReportQuery(_ID))
    assert hasattr(report, "bots")
    [entry] = report.bots
    return entry


def test_a_spot_grid_shows_the_rows_the_director_resolves() -> None:
    entry = _shown(_dispatcher(TradingVenue.SPOT_TESTNET))

    expected = recovery_policy_of(GRID_RECOVERY_LAYER, TradingVenue.SPOT_TESTNET).rows
    assert entry.recovery is not None
    assert [r.code for r in entry.recovery.rules] == [e.code for e in expected]
    assert {r.code for r in entry.recovery.rules} == {
        PRICE_FEED_STALE,
        RATE_LIMITED,
        USER_STREAM_DOWN,
    }
    by_code = {r.code: r for r in entry.recovery.rules}
    first = by_code[PRICE_FEED_STALE]
    assert (first.dwell_s, first.max_attempts, first.window_s) == (120, 3, 86400)
    assert first.stalled_after_s == 900
    assert first.decided_by == "common"
    pause = by_code[RATE_LIMITED]
    assert (pause.dwell_s, pause.max_attempts) == (2, 3)
    assert pause.decided_by == GRID_KIND_ID


def test_the_kinds_own_layer_reaches_the_report() -> None:
    entry = _shown(
        _dispatcher(
            TradingVenue.SPOT_TESTNET,
            kind=_TunedGrid(None, GridThresholds()),  # type: ignore[arg-type]
        )
    )

    assert entry.recovery is not None
    by_code = {r.code: r for r in entry.recovery.rules}
    assert by_code[PRICE_FEED_STALE].dwell_s == 300
    assert by_code[PRICE_FEED_STALE].decided_by == "tuned"
    assert by_code[USER_STREAM_DOWN].dwell_s == 120


@pytest.mark.parametrize(
    "venue", [TradingVenue.FUTURES_MAINNET, TradingVenue.FUTURES_TESTNET]
)
def test_a_futures_grid_shows_the_pause_and_a_quiet_feed_and_the_layer_that_listed_them(
    venue: TradingVenue,
) -> None:
    entry = _shown(_dispatcher(venue))

    assert entry.recovery is not None
    assert [(r.code, r.decided_by) for r in entry.recovery.rules] == [
        (PRICE_FEED_STALE, "futures"),
        (RATE_LIMITED, "futures"),
    ]
    assert entry.recovery.none_decided_by == ""


def test_a_bot_on_a_venue_that_trades_no_market_says_nothing_recovers_and_who_said_so() -> (
    None
):
    entry = _shown(_dispatcher(TradingVenue.DISABLED))

    assert entry.recovery is not None
    assert entry.recovery.rules == ()
    assert entry.recovery.none_decided_by == "unknown venue"


def test_attempts_inside_the_window_are_counted_and_older_ones_are_not() -> None:
    attempts = (
        RecoveryAttempt(PRICE_FEED_STALE, FAKE_CLOCK_START - timedelta(hours=2)),
        RecoveryAttempt(USER_STREAM_DOWN, FAKE_CLOCK_START - timedelta(hours=1)),
        RecoveryAttempt(PRICE_FEED_STALE, FAKE_CLOCK_START - timedelta(hours=25)),
    )

    entry = _shown(_dispatcher(TradingVenue.SPOT_TESTNET, attempts))

    assert entry.recovery is not None
    assert {r.attempts_used for r in entry.recovery.rules} == {2}


def test_a_listing_carries_no_table() -> None:
    dispatcher = _dispatcher(TradingVenue.SPOT_TESTNET)

    report = dispatcher.dispatch(GetBotStatusReportQuery, GetBotStatusReportQuery())

    assert all(entry.recovery is None for entry in report.bots)  # type: ignore[attr-defined]
