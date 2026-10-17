"""`EPIC-042B` — the attempts a bot has made to recover by itself, kept in its record (ADR 042 D4, D10).

An attempt is counted when it **starts** (the dwell has elapsed), not when it succeeds, so a
refusal or a crash between `propose` and `confirm` still spends one: a flapping market ends
at the budget. The ledger belongs to the bot's lifecycle, not to a kind's runtime, because
the mechanism is every kind's, and it is persisted with the bot so a restart keeps the
rolling window.

Every reason shares one ledger: the owner's three recoveries per 24 h are per bot. A rule's
`max_attempts` is judged against **all** attempts inside that rule's window.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    MAX_RECORDED_ATTEMPTS,
    HaltCode,
    HaltRecoveryRule,
)


@dataclass(frozen=True, slots=True)
class RecoveryAttempt:
    """One automatic run of the Resume path for `code`, started at `at`."""

    code: HaltCode
    at: datetime


def attempts_within(
    attempts: tuple[RecoveryAttempt, ...], window: timedelta, now: datetime
) -> int:
    """How many attempts started less than `window` before `now` (an attempt exactly `window` old no longer counts)."""
    return sum(1 for attempt in attempts if now - attempt.at < window)


def budget_left(
    rule: HaltRecoveryRule, attempts: tuple[RecoveryAttempt, ...], now: datetime
) -> bool:
    """Whether `rule` allows one more attempt now."""
    return attempts_within(attempts, rule.window, now) < rule.max_attempts


def recorded(
    attempts: tuple[RecoveryAttempt, ...],
    attempt: RecoveryAttempt,
    keep_for: timedelta,
) -> tuple[RecoveryAttempt, ...]:
    """`attempts` plus `attempt`, without the ones older than `keep_for` and at most `MAX_RECORDED_ATTEMPTS`."""
    kept = [earlier for earlier in attempts if attempt.at - earlier.at < keep_for] + [
        attempt
    ]
    return tuple(kept[-MAX_RECORDED_ATTEMPTS:])
