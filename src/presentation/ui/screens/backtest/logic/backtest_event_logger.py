from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.presentation.ui.common.base_event_logger import (
    BaseEventLogger,
)

if TYPE_CHECKING:
    from sagittarius_engine.extensions.pyside_mvc.QmlShared.log_list_model import (
        LogListModel,
    )


class BacktestEventLogger(BaseEventLogger):
    """
    @brief Domain-driven event logger specializing in Backtest execution lifecycle.
    @details Encapsulates message formatting, severity determination, and dev-mode
    filtering for Backtest operations, keeping BackTestPresenter focused purely on
    orchestration.
    """

    def __init__(
        self,
        log_model: LogListModel | None = None,
        is_dev_mode: bool = False,
        emit_signal: Callable[[str, str, bool], None] | None = None,
    ) -> None:
        super().__init__(
            log_model=log_model, is_dev_mode=is_dev_mode, emit_signal=emit_signal
        )

    def log_backtest_started(
        self,
        strategy_name: str,
        timeframe: str,
        capital: float,
        currency: str,
        symbol: str = "BTCUSDT",
    ) -> None:
        self.info(
            f"Bắt đầu chạy Backtest: {strategy_name} ({timeframe}) | Cặp: {symbol} | Vốn ban đầu: {capital:,.0f} {currency}"
        )

    def log_klines_loaded(
        self, count: int, symbol: str, start_date: str = "", end_date: str = ""
    ) -> None:
        range_str = f" ({start_date} -> {end_date})" if start_date and end_date else ""
        self.info(f"Đã nạp {count:,} nến lịch sử cho {symbol}{range_str}.")

    def log_indicators_calculated(
        self, elapsed_ms: float, indicator_names: list[str] | None = None
    ) -> None:
        names_str = f": {', '.join(indicator_names)}" if indicator_names else ""
        self.dev_trace("calculate_indicators", elapsed_ms=elapsed_ms, names=names_str)

    def log_backtest_completed(
        self,
        duration_sec: float,
        trade_count: int,
        net_pnl: float,
        win_rate: float,
        currency: str = "USDT",
    ) -> None:
        pnl_sign = "+" if net_pnl > 0 else ""
        self.success(
            f"Hoàn thành Backtest ({duration_sec:.2f}s): {trade_count} lệnh | Net PnL: {pnl_sign}{net_pnl:,.2f} {currency} | Win Rate: {win_rate:.1f}%"
        )

    def log_backtest_failed(self, error_message: str) -> None:
        self.error(f"Lỗi Backtest: {error_message}")

    def log_backtest_empty(self, reason: str = "") -> None:
        suffix = f": {reason}" if reason else ""
        self.warning(
            f"Backtest hoàn thành nhưng không phát sinh lệnh giao dịch nào{suffix}."
        )

    def log_signal_event(
        self, symbol: str, side: str, price: float, time_str: str = ""
    ) -> None:
        time_prefix = f"[{time_str}] " if time_str else ""
        self.log(
            f"{time_prefix}Tín hiệu: {side.upper()} {symbol} @ {price:,.2f}",
            level="info",
            is_dev=True,
        )

    def log_sync_event(self, message: str, is_error: bool = False) -> None:
        if is_error:
            self.error(f"[DataSync] {message}")
        else:
            self.info(f"[DataSync] {message}")
