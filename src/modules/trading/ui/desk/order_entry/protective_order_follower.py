"""`EPIC-028I` — places an entry's take-profit and stop-loss once the
entry has filled.

@details **The fill is the venue's word, not the submit's answer.** A
Futures market order is acknowledged `NEW`; its fill arrives later on the
user-data stream (`OrderFilledEvent`, found on the fake exchange), and a
limit entry may rest for hours. So the panel hands the entry to `expect`,
and the follower waits for its own venue's `OrderFeed` to report it, then
builds the two orders with `protective_orders_for` (opposite side,
reduce-only, `OrderPurpose.PROTECTIVE`) and sends them through the desk's
`IOrderSubmission`, so every gate still applies but the session limits do
not.

**The fill may be reported before `expect`** (the review of PR 307): the
stream's fill and the submit's answer reach the UI thread by separate
queued signals, and a market order often fills before its REST answer
returns. So the follower keeps what the feed reported about the last
`REMEMBERED_ORDERS` orders, and `expect` settles at once on an entry already
over.

**How an entry ends decides what is protected.** Filled whole: its whole
quantity. Cancelled or expired after a partial fill (`OrderEndedEvent`):
the quantity that filled, and the desk says so. Ended with nothing filled:
nothing, and the desk says so. Each is judged against the last fill price.

**A leftover protective order is a risk this does not remove.** Binance
does not link the take-profit and the stop-loss: when one closes the
position, the other keeps resting. It is reduce-only, so it is refused
while the account is flat; but if a new position on the same side opens
before it triggers, it closes part of that position at the old level. The
desk screen (`EPIC-028K`) lists it in Open orders, and cancelling the
sibling once one triggers is that task's to decide.

Plausible extension: protect each partial fill as it lands.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, replace
from decimal import Decimal

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_ended_event import (
    OrderEndedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.protective_levels import (
    ProtectiveLevels,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.protective_orders import (
    protective_orders_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.execute_order_block_reason import (
    format_execute_order_block_reason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_feed import OrderFeed
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger("App.Trading.OrderEntry")

#: Where the follower says what happened: `(text, is_error)`.
type ReportOutcome = Callable[[str, bool], None]

_KIND = {"take_profit_market": "Take-profit", "stop_market": "Stop-loss"}

#: How many orders' reported progress is kept for an `expect` still to come.
#: Its answer and its fill arrive moments apart, so a few dozen is plenty.
REMEMBERED_ORDERS = 64


@dataclass(frozen=True)
class _Expected:
    entry: Order
    levels: ProtectiveLevels


@dataclass(frozen=True)
class _Progress:
    """What the feed reported about one order so far."""

    filled: Decimal = Decimal(0)
    last_price: Decimal | None = None
    #: `FILLED`, or how it ended unfilled; `None` while it may still fill.
    ended: OrderStatus | None = None


class ProtectiveOrderFollower(QObject):
    """@brief An entry's TP/SL, placed when its fill is reported."""

    _placed = Signal(object)

    def __init__(
        self,
        submission: IOrderSubmission,
        feed: OrderFeed,
        thread_manager: IThreadManager,
        report: ReportOutcome,
    ) -> None:
        super().__init__(feed)
        self._submission = submission
        self._threads = thread_manager
        self._report = report
        self._expected: dict[str, _Expected] = {}
        self._progress: OrderedDict[str, _Progress] = OrderedDict()
        self._placed.connect(self._on_placed)
        feed.orderFilled.connect(self._on_order_filled)
        feed.orderEnded.connect(self._on_order_ended)

    def expect(self, entry: Order, levels: ProtectiveLevels) -> None:
        """Protects `entry` with `levels` once its fill is reported, or at
        once if it already was."""
        key = str(entry.client_order_id)
        self._expected[key] = _Expected(entry, levels)
        logger.info("TP/SL waits for %s %s to fill", entry.symbol, key)
        self._settle(key)

    @property
    def waiting(self) -> tuple[str, ...]:
        """The client order ids still waiting for their fill."""
        return tuple(self._expected)

    def _on_order_filled(self, event: OrderFilledEvent) -> None:
        key = str(event.order.client_order_id)
        progress = self._progress.get(key, _Progress())
        self._remember(
            key,
            _Progress(
                filled=progress.filled + event.fill_quantity,
                last_price=event.fill_price,
                ended=(
                    OrderStatus.FILLED
                    if event.order.status is OrderStatus.FILLED
                    else None
                ),
            ),
        )
        self._settle(key)

    def _on_order_ended(self, event: OrderEndedEvent) -> None:
        key = str(event.order.client_order_id)
        progress = self._progress.get(key, _Progress())
        self._remember(key, replace(progress, ended=event.order.status))
        self._settle(key)

    def _remember(self, key: str, progress: _Progress) -> None:
        self._progress[key] = progress
        self._progress.move_to_end(key)
        while len(self._progress) > REMEMBERED_ORDERS:
            oldest = next((k for k in self._progress if k not in self._expected), None)
            if oldest is None:
                break
            del self._progress[oldest]

    def _settle(self, key: str) -> None:
        """Places or gives up on `key`'s TP/SL once it is both expected and
        over."""
        expected = self._expected.get(key)
        progress = self._progress.get(key)
        if expected is None or progress is None or progress.ended is None:
            return
        del self._expected[key]
        del self._progress[key]
        entry = expected.entry
        ended = progress.ended.value.replace("_", " ")
        price = progress.last_price
        if price is None:  # no fill was reported: nothing to protect
            self._report(f"The entry ended {ended}; no TP/SL was placed.", True)
            return
        if progress.ended is OrderStatus.FILLED:
            quantity, note = entry.quantity, None
        else:
            quantity = progress.filled
            note = (
                f"The entry ended {ended} after {progress.filled} of "
                f"{entry.quantity} filled; TP/SL protect {progress.filled}."
            )
        requests = protective_orders_for(
            entry.symbol, entry.side, quantity, expected.levels, price
        )
        self._threads.submit(self._run_place, requests, note)

    def _run_place(self, requests: tuple[OrderRequest, ...], note: str | None) -> None:
        outcomes: list[tuple[str, bool]] = [] if note is None else [(note, False)]
        for request in requests:
            kind = _KIND.get(request.order_type.value, request.order_type.value)
            try:
                result = self._submission.submit(request, live=True)
            except Exception as exc:  # noqa: BLE001 - worker boundary: one refused order must not hide the other's outcome
                outcomes.append((f"{kind} failed: {exc}", True))
                continue
            if result.blocked:
                reason = format_execute_order_block_reason(result.blocked_by)
                outcomes.append((f"{kind} not placed: {reason}", True))
            else:
                outcomes.append((f"{kind} placed at {request.stop_price}.", False))
        self._placed.emit(outcomes)

    def _on_placed(self, outcomes: list[tuple[str, bool]]) -> None:
        failed = any(is_error for _text, is_error in outcomes)
        text = " ".join(text for text, _is_error in outcomes)
        logger.info("TP/SL: %s", text)
        self._report(text, failed)
