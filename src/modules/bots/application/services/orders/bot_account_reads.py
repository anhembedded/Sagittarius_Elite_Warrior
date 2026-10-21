"""`EPIC-029E` / `EPIC-039L` — what one bot reads of its account: holdings, position, open orders.

@details The reads of `BotOrderGateway` that are not orders, split from it (the 400-line
ceiling). One of them is a seam (`EPIC-039L`, decision D4): an order the bot carries the tag
of is either a **ladder order** or a **protective stop**, told apart by one fact (a stop is a
`close_position` order, which a ladder never holds), and `ladder_orders` and
`protective_orders` are the only two ways to read the tagged open orders. Every ladder read
(the stop sequence's confirmation, the housekeeping, the reconcile, the recovery report)
goes through the first, so none sees a stop; a guard test fails the day one does not.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_identity import (
    BotIdentity,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_shared_reads import (
    BotSharedReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.risk.bounded_age_reading import (
    BoundedAgeReading,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    tag_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_trading_ports import (
    VenueTradingPorts,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class BotAccountReads:
    """One bot's reads of its venue's account."""

    def __init__(
        self,
        ports: VenueTradingPorts,
        identity: BotIdentity,
        shared: BotSharedReads | None = None,
    ) -> None:
        self._ports = ports
        self._identity = identity
        self._shared = shared if shared is not None else BotSharedReads()

    def holding(self, asset: str) -> Decimal | None:
        """The account's whole holding of `asset` (free and locked), or
        `None` when the venue did not report holdings."""
        status = self._ports.account_snapshot.check_connection()
        if status.holdings is None:
            return None
        for held in status.holdings:
            if held.asset == asset:
                return held.free + held.locked
        return Decimal(0)

    def position(self) -> Decimal | None:
        """The account's signed position on the bot's symbol (positive long, negative short,
        zero flat), as the exchange reports it now; `None` when the read failed, which is not
        a flat account (`EPIC-039H`: a close is confirmed from this and from nothing else)."""
        return self._position_in(self._ports.account_snapshot.open_positions)

    def watched_position(self) -> Decimal | None:
        """The same, for a watch of the idle beat: the venue's reading the bots of the venue
        share when there is one (`BOT-184`, `VenuePositionReads`), at most half a beat old and
        never older than the bot's own last order; a confirmation never asks this."""
        positions = self._shared.positions
        if positions is None:
            return self.position()
        return self._position_in(positions.positions)

    @property
    def shared_mark(self) -> BoundedAgeReading[Decimal] | None:
        """The reading of the bot's symbol's mark its two watches share, if there is one
        (`BOT-221`)."""
        return self._shared.mark

    def account_changed(self) -> None:
        """Something this bot did or heard changes what the account holds: the venue's shared
        reading of the positions and the symbol's shared mark, if there are any, are dropped
        (`BOT-184`, `BOT-221`)."""
        if self._shared.positions is not None:
            self._shared.positions.invalidate()
        if self._shared.mark is not None:
            self._shared.mark.invalidate()

    def _position_in(
        self, read: Callable[[], tuple[LivePosition, ...]]
    ) -> Decimal | None:
        try:
            held = read()
        except ExchangeRateLimitedError:
            # The pause was told once, by the venue's gate (`ExchangeCallPolicy`, `BUG-247`).
            logger.debug(
                "Bot %s: the position of %s was not read: the exchange asked for a pause",
                self._identity.tag,
                self._identity.symbol,
            )
            return None
        except (
            Exception
        ):  # converted at this seam: an unread position is `None`, never flat
            logger.exception(
                "Bot %s: the position of %s could not be read",
                self._identity.tag,
                self._identity.symbol,
            )
            return None
        return sum(
            (p.position_amt for p in held if p.symbol == self._identity.symbol),
            Decimal(0),
        )

    def connection_failure(self) -> ConnectionFailureKind | None:
        """Why the venue's account cannot be read now, or `None` when it can: a network
        read. A venue with no key answers at once, without a request; a caller that reads
        the account only to report asks this first, so a state the operator fixes is never
        an exception. Only `KEY_REJECTED` is a rejected key: an unreachable exchange or a
        clock skew is not."""
        return self._ports.account_snapshot.check_connection().failure

    def ladder_orders(self) -> tuple[Order, ...]:
        """The account's open orders on the bot's symbol that carry its tag and are not
        protective stops."""
        return tuple(order for order in self._tagged() if not order.close_position)

    def protective_orders(self) -> tuple[Order, ...]:
        """The account's open protective stops on the bot's symbol that carry its tag."""
        return tuple(order for order in self._tagged() if order.close_position)

    def order_status(self, client_order_id: str) -> OrderStatus | None:
        """How the exchange holds one of the bot's orders now, read by its client id (a regular
        order, else a conditional one); `None` when it holds none or could not be asked."""
        try:
            order = self._ports.account_activity.find_order(
                self._identity.symbol, client_order_id
            )
        except Exception:  # converted at this seam: an unread order is `None`
            logger.exception(
                "Bot %s: the order %s could not be read",
                self._identity.tag,
                client_order_id,
            )
            return None
        return None if order is None else order.status

    def _tagged(self) -> tuple[Order, ...]:
        return tuple(
            order
            for order in self._ports.account_activity.open_orders(self._identity.symbol)
            if tag_of(order.client_order_id) == self._identity.tag
        )
