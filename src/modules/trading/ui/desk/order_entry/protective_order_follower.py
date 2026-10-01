"""`EPIC-028I` — places an entry's take-profit and stop-loss once the
entry has filled.

@details **The fill is the venue's word, not the submit's answer.** A
Futures market order is acknowledged `NEW`; its fill arrives later on the
user-data stream (`OrderFilledEvent`, found on the fake exchange), and a
limit entry may rest for hours. So the panel hands the entry to `expect`,
and the follower waits for its own venue's `OrderFeed` to report it
`FILLED`, then builds the two orders with `protective_orders_for` (opposite
side, reduce-only, `OrderPurpose.PROTECTIVE`) and sends them through the
desk's `IOrderSubmission`, so every gate still applies but the session
limits do not.

An entry that ends any other way (cancelled, expired, rejected) is
forgotten and the desk says no TP/SL was placed; a partly filled entry that
is then cancelled is not protected either, which the desk says too. The
quantity protected is the entry's whole quantity, judged against the fill
price.

Plausible extensions: protect each partial fill as it lands; cancel the
other protective order when one triggers (Binance does not link them; the
reduce-only one left over is refused when it triggers on a flat position).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal
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
    is_terminal,
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


@dataclass(frozen=True)
class _Expected:
    entry: Order
    levels: ProtectiveLevels


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
        self._placed.connect(self._on_placed)
        feed.orderFilled.connect(self._on_order_event)

    def expect(self, entry: Order, levels: ProtectiveLevels) -> None:
        """Protects `entry` with `levels` once its fill is reported."""
        self._expected[str(entry.client_order_id)] = _Expected(entry, levels)
        logger.info(
            "TP/SL waits for %s %s to fill", entry.symbol, entry.client_order_id
        )

    @property
    def waiting(self) -> tuple[str, ...]:
        """The client order ids still waiting for their fill."""
        return tuple(self._expected)

    def _on_order_event(self, event: OrderFilledEvent) -> None:
        order = event.order
        key = str(order.client_order_id)
        expected = self._expected.get(key)
        if expected is None:
            return
        if order.status is OrderStatus.FILLED:
            del self._expected[key]
            requests = protective_orders_for(
                order.symbol,
                expected.entry.side,
                expected.entry.quantity,
                expected.levels,
                event.fill_price,
            )
            self._threads.submit(self._run_place, requests)
        elif is_terminal(order.status):
            del self._expected[key]
            self._report(
                f"The entry ended {order.status.value.replace('_', ' ')}; "
                "no TP/SL was placed.",
                True,
            )

    def _run_place(self, requests: tuple[OrderRequest, ...]) -> None:
        outcomes: list[tuple[str, bool]] = []
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
