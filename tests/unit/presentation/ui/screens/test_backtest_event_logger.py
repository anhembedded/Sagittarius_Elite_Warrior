from __future__ import annotations

from unittest.mock import MagicMock

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_event_logger import (
    BacktestEventLogger,
)


def test_backtest_event_logger_lifecycle_methods() -> None:
    mock_log_model = MagicMock()
    logger = BacktestEventLogger(log_model=mock_log_model, is_dev_mode=False)

    logger.log_backtest_started(
        strategy_name="EMA Crossover",
        timeframe="15m",
        capital=50000,
        currency="USDT",
        symbol="BTCUSDT",
    )
    mock_log_model.append.assert_called_once()
    assert "EMA Crossover" in mock_log_model.append.call_args[0][0]
    assert "50,000" in mock_log_model.append.call_args[0][0]

    mock_log_model.reset_mock()
    logger.log_klines_loaded(2000, "BTCUSDT", "2026-01-01", "2026-02-01")
    mock_log_model.append.assert_called_once()
    assert "2,000 nến" in mock_log_model.append.call_args[0][0]

    mock_log_model.reset_mock()
    logger.log_backtest_completed(
        duration_sec=0.45,
        trade_count=12,
        net_pnl=1250.50,
        win_rate=66.7,
        currency="USDT",
    )
    mock_log_model.append.assert_called_once()
    assert "Hoàn thành" in mock_log_model.append.call_args[0][0]
    assert "+1,250.50 USDT" in mock_log_model.append.call_args[0][0]

    mock_log_model.reset_mock()
    logger.log_backtest_failed("Missing Kline Data")
    mock_log_model.append.assert_called_once()
    assert "Lỗi Backtest" in mock_log_model.append.call_args[0][0]

    mock_log_model.reset_mock()
    logger.log_backtest_empty("No matching range")
    mock_log_model.append.assert_called_once()
    assert "không phát sinh lệnh" in mock_log_model.append.call_args[0][0]


def test_backtest_event_logger_dev_mode_traces() -> None:
    mock_log_model = MagicMock()
    logger = BacktestEventLogger(log_model=mock_log_model, is_dev_mode=False)

    logger.log_indicators_calculated(
        elapsed_ms=12.5, indicator_names=["EMA_9", "EMA_21"]
    )
    mock_log_model.append.assert_not_called()

    logger.log_signal_event("BTCUSDT", "buy", 45000.0, "12:00:00")
    mock_log_model.append.assert_not_called()

    # Enable dev mode
    logger.is_dev_mode = True
    logger.log_indicators_calculated(
        elapsed_ms=12.5, indicator_names=["EMA_9", "EMA_21"]
    )
    assert mock_log_model.append.call_count == 1
    assert "calculate_indicators" in mock_log_model.append.call_args[0][0]

    mock_log_model.reset_mock()
    logger.log_signal_event("BTCUSDT", "buy", 45000.0, "12:00:00")
    assert mock_log_model.append.call_count == 1
    assert "BUY BTCUSDT" in mock_log_model.append.call_args[0][0]


def test_backtest_event_logger_user_selection_methods() -> None:
    mock_log_model = MagicMock()
    logger = BacktestEventLogger(log_model=mock_log_model, is_dev_mode=False)

    logger.log_strategy_selected("Ema Crossover", "ema_crossover")
    mock_log_model.append.assert_called_once_with(
        "Đã chọn chiến lược: Ema Crossover (ema_crossover)", level="info"
    )

    mock_log_model.reset_mock()
    logger.log_timeframe_selected("15m")
    mock_log_model.append.assert_called_once_with(
        "Đã đổi khung thời gian: 15m", level="info"
    )

    mock_log_model.reset_mock()
    logger.log_time_range_selected("1_month", "2026-01-01", "2026-02-01")
    mock_log_model.append.assert_called_once_with(
        "Đã chọn khoảng thời gian: 1_month (2026-01-01 -> 2026-02-01)", level="info"
    )

    mock_log_model.reset_mock()
    logger.log_capital_updated(100000.0, "USDT")
    mock_log_model.append.assert_called_once_with(
        "Đã cập nhật vốn ban đầu: 100,000 USDT", level="info"
    )

    mock_log_model.reset_mock()
    logger.log_bot_params_saved("Ema Crossover", {"fast_period": 9, "slow_period": 21})
    mock_log_model.append.assert_called_once_with(
        "Đã lưu thông số chiến lược (Ema Crossover): fast_period=9, slow_period=21",
        level="info",
    )

    mock_log_model.reset_mock()
    logger.log_indicator_toggled("EMA 20", True)
    mock_log_model.append.assert_called_once_with(
        "Bật chỉ báo tham chiếu: EMA 20", level="info"
    )
