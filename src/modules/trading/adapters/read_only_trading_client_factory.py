"""`EPIC-035H` — the venue's client factory, for a copy of the app that is read-only.

Every order that leaves the app is made by a client this factory's venue hands
out (a bot's through `IOrderSubmission`, a person's through the desk, the
Emergency Stop's), so wrapping the factory is the one place that covers them
all. `ReadOnlyTradingClient` keeps the reads and refuses the writes with the
instance's own reason; `VALIDATE_ONLY` still lets a test order through, which
places nothing.

@par Extension cases
  · a user-chosen viewer mode — the same wrapper with another reason;
  · a finer rule (cancel allowed, place refused) — one condition in the client.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.errors import ReadOnlyInstanceError
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client_factory import (
    ITradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType


class ReadOnlyTradingClient(ITradingClient):
    """Reads through; places a live order or cancels none."""

    def __init__(
        self, inner: ITradingClient, mode: OrderSubmissionMode, reason: str
    ) -> None:
        self._inner = inner
        self._mode = mode
        self._reason = reason

    def place_order(self, order: Order) -> Order:
        # Fail closed: only a test order, which places nothing, passes.
        if self._mode is not OrderSubmissionMode.VALIDATE_ONLY:
            raise ReadOnlyInstanceError(self._reason)
        return self._inner.place_order(order)

    def find_order(self, symbol: str, client_order_id: str) -> Order | None:
        return self._inner.find_order(symbol, client_order_id)

    def cancel_order(self, symbol: str, client_order_id: str) -> Order:
        raise ReadOnlyInstanceError(self._reason)

    def cancel_all_orders(self, symbol: str) -> list[Order]:
        raise ReadOnlyInstanceError(self._reason)

    def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        return self._inner.get_open_orders(symbol)

    def get_positions(self, symbol: str | None = None) -> list[LivePosition]:
        return self._inner.get_positions(symbol)


class ReadOnlyTradingClientFactory(ITradingClientFactory):
    """Hands out `ReadOnlyTradingClient`s over another factory's clients."""

    def __init__(self, inner: ITradingClientFactory, reason: str) -> None:
        self._inner = inner
        self._reason = reason

    def create(self, mode: OrderSubmissionMode) -> ITradingClient:
        return ReadOnlyTradingClient(self._inner.create(mode), mode, self._reason)

    def accepted_order_types(self) -> frozenset[OrderType]:
        return self._inner.accepted_order_types()
