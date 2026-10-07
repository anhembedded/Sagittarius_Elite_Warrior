"""`EPIC-028I` — a filled Futures entry protected by a take-profit and a
stop-loss, against the fake exchange: both sent through the Algo Order API,
on the opposite side, reduce-only, past a session limit that allows one
order.

@details The entry and both protective orders go through the real
`ExecuteOrderCommandHandler`, `FuturesTradingClient` and `python-binance`
(`test_futures_algo_orders_against_fake_server.py`'s context). The session
is limited to one order, the entry, so the take-profit and stop-loss only
reach the wire because their purpose exempts them.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.handler import (
    ExecuteOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.handler import (
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.query import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.session_readiness import (
    SessionReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.protective_levels import (
    ProtectiveLevels,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimits,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.protective_orders import (
    protective_orders_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)
from Sagittarius_Elite_Warrior.tests.integration.application.test_futures_algo_orders_against_fake_server import (
    _FUTURES,
    _client,
    _context,
    _with_fake_exchange,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.recording_publisher import (
    RecordingPublisher,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    single_venue_scopes,
)

_ONE_ORDER = TradingLimits(
    max_orders_per_session=1,
    max_notional_per_order=Decimal(100000),
    max_positions_per_symbol=1,
    min_order_interval=timedelta(minutes=10),
)


def _as_query(request: OrderRequest) -> PreviewOrderQuery:
    return PreviewOrderQuery(
        venue=_FUTURES,
        symbol=request.symbol,
        side=request.side,
        order_type=request.order_type,
        quantity=request.quantity,
        reference_price=request.reference_price,
        reduce_only=request.reduce_only,
        stop_price=request.stop_price,
        last_price=request.last_price,
    )


def test_a_filled_long_is_protected_past_a_one_order_session() -> None:
    def body(urls) -> None:
        context = _context()
        state = TradingSessionState()
        state.enable(set())
        handler = ExecuteOrderCommandHandler(
            single_venue_scopes(context, state),
            PreviewOrderQueryHandler(FakeVenueContexts(context)),
            TradingLimitPolicy(_ONE_ORDER),
            SessionReadiness(single_venue_scopes(context, state), RecordingPublisher()),
        )
        entry = handler.execute(
            ExecuteOrderCommand(
                order_request=PreviewOrderQuery(
                    venue=_FUTURES,
                    symbol="BTCUSDT",
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=Decimal("0.01"),
                    reference_price=Decimal(50000),
                ),
                live=True,
            )
        )
        # The acknowledgement says NEW: Binance reports a market order's fill
        # on the user-data stream, which is why the desk waits for the fill
        # event before protecting (`ProtectiveOrderFollower`). The fake has
        # filled it: the long is open.
        assert entry.submitted_order is not None
        (position,) = _client(context).get_positions("BTCUSDT")
        assert position.position_amt == Decimal("0.01")

        results = [
            handler.execute(
                ExecuteOrderCommand(
                    order_request=_as_query(request),
                    live=True,
                    purpose=request.purpose,
                )
            )
            for request in protective_orders_for(
                "BTCUSDT",
                OrderSide.BUY,
                Decimal("0.01"),
                ProtectiveLevels(Decimal(52000), Decimal(48000)),
                Decimal(50000),
            )
        ]

        assert [r.blocked_by for r in results] == [None, None]
        resting = _client(context).get_open_orders("BTCUSDT")
        assert sorted(o.order_type.value for o in resting) == [
            "stop_market",
            "take_profit_market",
        ]
        assert all(o.side is OrderSide.SELL and o.reduce_only for o in resting)
        assert state.orders_sent_this_session == 1

    _with_fake_exchange(body)
