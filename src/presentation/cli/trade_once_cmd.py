"""`EPIC-021G` — headless `main.py trade-once`. Runs one strategy
evaluation against the most recent locally-stored candles and, if
actionable, attempts exactly one order through the full safety pipeline
(`ExecuteOrderCommand`) — dry-run unless `--live` is passed. Runs one
round and exits; it is not a daemon (`EPIC-021G` §5)."""

import argparse
from decimal import Decimal

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_factory import (
    build_engine,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.policies.position_sizing_bridge import (
    calculate_live_order_quantity,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.policies.signal_action_to_order_intent import (
    order_intent_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.invalid_order_for_submission import (
    InvalidOrderForSubmissionError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.trade_once_formatter import (
    format_candle_and_signal,
    format_limit_checks,
    format_result,
)
from sagittarius_engine import App

#: How many closed candles to warm indicators up on before trusting the
#: latest one's signal — generous enough for this repo's slower
#: strategies (e.g. EMA 200) without a per-strategy lookback table.
_WARMUP_CANDLE_LIMIT = 500

#: Sizing/leverage for this CLI's own order, same fixed values
#: `LiveTradingCoordinator` uses — see that module for why they are not
#: configurable yet.
_SIZING = PositionSizing(type=PositionSizingType.PERCENT_OF_EQUITY, value=20.0)
_LEVERAGE = 1.0


def execute_trade_once(app: App, args: argparse.Namespace) -> None:
    try:
        interval = TimeFrame(args.interval)
    except ValueError:
        print(f"Invalid interval: {args.interval!r}")
        return

    strategy_registry = app.container.resolve(StrategyRegistry)
    if args.strategy not in strategy_registry.available():
        print(
            f"Strategy does not exist: {args.strategy!r}. "
            f"Available: {sorted(strategy_registry.available())}"
        )
        return

    # `EPIC-025` PR 1.1 — resolved from the container rather than dispatched,
    # so this command names only market_data's contract. `app.dispatch` stays
    # in use below for everything that is still a command.
    candles: tuple[MarketData, ...] = app.container.resolve(IHistoricalKlines).load(
        args.symbol, interval, limit=_WARMUP_CANDLE_LIMIT
    )
    if not candles:
        print(
            f"No candle data for {args.symbol} {interval.value} yet — run `sync` first."
        )
        return

    engine = build_engine(
        strategy_registry, args.strategy, app.container.resolve(IEventPublisher)
    )
    signal = None
    for candle in candles:
        signal = engine.on_tick(candle)

    print(format_candle_and_signal(candles[-1], args.strategy, signal))
    if signal is None:
        return

    metadata_provider = app.container.resolve(IMarketMetadataProvider)
    metadata = metadata_provider.get_or_fetch(args.symbol)
    if metadata is None:
        print(f"No futures metadata available for {args.symbol}.")
        return

    account_reader = app.container.resolve(ITradingAccountReader)
    status = account_reader.check_connection()
    if status.usdt_balance is None:
        print("USDT balance unknown (credentials not configured or connection lost).")
        return

    intent = order_intent_for(signal.action)
    reference_price = Decimal(str(signal.price))
    quantity = calculate_live_order_quantity(
        sizing=_SIZING,
        available_balance=status.usdt_balance,
        reference_price=reference_price,
        leverage=_LEVERAGE,
        step_size=metadata.step_size,
    )
    if quantity <= 0:
        print("Calculated quantity is 0 — nothing to send.")
        return

    order_request = OrderRequest(
        symbol=args.symbol,
        side=intent.side,
        order_type=OrderType.MARKET,
        quantity=quantity,
        reference_price=reference_price,
        reduce_only=intent.reduce_only,
    )
    # `BUG-090` — a live order the app's own `notional_check` gate didn't
    # catch (e.g. a margin/precision/rate-limit rejection, which is real
    # exchange state this app cannot pre-check) must print a friendly
    # message like `order-dry-run` already does, not crash with a raw
    # traceback — a rejection is an expected, named outcome, not a bug.
    try:
        result: ExecuteOrderResult = app.container.resolve(IOrderSubmission).submit(
            order_request, live=args.live
        )
    except OrderRejectedByExchangeError as exc:
        print(f"Exchange rejected the order: {exc}")
        return
    except InvalidOrderForSubmissionError as exc:
        print(f"Order is not valid for submission: {exc}")
        return
    except (BinanceAPIException, BinanceRequestException, RequestException):
        print(
            "Could not send the order to the exchange — check your network connection and try again."
        )
        return

    if result.limit_context is not None:
        limits_policy = app.container.resolve(TradingLimitPolicy)
        print(
            format_limit_checks(
                result.limit_checks, result.limit_context, limits_policy.limits
            )
        )

    print(format_result(result, args.live))
