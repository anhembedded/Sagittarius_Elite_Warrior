from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.query import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    MANUAL_OWNER,
)


@dataclass(frozen=True)
class ExecuteOrderCommand:
    """@brief Command to execute one live order, gated behind three safety
    checks and the trading limits (`EPIC-021G`).

    @details `live` defaults `False` — a dry run: every gate and limit is
    evaluated with real, live data, but `ITradingClient.place_order()` is
    never called (`EPIC-021G` §5's own worked example: "DRY-RUN → dừng ở
    đây", stopping *before* any order-submission network call, not merely
    before a fill). Only `live=True` submits — the one place in this
    entire app allowed to construct `FuturesTradingClient` with
    `OrderSubmissionMode.LIVE` (guarded by `ast`, see
    `test_order_submission_mode_live_is_restricted.py`).
    """

    order_request: PreviewOrderQuery
    live: bool = False
    #: Who is asking (`EPIC-025` PR 2.1f) — `OrderRequest.owner_id`, carried
    #: here rather than on `PreviewOrderQuery` because ownership is an
    #: execute-time concern: a preview shapes an order and says nothing about
    #: whether this caller may send it. Defaults to `MANUAL_OWNER`, the value
    #: with the fewest privileges, so a command built without one is refused on
    #: a leased symbol instead of waved through.
    owner_id: str = MANUAL_OWNER
