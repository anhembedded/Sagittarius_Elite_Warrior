"""`EPIC-021G` — turns an actionable live `Signal` into a real order
attempt, with no shortcut from event handler to `ITradingClient` (ADR §7):
every signal goes through the exact same `ExecuteOrderCommand` pipeline
`trade-once` uses, so the three safety gates and four trading limits apply
identically to both entry points.

@par Not wired through the `SignalGeneratedEvent` bus — a real hazard, not
a style choice
`StrategyEngine.on_tick()`/`run_batch()` publish `SignalGeneratedEvent` on
the **same global event bus** a backtest run's `RunHistoricalTickBacktest
CommandHandler` uses (both take the shared `IEventPublisher` singleton —
verified by reading that handler's own construction, not assumed). A
`LiveTradingCoordinator` subscribed to that event with
`app.event_bus.on(SignalGeneratedEvent, coordinator.handle)` would receive
every signal a *backtest* produces too, and — gated only by the three
safety checks, which a misconfigured or newly-enabled session could pass —
attempt a real order from a backtest run. `MarketTickEventHandler` calls
`.handle(signal)` on this class directly instead, using the `Signal`
`StrategyEngine.on_tick()` already returns to its caller — never touching
the shared bus at all. See that handler's own module docstring for the
matching half of this decision.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import cast

from Sagittarius_Elite_Warrior.src.application.ports.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.preview_order.query import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.execute_order.result import (
    ExecuteOrderResult,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.trading.policies.position_sizing_bridge import (
    calculate_live_order_quantity,
)
from Sagittarius_Elite_Warrior.src.domain.trading.policies.signal_action_to_order_intent import (
    order_intent_for,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal

logger = logging.getLogger("App.LiveTradingCoordinator")

#: Sizing/leverage for the live path. Hardcoded rather than configurable
#: yet — a real "position sizing" control belongs on `EPIC-021I`'s Trading
#: screen; this task's scope is the safety pipeline the sizing feeds into,
#: not that control surface.
_LIVE_SIZING = PositionSizing(type=PositionSizingType.PERCENT_OF_EQUITY, value=20.0)
_LIVE_LEVERAGE = 1.0


class LiveTradingCoordinator:
    """@brief Turns one actionable `Signal` into `ExecuteOrderCommand`, for
    the one configured live symbol.

    @details `handle()` is called directly by `MarketTickEventHandler` —
    never via the shared event bus (see this module's own docstring for
    why). Ignores a signal for any other symbol as defense in depth:
    `MarketTickEventHandler` already filters to `live_symbol` before this
    is ever called, but a caller that skips that check must not corrupt
    per-symbol sizing/limit state this class doesn't have for any symbol
    but the one it was configured for.
    """

    def __init__(
        self,
        live_symbol: str,
        dispatcher: ICommandDispatcher,
        account_reader: ITradingAccountReader,
        metadata_provider: IMarketMetadataProvider,
    ) -> None:
        self._live_symbol = live_symbol
        self._dispatcher = dispatcher
        self._account_reader = account_reader
        self._metadata_provider = metadata_provider

    def handle(self, signal: Signal) -> None:
        if signal.symbol != self._live_symbol:
            logger.debug(
                "Ignoring signal for %s — live symbol is %s.",
                signal.symbol,
                self._live_symbol,
            )
            return

        metadata = self._metadata_provider.get_or_fetch(signal.symbol)
        if metadata is None:
            logger.debug(
                "No futures metadata for %s yet — cannot size an order.", signal.symbol
            )
            return

        status = self._account_reader.check_connection()
        if status.usdt_balance is None:
            logger.debug("No known USDT balance yet — cannot size an order.")
            return

        intent = order_intent_for(signal.action)
        reference_price = Decimal(str(signal.price))
        quantity = calculate_live_order_quantity(
            sizing=_LIVE_SIZING,
            available_balance=status.usdt_balance,
            reference_price=reference_price,
            leverage=_LIVE_LEVERAGE,
            step_size=metadata.step_size,
        )
        if quantity <= 0:
            logger.debug("Computed live order quantity was zero — nothing to send.")
            return

        command = ExecuteOrderCommand(
            order_request=PreviewOrderQuery(
                symbol=signal.symbol,
                side=intent.side,
                order_type=OrderType.MARKET,
                quantity=quantity,
                reference_price=reference_price,
                reduce_only=intent.reduce_only,
            ),
            live=True,
        )
        # `ICommandDispatcher.dispatch()`'s own signature returns `object` —
        # this module is under mypy's checked scope (unlike most of the
        # coordinator/controller call sites using this same dispatch
        # pattern, which live under `presentation/` and are excluded
        # wholesale — see `pyproject.toml`'s `[tool.mypy]` `exclude`), so a
        # bare `result: ExecuteOrderResult = ...` fails mypy here where it
        # silently wouldn't there. `cast` documents the trust explicitly
        # rather than annotating past it.
        result = cast(
            ExecuteOrderResult,
            self._dispatcher.dispatch(ExecuteOrderCommand, command),
        )
        if result.blocked:
            logger.info("Live order blocked: %s", result.blocked_by)
        else:
            logger.info(
                "Live order submitted for %s: %s", signal.symbol, signal.action.value
            )
