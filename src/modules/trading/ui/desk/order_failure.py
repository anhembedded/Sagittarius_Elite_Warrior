"""`BOT-169`, `BUG-170` — what a desk says when sending an order raised.

@details A worker catches what `IOrderSubmission.submit(live=True)` raised and
carries a `SubmitFailure` to the UI thread: the kind decides the wording, the
technical text rides as `detail` (`failure_detail`) and is never a headline.
The three kinds are three different truths about the exchange:

- `OUTCOME_UNKNOWN` (`OrderOutcomeUnknownError`): the order MAY BE LIVE. The
  wording says so and never says "rejected" or "failed to send", because the
  user's next move (send it again) would double the position.
- `NOT_PLACED` (`OrderNotPlacedError`): the exchange holds no such order.
- `SHORT_NOT_SUPPORTED` (`ManualShortNotSupportedOnMarketError`): the domain
  refused before anything was sent; nothing is live.
- `PAUSED` / `BANNED` (`ExchangeRateLimitedError`, `BOT-181`): the exchange asked
  for a pause (or banned the address) and nothing was sent; the wording says so
  and until when, in the machine's local time.
- `FAILED`: anything else raised before an answer; check before retrying.

A command failure, so every one is a message box (`ui-presentation-rule.md`
§10). The cause carries the kind, so a box open for one kind never swallows
the other's.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    failure_detail,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.failure_cause import (
    failure_cause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.manual_short_not_supported_on_market_error import (
    ManualShortNotSupportedOnMarketError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_outcome_unknown import (
    OrderNotPlacedError,
    OrderOutcomeUnknownError,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_service import (
    SYSTEM_TIMEZONE_KEY,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    AppValueFormatter,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    FormatContext,
)


class SubmitFailureKind(Enum):
    OUTCOME_UNKNOWN = "outcome_unknown"
    NOT_PLACED = "not_placed"
    SHORT_NOT_SUPPORTED = "short_not_supported"
    PAUSED = "paused"
    BANNED = "banned"
    FAILED = "failed"


@dataclass(frozen=True)
class SubmitFailure:
    """A failed submission, as the worker hands it to the UI thread."""

    kind: SubmitFailureKind
    #: `failure_detail` of what was raised; for Details… and the log.
    detail: str
    #: When the exchange's pause or ban ends; set for `PAUSED` and `BANNED`.
    resume_at: datetime | None = None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def submit_failure_of(
    exc: Exception, now: Callable[[], datetime] = _utc_now
) -> SubmitFailure:
    """Classifies `exc` by type, at the worker boundary. `now` dates the end
    of a pause: the error carries how long it lasts, not when it began."""
    if isinstance(exc, ExchangeRateLimitedError):
        kind = SubmitFailureKind.BANNED if exc.banned else SubmitFailureKind.PAUSED
        return SubmitFailure(kind, failure_detail(exc), now() + exc.retry_after)
    if isinstance(exc, OrderOutcomeUnknownError):
        kind = SubmitFailureKind.OUTCOME_UNKNOWN
    elif isinstance(exc, OrderNotPlacedError):
        kind = SubmitFailureKind.NOT_PLACED
    elif isinstance(exc, ManualShortNotSupportedOnMarketError):
        kind = SubmitFailureKind.SHORT_NOT_SUPPORTED
    else:
        kind = SubmitFailureKind.FAILED
    return SubmitFailure(kind, failure_detail(exc))


def submit_failure_headline(failure: SubmitFailure, what: str) -> str:
    """The sentence for `what` ("order", "close order", "take-profit order")."""
    if failure.kind is SubmitFailureKind.OUTCOME_UNKNOWN:
        return (
            f"The {what} may be live on the exchange: its outcome could not "
            "be read. Check Open orders and Positions before sending another."
        )
    if failure.kind is SubmitFailureKind.NOT_PLACED:
        return (
            f"The exchange reports no such {what}. "
            "Check Open orders before sending it again."
        )
    if failure.kind is SubmitFailureKind.SHORT_NOT_SUPPORTED:
        return (
            f"The {what} was not sent: Spot has no short, and there is no "
            "sellable holding of this asset to sell instead."
        )
    if failure.kind in (SubmitFailureKind.PAUSED, SubmitFailureKind.BANNED):
        return _pause_headline(failure, what)
    return (
        f"The {what} could not be sent. Check Open orders and Positions, "
        "then try again."
    )


def _pause_headline(refused: SubmitFailure, what: str) -> str:
    until = (
        "" if refused.resume_at is None else f" until {_local_time(refused.resume_at)}"
    )
    if refused.kind is SubmitFailureKind.BANNED:
        opening = "The exchange has banned this machine's requests"
    else:
        opening = "The exchange asked for a pause"
    return (
        f"{opening}: the {what} was not sent, and nothing can be sent{until} "
        "(local time). Try again then."
    )


def _local_time(moment: datetime) -> str:
    return AppValueFormatter(SYSTEM_TIMEZONE_KEY).format(
        ColumnKind.TIMESTAMP, moment, FormatContext(ColumnKind.TIMESTAMP.value)
    )


def submit_failure_notice(
    problem: SubmitFailure, *, venue: TradingVenue, area: str, what: str
) -> FailureNotice:
    """@param area Which action failed ("order", "close", "protective.stop"):
    part of the cause, so one action's box never swallows another's."""
    return FailureNotice(
        kind=FailureKind.COMMAND,
        cause=failure_cause(venue, area, problem.kind.value),
        headline=submit_failure_headline(problem, what),
        detail=problem.detail,
    )
