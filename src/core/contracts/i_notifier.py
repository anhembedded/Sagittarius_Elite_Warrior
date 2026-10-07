"""`INotifier` — the one way the app tells the user about a failure or an event (`BOT-169`).

@details
A module that has something to say to the user (a command failed, a background
read could not complete, an order stopped a bot) says it through this port and
never writes it into a widget of its own. Which surface carries it is the
shell's decision, from the kind of message (`ui-presentation-rule.md` §10):

| Kind | Surface |
| :--- | :--- |
| `FailureKind.COMMAND` — the user just ran it and it failed | a modal message box, technical text behind Details… |
| `FailureKind.BACKGROUND` — a read or connection failed, the app keeps working | an inline message bar at the top of the affected mode, Retry and Details… |
| `notify()` — something happened while the user looked elsewhere | a toast, plus a line in the log |

**The headline is a sentence the caller writes**: what failed and what to do.
It is never an exception's text. The technical text travels as `detail`,
produced by `failure_detail()`, and is shown only on demand.

**One failure is one message.** `cause` is a stable key (`"trading.futures_testnet.account"`);
the same cause told again is one message box or one bar, updated in place, and
a cause that fails with the same `failure_signature(detail)` as a bar already
showing in its mode joins that bar: one outage read by four queries in 50 ms is one bar. A recovery
clears a cause with `clear_failure()`; its bar goes when every cause on it has.

**Thread-safe by contract.** Every method may be called from any thread; the
implementation delivers on the UI thread.

`Protocol`, not `ABC`: the implementation is a `QObject`, whose metaclass
conflicts with `ABCMeta` (`architecture-rule.md` §2.1 reason (a); the same
reason as `INotificationChannel`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

#: The longest technical text a notice carries: a traceback-sized detail is
#: cut, because the full text is in the log.
MAX_DETAIL_CHARS = 2000


class FailureKind(Enum):
    """What the user was doing when it failed: it decides the surface."""

    #: The user just ran a command and it failed; they must decide something.
    COMMAND = "command"
    #: A read or a connection failed; the app keeps working and may retry.
    BACKGROUND = "background"


@dataclass(frozen=True, slots=True)
class FailureNotice:
    """One failure to tell the user about."""

    kind: FailureKind
    #: The stable key of what failed: one cause is one message.
    cause: str
    #: What failed and what to do, as a plain sentence. Never an exception's text.
    headline: str
    #: The mode whose message bar shows a `BACKGROUND` failure; "" is the shell's own.
    scope: str = ""
    #: The technical text behind Details…, from `failure_detail()`.
    detail: str = ""
    #: What the message bar's Retry does (on the UI thread); `None` offers no Retry.
    retry: Callable[[], None] | None = None


@runtime_checkable
class INotifier(Protocol):
    """Tells the user about failures and events, on whichever surface fits."""

    def report_failure(self, notice: FailureNotice) -> None:
        """Shows `notice`, or updates the message already showing its cause."""
        ...

    def clear_failure(self, cause: str) -> None:
        """The cause recovered: its message bar goes. A message box is the
        user's to dismiss and stays."""
        ...

    def notify(self, headline: str, detail: str = "") -> None:
        """Tells the user, as a toast, of an event that happened while they
        looked elsewhere."""
        ...


#: What says the exchange itself could not answer: the sentence the adapters'
#: `describe_failure` writes for a gateway's HTML page, and python-binance's own
#: message for one that reached a caller unsanitised (`BUG-168`).
_EXCHANGE_UNAVAILABLE_MARKERS = (
    "the exchange is unavailable",
    "invalid json error message from binance",
)
EXCHANGE_UNAVAILABLE = "exchange unavailable"


def failure_signature(detail: str) -> str:
    """What failed, whoever told it: two notices with the same signature are one
    failure. Every way of saying "the exchange could not answer" is one
    signature, so one outage read by four queries is one message; any other text
    is its own signature, and an empty one is never merged with another."""
    lowered = detail.lower()
    if any(marker in lowered for marker in _EXCHANGE_UNAVAILABLE_MARKERS):
        return EXCHANGE_UNAVAILABLE
    return detail


def failure_detail(exc: BaseException) -> str:
    """An exception as the technical text a notice carries: its message (or
    its type when it has none), whitespace collapsed and cut. The one function
    that turns an exception into text for a screen; UI code writes no exception
    anywhere else (`test_ui_never_shows_an_exception.py`)."""
    text = " ".join(str(exc).split()) or type(exc).__name__
    return text if len(text) <= MAX_DETAIL_CHARS else text[:MAX_DETAIL_CHARS] + "…"
