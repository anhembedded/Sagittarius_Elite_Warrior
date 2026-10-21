"""`BOT-226` — whether an exchange read guards a bot's exits, so it may use the weight reserve.

@details The venue's request-weight gate closes at 70 % of the minute's weight (`BUG-216`) so
that the chains already in flight (a Grid's registers, a burst of fills) cannot carry it past the
exchange's limit. While it is closed every read fails too, and with them the three facts a bot's
exits are judged on: its **position**, the symbol's **mark price** and its **open protective
stops**. Two wide ladders placed in one minute closed it and left every bot's stop loss and take
profit unjudged for the rest of the minute (`BUG-247`, owner decision "C", 2026-10-21).

A read says what it is for through this enum, on the port that serves the fact
(`IAccountSnapshot.open_positions`, `IOrderEntryTerms.mark_price_for`,
`IAccountActivity.open_orders`), never by the call site that happens to make it:

  · `ROUTINE` — the default: ladder placement, reconciliation, housekeeping, a screen's refresh,
    a start's checks. Waits at the 70 % line, as before.
  · `EXIT_GUARD` — the read of one of the three facts above, made to judge or confirm an exit.
    Passes between the 70 % line and the hard line (`ExchangeCallPolicy`, 90 %), where the
    reserve ends and every request waits.

The query handler of each port carries the priority to the session with `prioritised`: the
session sits below `ITradingClient`, whose methods are the many implementers a parameter on each
would change. The handlers are the only places that open the scope (a guard test locks that), and
the scope closes with the read. A session opened inside the scope (`VenueSessions`: ping and time,
about 2 weight, when the old one is ten minutes old) rides the same class, because the guard
needs it.

Plausible extensions, each a local change: a Spot venue's holdings read as a guard is one more
port method taking `priority`; an exit's own order (a market close) riding the reserve is a third
member and a decision of its own (a placement is not a read); a finer split of the reserve per
class is one more ratio in the policy.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from enum import Enum


class RequestPriority(Enum):
    """What a read is for, which decides how much of the venue's weight it may spend."""

    ROUTINE = "routine"
    EXIT_GUARD = "exit_guard"


_CURRENT: ContextVar[RequestPriority] = ContextVar(
    "request_priority", default=RequestPriority.ROUTINE
)


@contextmanager
def prioritised(priority: RequestPriority) -> Iterator[None]:
    """Every request this thread sends inside the block carries `priority`."""
    token = _CURRENT.set(priority)
    try:
        yield
    finally:
        _CURRENT.reset(token)


def current_priority() -> RequestPriority:
    """The priority of the request being sent: `ROUTINE` outside any `prioritised` block."""
    return _CURRENT.get()
