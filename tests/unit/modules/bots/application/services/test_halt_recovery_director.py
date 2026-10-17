"""`EPIC-042C` - which event a halt applies: plain, or transient (ADR 042 §2.1, D8, D10).

The director reads the bot, the reason and the effective policy. A bot the owner paused, a restart's
wait, a reason with no rule and a venue that clears the policy all halt plainly; a transient halt
spends the budget only when its attempt starts, and a spent budget halts plainly *and says so*.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.halt_recovery_director import (
    NO_HALT_RECOVERY,
    TRANSIENT_FROM,
    HaltRecoveryDirector,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    recovery_policy_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_RECOVERY_LAYER,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    DEFAULT_RULE,
    PRICE_FEED_STALE,
    USER_STREAM_DOWN,
    HaltCode,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.recovery_ledger import (
    RecoveryAttempt,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

S = BotLifecycleState
E = BotLifecycleEvent
NOW = datetime(2026, 10, 17, 12, tzinfo=UTC)


def _bot(
    state: S,
    attempts: tuple[RecoveryAttempt, ...] = (),
    venue: TradingVenue = TradingVenue.SPOT_TESTNET,
) -> Bot:
    definition = BotDefinition("grid", "grid", venue, "BTCUSDT")
    return Bot(
        BotId("abc123"), definition, BotLifecycle(state, None, None, attempts), NOW
    )


def _director(venue: TradingVenue = TradingVenue.SPOT_TESTNET) -> HaltRecoveryDirector:
    return HaltRecoveryDirector(recovery_policy_of(GRID_RECOVERY_LAYER, venue))


@pytest.mark.parametrize("state", sorted(TRANSIENT_FROM))
@pytest.mark.parametrize("code", [PRICE_FEED_STALE, USER_STREAM_DOWN])
def test_a_running_or_starting_bot_halts_transiently_for_a_common_reason(
    state: S, code: HaltCode
) -> None:
    assert _director().decide(_bot(state), code, NOW).event is E.HALT_TRANSIENT


@pytest.mark.parametrize("state", [s for s in S if s not in TRANSIENT_FROM])
def test_every_other_state_halts_plainly(state: S) -> None:
    """The owner's Pause (PAUSED) and a restart's wait (RECOVERING) are never undone by a machine."""
    assert _director().decide(_bot(state), PRICE_FEED_STALE, NOW).event is E.HALT


def test_a_reason_with_no_rule_halts_plainly() -> None:
    decision = _director().decide(_bot(S.RUNNING), HaltCode("order_rejected"), NOW)

    assert (decision.event, decision.note, decision.rule) == (E.HALT, "", None)


@pytest.mark.parametrize(
    "venue", [TradingVenue.FUTURES_TESTNET, TradingVenue.FUTURES_MAINNET]
)
def test_a_futures_bot_never_halts_transiently(venue: TradingVenue) -> None:
    """ADR 042 D5: its halt closes the position and `EPIC-039L` governs it."""
    bot = _bot(S.RUNNING, venue=venue)

    assert _director(venue).decide(bot, PRICE_FEED_STALE, NOW).event is E.HALT


def test_a_bot_with_the_budget_spent_halts_plainly_and_says_so() -> None:
    spent = tuple(
        RecoveryAttempt(PRICE_FEED_STALE, NOW - timedelta(hours=hour))
        for hour in range(1, DEFAULT_RULE.max_attempts + 1)
    )

    decision = _director().decide(_bot(S.RUNNING, spent), PRICE_FEED_STALE, NOW)

    assert decision.event is E.HALT
    assert "3 automatic recoveries allowed in 24 h are used up" in decision.note


def test_the_budget_returns_when_the_oldest_attempt_leaves_the_window() -> None:
    attempts = (
        RecoveryAttempt(PRICE_FEED_STALE, NOW - timedelta(hours=24)),
        RecoveryAttempt(USER_STREAM_DOWN, NOW - timedelta(hours=2)),
        RecoveryAttempt(PRICE_FEED_STALE, NOW - timedelta(hours=1)),
    )

    decision = _director().decide(_bot(S.RUNNING, attempts), PRICE_FEED_STALE, NOW)

    assert decision.event is E.HALT_TRANSIENT


def test_a_director_with_no_policy_recovers_nothing() -> None:
    assert (
        NO_HALT_RECOVERY.decide(_bot(S.RUNNING), PRICE_FEED_STALE, NOW).event is E.HALT
    )


def test_the_ledger_is_kept_for_the_longest_window() -> None:
    assert _director().keep_for == DEFAULT_RULE.window
