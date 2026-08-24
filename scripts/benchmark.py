import os
import sys
import time
from datetime import UTC, datetime, timedelta

# Cấu hình sys.path để import thẳng từ thư viện của app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.ema_20_script import (
    Ema20Script,
)
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.ema_50_script import (
    Ema50Script,
)
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.ema_100_script import (
    Ema100Script,
)
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.ema_200_script import (
    Ema200Script,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.indicator_script_runner import (
    IndicatorScriptRunner,
    qualified_line_name,
)


def create_mock_candles(count: int):
    candles = []
    base_time = datetime(2023, 1, 1, tzinfo=UTC)
    for i in range(count):
        close_time = base_time + timedelta(minutes=i)
        candles.append(
            MarketData(
                symbol="BTCUSDT",
                interval="1m",
                open_time=close_time - timedelta(minutes=1),
                open_price=100.0 + i,
                high_price=110.0 + i,
                low_price=90.0 + i,
                close_price=105.0 + i,
                volume=1000.0,
                close_time=close_time,
                quote_asset_volume=100000.0,
                number_of_trades=500,
                taker_buy_base_asset_volume=500.0,
                taker_buy_quote_asset_volume=50000.0,
                is_closed=True,
            )
        )
    return candles


class BenchmarkMetrics:
    def __init__(self):
        self.total_data_copied = 0
        self.emit_count = 0

    def mock_emit_line(self, name: str, x_data: list, y_data: list):
        # Mô phỏng Qt Signal: Qt phải copy list (x_data, y_data) xuyên Thread để báo UI vẽ
        list_x = list(x_data)
        list_y = list(y_data)
        self.total_data_copied += len(list_x) + len(list_y)
        self.emit_count += 1

    def mock_emit_region(self, *args, **kwargs):
        pass

    def mock_emit_info(self, *args, **kwargs):
        pass

    def mock_emit_markers(self, *args, **kwargs):
        pass

    def mock_on_error(self, *args, **kwargs):
        pass


def run_current_approach(candles, registry, scripts_to_run):
    metrics = BenchmarkMetrics()
    runner = IndicatorScriptRunner(
        registry=registry,
        emit_line=metrics.mock_emit_line,
        emit_region=metrics.mock_emit_region,
        emit_info=metrics.mock_emit_info,
        emit_markers=metrics.mock_emit_markers,
        on_error=metrics.mock_on_error,
    )
    # Khởi tạo 4 chỉ báo EMA
    runner.rebuild(scripts_to_run)

    start = time.time()
    # Chạy logic hiện tại của app
    runner.feed_all(candles)
    end = time.time()

    return end - start, metrics


def run_batch_approach(candles, registry, scripts_to_run):
    metrics = BenchmarkMetrics()

    runner = IndicatorScriptRunner(
        registry=registry,
        emit_line=lambda *args: (
            None
        ),  # Vô hiệu hoá emit liên tục trong vòng lặp của app
        emit_region=metrics.mock_emit_region,
        emit_info=metrics.mock_emit_info,
        emit_markers=metrics.mock_emit_markers,
        on_error=metrics.mock_on_error,
    )
    runner.rebuild(scripts_to_run)

    start = time.time()

    # 1. Tính toán mọi thứ trước
    for candle in candles:
        timestamp = float(candle.close_time.timestamp())
        for active in runner.active.values():
            for line_name, line in active.script.compute(candle).items():
                active.record(line_name, timestamp, line.value)

    # 2. Gọi hàm vẽ (emit_line) 1 LẦN DUY NHẤT CHO MỖI ĐƯỜNG EMA
    for key, active in runner.active.items():
        for line_name, (x_data, y_data) in active.series.items():
            metrics.mock_emit_line(qualified_line_name(key, line_name), x_data, y_data)

    end = time.time()

    return end - start, metrics


def main():
    print("Khởi tạo IndicatorScriptRegistry...")
    registry = IndicatorScriptRegistry()
    registry.register("ema_20", Ema20Script)
    registry.register("ema_50", Ema50Script)
    registry.register("ema_100", Ema100Script)
    registry.register("ema_200", Ema200Script)

    scripts_to_run = ["ema_20", "ema_50", "ema_100", "ema_200"]

    candles_count = 10000
    print(f"Tạo {candles_count} nến (MarketData) mock...")
    candles = create_mock_candles(candles_count)

    print(
        f"\n--- BENCHMARK: CHẠY 4 CHỈ BÁO ({', '.join(scripts_to_run)}) - {candles_count} NẾN ---"
    )

    current_time, current_metrics = run_current_approach(
        candles, registry, scripts_to_run
    )
    print("\n[HIỆN TẠI] Runner phát Signal báo vẽ từng nến cho TỪNG CHỈ BÁO:")
    print(f"- Thời gian xử lý : {current_time:.4f} giây")
    print(f"- Số lần gọi vẽ (emit) : {current_metrics.emit_count:,} lần")
    print(f"- Data rác bị RAM copy: {current_metrics.total_data_copied:,} phần tử")

    batch_time, batch_metrics = run_batch_approach(candles, registry, scripts_to_run)
    print("\n[ĐỀ XUẤT] Logic gộp batching trước khi vẽ:")
    print(f"- Thời gian xử lý : {batch_time:.4f} giây")
    print(f"- Số lần gọi vẽ (emit) : {batch_metrics.emit_count:,} lần")
    print(f"- Data rác bị RAM copy: {batch_metrics.total_data_copied:,} phần tử")

    if batch_time > 0:
        print(
            f"\n=> KẾT LUẬN: Với 4 EMA, thuật toán batch nhanh hơn gấp {current_time / batch_time:.1f} lần!"
        )
        print(
            f"=> Rác luân chuyển qua RAM giảm {(current_metrics.total_data_copied - batch_metrics.total_data_copied) / current_metrics.total_data_copied * 100:.2f}%"
        )


if __name__ == "__main__":
    main()
