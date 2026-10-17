"""`EPIC-042B` — the attempts a bot has made to recover are counted in a rolling window, per bot."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    DEFAULT_RULE,
    PRICE_FEED_STALE,
    USER_STREAM_DOWN,
    HaltCode,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.recovery_ledger import (
    MAX_RECORDED_ATTEMPTS,
    RecoveryAttempt,
    attempts_within,
    budget_left,
    recorded,
)

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
DAY = timedelta(hours=24)


def _at(ago: timedelta, code: HaltCode = PRICE_FEED_STALE) -> RecoveryAttempt:
    return RecoveryAttempt(code, NOW - ago)


def test_an_attempt_exactly_one_window_old_no_longer_counts() -> None:
    attempts = (_at(DAY), _at(DAY - timedelta(seconds=1)))
    assert attempts_within(attempts, DAY, NOW) == 1


def test_every_reason_shares_one_budget() -> None:
    """The owner's three recoveries per 24 h are per bot, not per reason."""
    attempts = (
        _at(timedelta(hours=1), PRICE_FEED_STALE),
        _at(timedelta(hours=2), USER_STREAM_DOWN),
        _at(timedelta(hours=3), PRICE_FEED_STALE),
    )
    assert not budget_left(DEFAULT_RULE, attempts, NOW)


def test_the_budget_returns_as_the_oldest_attempt_leaves_the_window() -> None:
    attempts = (
        _at(DAY + timedelta(seconds=1)),
        _at(timedelta(hours=2)),
        _at(timedelta(hours=1)),
    )
    assert budget_left(DEFAULT_RULE, attempts, NOW)


def test_a_new_attempt_is_appended_and_the_old_ones_are_dropped() -> None:
    old, recent = _at(DAY * 2), _at(timedelta(hours=3))
    kept = recorded((old, recent), RecoveryAttempt(PRICE_FEED_STALE, NOW), DAY)
    assert kept == (recent, RecoveryAttempt(PRICE_FEED_STALE, NOW))


def test_the_ledger_is_capped_so_the_file_does_not_grow() -> None:
    attempts: tuple[RecoveryAttempt, ...] = ()
    for minute in range(MAX_RECORDED_ATTEMPTS + 5):
        attempts = recorded(
            attempts,
            RecoveryAttempt(PRICE_FEED_STALE, NOW + timedelta(minutes=minute)),
            DAY,
        )
    assert len(attempts) == MAX_RECORDED_ATTEMPTS
    assert attempts[-1].at == NOW + timedelta(minutes=MAX_RECORDED_ATTEMPTS + 4)
