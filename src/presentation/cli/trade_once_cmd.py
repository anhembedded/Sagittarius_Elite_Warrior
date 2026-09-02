"""`EPIC-021G` — headless `main.py trade-once`. Runs one strategy
evaluation against the most recent locally-stored candles and, if
actionable, attempts exactly one order through the full safety pipeline
(`ExecuteOrderCommand`) — dry-run unless `--live` is passed. Runs one
round and exits; it is not a daemon (`EPIC-021G` §5)."""

import argparse
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.application.ports.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_factory import (
    build_engine,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines import (
    GetHistoricalKlinesQuery,
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
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.trading.policies.position_sizing_bridge import (
    calculate_live_order_quantity,
)
from Sagittarius_Elite_Warrior.src.domain.trading.policies.signal_action_to_order_intent import (
    order_intent_for,
)
from Sagittarius_Elite_Warrior.src.domain.trading.policies.trading_limit_policy import (
    TradingLimitPolicy,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
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
        print(f"Interval không hợp lệ: {args.interval!r}")
        return

    strategy_registry = app.container.resolve(StrategyRegistry)
    if args.strategy not in strategy_registry.available():
        print(
            f"Chiến lược không tồn tại: {args.strategy!r}. "
            f"Có sẵn: {sorted(strategy_registry.available())}"
        )
        return

    candles: list[MarketData] = app.dispatch(
        GetHistoricalKlinesQuery,
        GetHistoricalKlinesQuery(
            symbol=args.symbol, interval=interval, limit=_WARMUP_CANDLE_LIMIT
        ),
    )
    if not candles:
        print(
            f"Chưa có dữ liệu nến cho {args.symbol} {interval.value} — chạy "
            "`sync` trước."
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
        print(f"Không có futures metadata cho {args.symbol}.")
        return

    account_reader = app.container.resolve(ITradingAccountReader)
    status = account_reader.check_connection()
    if status.usdt_balance is None:
        print("Không biết số dư USDT (chưa cấu hình credentials hoặc mất kết nối).")
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
        print("Khối lượng tính được bằng 0 — không có gì để gửi.")
        return

    command = ExecuteOrderCommand(
        order_request=PreviewOrderQuery(
            symbol=args.symbol,
            side=intent.side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            reference_price=reference_price,
            reduce_only=intent.reduce_only,
        ),
        live=args.live,
    )
    result: ExecuteOrderResult = app.dispatch(ExecuteOrderCommand, command)

    if result.limit_context is not None:
        limits_policy = app.container.resolve(TradingLimitPolicy)
        print(
            format_limit_checks(
                result.limit_checks, result.limit_context, limits_policy.limits
            )
        )

    print(format_result(result, args.live))
