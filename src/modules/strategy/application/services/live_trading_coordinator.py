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
from collections.abc import Mapping
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal import Signal
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.strategy_owner import (
    STRATEGY_OWNER,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.policies.position_sizing_bridge import (
    calculate_live_order_quantity,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.policies.signal_action_to_order_intent import (
    order_intent_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.live_order_blocked_event import (
    LiveOrderBlockedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holdings_close_policy import (
    sellable_spot_quantity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.LiveTradingCoordinator")

#: `EPIC-027N` — Phase 1 Spot trades USDT-quoted pairs only (ADR D9/O4), the
#: same quote asset `emergency_stop/handler.py`/`spot_account_reader.py`
#: already carry.
_QUOTE_ASSET = "USDT"


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
        order_submission: IOrderSubmission,
        account_reader: ITradingAccountReader,
        metadata_provider: IMarketMetadataProvider,
        event_publisher: IEventPublisher,
        trading_session: ITradingSession,
        sizing_percent: float,
        leverage: float,
        *,
        venue: TradingVenue,
    ) -> None:
        #: `EPIC-028C` — the venue this coordinator's orders go to, stamped
        #: on every `LiveOrderBlockedEvent` so only that venue's desk shows it.
        self._venue = venue
        self._live_symbol = live_symbol
        self._order_submission = order_submission
        self._account_reader = account_reader
        self._metadata_provider = metadata_provider
        self._event_publisher = event_publisher
        #: `EPIC-027N` — the venue's market type and, on Spot, the holdings
        #: baseline a SELL signal must size against (never below it).
        self._trading_session = trading_session
        #: `BUG-084` — real config-backed controls
        #: (`ConfigKeys.TRADING_LIVE_SIZING_PERCENT`/`TRADING_LIVE_LEVERAGE`),
        #: not the hardcoded 20%/1x this class shipped with. That fixed
        #: combination, next to `trading.max_notional_per_order_usdt`'s
        #: 500 USDT cap, left a usable-balance window of roughly
        #: 500-2,500 USDT — outside it (including Futures Testnet's own
        #: 15,000 USDT default balance), no order the strategy ever
        #: proposed could clear the cap, and nothing said why.
        self._sizing = PositionSizing(
            type=PositionSizingType.PERCENT_OF_EQUITY, value=sizing_percent
        )
        self._leverage = leverage

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
        snapshot = self._trading_session.snapshot()
        is_spot_sell = (
            snapshot.market_type is MarketType.SPOT
            and signal.action is SignalAction.SELL
        )
        if is_spot_sell:
            if snapshot.spot_baseline_holdings is None:
                reason = (
                    "No Spot holdings baseline recorded this session — "
                    "the strategy's SELL signal was not sent."
                )
                logger.info(reason)
                self._event_publisher.publish(
                    LiveOrderBlockedEvent(
                        symbol=signal.symbol, reason=reason, venue=self._venue
                    )
                )
                return
            quantity = self._sellable_spot_quantity(
                signal.symbol,
                status.holdings or (),
                metadata,
                snapshot.spot_baseline_holdings,
            )
        else:
            quantity = calculate_live_order_quantity(
                sizing=self._sizing,
                available_balance=status.usdt_balance,
                reference_price=reference_price,
                leverage=self._leverage,
                step_size=metadata.step_size,
            )
        if quantity <= 0:
            reason = (
                "Spot holding surplus over the baseline floors to dust — "
                "nothing to send."
                if is_spot_sell
                else (
                    f"Computed live order quantity was zero for balance "
                    f"{status.usdt_balance} at {self._sizing.value}% sizing — "
                    f"nothing to send."
                )
            )
            logger.info(reason)
            # `BUG-084` — this used to be a `logger.debug()` line, functionally
            # invisible: an operator watching the Trading screen had no way
            # to tell "no signal fired" from "a signal fired but sizing
            # produced nothing to send".
            self._event_publisher.publish(
                LiveOrderBlockedEvent(
                    symbol=signal.symbol, reason=reason, venue=self._venue
                )
            )
            return

        order_request = OrderRequest(
            symbol=signal.symbol,
            side=intent.side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            reference_price=reference_price,
            reduce_only=intent.reduce_only,
            # `EPIC-025` PR 2.1f — the strategy's own lease, so the symbol it
            # claimed on arm does not refuse the order it armed to place.
            # Omitting this would leave `OrderRequest`'s `MANUAL_OWNER` default
            # here and block the strategy with its own lease, which is why that
            # default is the unprivileged one: the mistake fails safe.
            owner_id=STRATEGY_OWNER,
        )
        # `EPIC-025` PR 1.3c-2 — the `cast` that used to stand here is gone
        # with the untyped dispatch it documented: `IOrderSubmission.submit()`
        # declares `ExecuteOrderResult`, so mypy (which checks this file,
        # unlike the `presentation/` call sites it is excluded from) reads the
        # type instead of being told to trust one.
        # `BUG-090` — an exchange rejection (margin, rate limit, a
        # notional/precision edge `preview.notional_check` didn't catch)
        # is expected, named domain state, not a bug: it must not escape
        # to `MarketTickEventHandler.handle()`, which has no `except` of
        # its own and would otherwise let one rejected order take down
        # tick processing for the rest of the session.
        try:
            result = self._order_submission.submit(order_request, live=True)
        except OrderRejectedByExchangeError as exc:
            logger.warning("Live order rejected by exchange: %s", exc)
            return
        except Exception as exc:  # noqa: BLE001 - worker boundary: a network/exchange
            # failure below `ITradingClient` must not propagate through this
            # application-layer coordinator (`architecture-rule.md` §3 bars
            # importing infra-specific exception types like
            # `BinanceRequestException` here to narrow this further) and
            # crash the rest of this session's tick processing.
            logger.error("Live order attempt failed — network/exchange error: %s", exc)
            return
        if result.blocked:
            logger.info("Live order blocked: %s", result.blocked_by)
            # `BUG-084` — a blocked order used to be a log line only; the
            # Trading screen had no way to show why the strategy's signal
            # never became an order. Reaches `OrderFeed.orderBlocked` ->
            # `TradingPresenter`'s own log panel.
            self._event_publisher.publish(
                LiveOrderBlockedEvent(
                    symbol=signal.symbol,
                    reason=str(result.blocked_by),
                    venue=self._venue,
                )
            )
        else:
            logger.info(
                "Live order submitted for %s: %s", signal.symbol, signal.action.value
            )

    def _sellable_spot_quantity(
        self,
        symbol: str,
        holdings: tuple[SpotHolding, ...],
        metadata: SymbolOrderMetadata,
        baseline: Mapping[str, Decimal],
    ) -> Decimal:
        """@brief AC4 — a strategy's own SELL signal sizes from the actual
        holding, never a percent of balance, and never below the session's
        Spot baseline (the identical rule `EmergencyStopCommandHandler`
        already applies, reused via the same pure policy rather than a
        second, divergent one).
        """
        base_asset = symbol.removesuffix(_QUOTE_ASSET)
        current_total = next(
            (holding.total for holding in holdings if holding.asset == base_asset),
            Decimal(0),
        )
        baseline_quantity = baseline.get(base_asset, Decimal(0))
        return sellable_spot_quantity(
            current_total, baseline_quantity, metadata.step_size_for(OrderType.MARKET)
        )
