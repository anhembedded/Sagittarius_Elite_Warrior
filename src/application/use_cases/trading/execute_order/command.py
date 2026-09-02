from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.application.use_cases.queries.preview_order.query import (
    PreviewOrderQuery,
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
