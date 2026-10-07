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
- `FAILED`: anything else raised before an answer; check before retrying.

A command failure, so every one is a message box (`ui-presentation-rule.md`
§10). The cause carries the kind, so a box open for one kind never swallows
the other's.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    failure_detail,
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


class SubmitFailureKind(Enum):
    OUTCOME_UNKNOWN = "outcome_unknown"
    NOT_PLACED = "not_placed"
    SHORT_NOT_SUPPORTED = "short_not_supported"
    FAILED = "failed"


@dataclass(frozen=True)
class SubmitFailure:
    """A failed submission, as the worker hands it to the UI thread."""

    kind: SubmitFailureKind
    #: `failure_detail` of what was raised; for Details… and the log.
    detail: str


def submit_failure_of(exc: Exception) -> SubmitFailure:
    """Classifies `exc` by type, at the worker boundary."""
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
    return (
        f"The {what} could not be sent. Check Open orders and Positions, "
        "then try again."
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
