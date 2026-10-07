from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.query import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_purpose import (
    OrderPurpose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    MANUAL_OWNER,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import (
    TRIGGERED_ORDER_TYPES,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
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
    #: `EPIC-028I` — an execute-time concern like `owner_id`: whether the
    #: trading limits apply (`OrderPurpose`).
    purpose: OrderPurpose = OrderPurpose.ENTRY
    #: `EPIC-034C` — `OrderRequest.opens_session`: a manual live order opens the
    #: venue's order session itself, after the same reconciliation Start bot and
    #: arm strategy run. Read only when `live`.
    opens_session: bool = False

    def __post_init__(self) -> None:
        """@throws ValueError an order whose purpose passes the trading
        limits (`OrderPurpose.only_reduces`) but that could open a position:
        one that is not reduce-only, one on a venue whose exchange does not
        enforce reduce-only (only Futures does; the Spot mapper never sends
        the flag), or a protective order that is not a triggered type."""
        if not self.purpose.only_reduces:
            return
        request = self.order_request
        if not request.reduce_only:
            raise ValueError(f"a {self.purpose.value} order must be reduce-only")
        if request.venue.market_type is not MarketType.FUTURES_USD_M:
            raise ValueError(
                f"a {self.purpose.value} order passes the trading limits only "
                f"where the exchange enforces reduce-only, not on "
                f"{request.venue.value}"
            )
        if (
            self.purpose is OrderPurpose.PROTECTIVE
            and request.order_type not in TRIGGERED_ORDER_TYPES
        ):
            raise ValueError(
                f"a protective order must be a triggered type, not "
                f"{request.order_type.value}"
            )

    @property
    def venue(self) -> TradingVenue:
        """`EPIC-028B` (ADR D3) — read from `order_request`, never stored a
        second time: the order and the command acting on it cannot then
        disagree about which venue they address."""
        return self.order_request.venue
