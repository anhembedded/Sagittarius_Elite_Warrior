r"""Desktop E2E regression for BUG-008 Backtest chart timeframe buttons.

Run from the Sagittarius-Engine workspace root on a Windows desktop session:

    .\Sagittarius_Elite_Warrior\.venv\Scripts\python.exe -m `
      Sagittarius_Elite_Warrior.scripts.backtest_timeframe_toolbar_e2e

The probe starts the real application shell, injects a deterministic local
repository before navigating to Backtest, then uses a real Qt mouse click on
the visible chart-header ``5m`` button. It is opt-in desktop release evidence,
not an ordinary CI timing gate.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

from PySide6.QtCore import Qt, QtMsgType, qInstallMessageHandler
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication
from sagittarius_engine.extensions.pyside_mvc import configure_app_qml
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    DatabaseStatusSnapshot,
    DataGap,
    IMarketDataRepository,
    RangeCoverageSnapshot,
)
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
    BackTestPresenter,
)

_SYMBOL = "BTCUSDT"
_CANDLE_COUNT = 240
_INITIAL_INTERVAL = TimeFrame.ONE_HOUR
_REQUESTED_INTERVAL = TimeFrame.FIVE_MINUTES
_PREVIEW_TIMEOUT_MS = 5_000


class _SeededMarketDataRepository(IMarketDataRepository):
    """Deterministic multi-timeframe source used solely by the desktop probe."""

    def __init__(self, klines: list[MarketData]) -> None:
        self._klines = list(klines)

    def save_klines(self, klines: list[MarketData]) -> None:
        self._klines = list(klines)

    def get_latest_kline_time(
        self, symbol: str, interval: TimeFrame
    ) -> datetime | None:
        rows = self.get_klines(symbol, interval)
        return rows[-1].open_time if rows else None

    def get_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
        order_by_desc: bool = False,
    ) -> list[MarketData]:
        rows = [
            kline
            for kline in self._klines
            if kline.symbol == symbol and kline.interval == interval.value
        ]
        if start_time is not None:
            rows = [row for row in rows if row.open_time >= start_time]
        if end_time is not None:
            rows = [row for row in rows if row.open_time <= end_time]
        rows.sort(key=lambda row: row.open_time, reverse=order_by_desc)
        return rows[:limit] if limit is not None else rows

    def count_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> int:
        return len(self.get_klines(symbol, interval, start_time, end_time, limit))

    def stream_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        offset: int | None = None,
        limit: int | None = None,
        order_by_desc: bool = False,
    ) -> Iterator[MarketData]:
        rows = self.get_klines(
            symbol, interval, start_time, end_time, None, order_by_desc
        )
        if offset is not None:
            rows = rows[offset:]
        if limit is not None:
            rows = rows[:limit]
        yield from rows

    def clear_klines(self, symbol: str, interval: TimeFrame | None = None) -> int:
        return 0

    def purge_all(self) -> int:
        return 0

    def list_available_shards(self) -> list[str]:
        return [_SYMBOL]

    def vacuum(self, symbol: str | None = None) -> None:
        pass

    def get_gaps(self, symbol: str, interval: TimeFrame) -> list[DataGap]:
        return []

    def has_any_klines(self, symbol: str) -> bool:
        return any(kline.symbol == symbol for kline in self._klines)

    def get_database_status(
        self, symbol: str, interval: TimeFrame
    ) -> DatabaseStatusSnapshot:
        rows = self.get_klines(symbol, interval)
        return DatabaseStatusSnapshot(
            first_record=rows[0].open_time if rows else None,
            last_record=rows[-1].open_time if rows else None,
            total_candles=len(rows),
            gaps=0,
        )

    def get_database_status_for_intervals(
        self, symbol: str, intervals: list[TimeFrame]
    ) -> dict[str, DatabaseStatusSnapshot]:
        return {
            interval.value: self.get_database_status(symbol, interval)
            for interval in intervals
        }

    def get_range_coverage(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None,
        end_time: datetime,
        now: datetime,
    ) -> RangeCoverageSnapshot:
        rows = self.get_klines(symbol, interval, start_time, end_time)
        rows = [row for row in rows if row.open_time < end_time]
        first_gap_after = next(
            (
                previous.open_time
                for previous, current in pairwise(rows)
                if (current.open_time - previous.open_time).total_seconds()
                > interval.to_seconds()
            ),
            None,
        )
        return RangeCoverageSnapshot(
            first_record=rows[0].open_time if rows else None,
            last_record=rows[-1].open_time if rows else None,
            total_candles=len(rows),
            distinct_candles=len({row.open_time for row in rows}),
            first_gap_after=first_gap_after,
            unclosed_candles=sum(
                bool(row.close_time and row.close_time > now) for row in rows
            ),
        )


def _make_klines(interval: TimeFrame) -> list[MarketData]:
    start = datetime(2026, 8, 1, tzinfo=UTC)
    cadence = timedelta(seconds=interval.to_seconds())
    return [
        MarketData(
            symbol=_SYMBOL,
            interval=interval.value,
            open_time=start + cadence * index,
            open_price=10_000.0 + index,
            high_price=10_010.0 + index,
            low_price=9_990.0 + index,
            close_price=10_005.0 + index,
            volume=100.0 + index,
            close_time=start + cadence * (index + 1) - timedelta(seconds=1),
            quote_asset_volume=0.0,
            number_of_trades=1,
            taker_buy_base_asset_volume=0.0,
            taker_buy_quote_asset_volume=0.0,
        )
        for index in range(_CANDLE_COUNT)
    ]


def _load_config(project_root: Path, database_directory: str) -> ConfigManager:
    config = ConfigManager()
    config.load_json(str(project_root / "src" / "config" / "app_config.json"))
    config.load_json(str(project_root / "src" / "config" / "user_config.json"))
    config.load_dict(
        {
            ConfigKeys.DATABASE_DIR.value: database_directory,
            "DEFAULT_INTERVAL": _INITIAL_INTERVAL.value,
            "DEV_BOARD_AUTOSTART_ENABLED": False,
        }
    )
    return config


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    qt_messages: list[str] = []

    def capture_qt_message(
        message_type: QtMsgType, context: object, message: str
    ) -> None:
        del context
        if message_type in {
            QtMsgType.QtWarningMsg,
            QtMsgType.QtCriticalMsg,
            QtMsgType.QtFatalMsg,
        }:
            qt_messages.append(message)

    previous_message_handler = qInstallMessageHandler(capture_qt_message)
    window: MainWindow | None = None
    engine = None
    try:
        app = QApplication.instance() or QApplication([])
        app.setQuitOnLastWindowClosed(False)
        configure_app_qml(
            Palette.as_ui_dict(), get_icon_loader(), Palette.as_icon_dict()
        )
        with tempfile.TemporaryDirectory(prefix="sagittarius-timeframe-e2e-") as db_dir:
            engine = create_app(_load_config(project_root, db_dir))
            engine.boot()
            seeded_klines = _make_klines(_INITIAL_INTERVAL) + _make_klines(
                _REQUESTED_INTERVAL
            )
            engine.context.container.singleton(
                IMarketDataRepository, _SeededMarketDataRepository(seeded_klines)
            )

            window = MainWindow(engine)
            window.show()
            window.switch_screen("backtest")
            app.processEvents()
            presenter = window._router.get_current_presenter()
            if not isinstance(presenter, BackTestPresenter):
                raise TypeError("Backtest presenter did not load in MainWindow")

            view = presenter.view
            chart = view.chart_cards[0]
            button = chart.toolbar._buttons[_REQUESTED_INTERVAL.value]
            preview_rendered = QSignalSpy(view.chartPreviewRendered)
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
            if not preview_rendered.wait(_PREVIEW_TIMEOUT_MS):
                raise RuntimeError("5m toolbar click did not render a chart preview")

            if presenter._view_model.selectedTimeframe != _REQUESTED_INTERVAL.value:
                raise RuntimeError("5m toolbar click did not update Backtest timeframe")
            if len(chart._raw_history) != _CANDLE_COUNT:
                raise RuntimeError("5m toolbar click did not replace chart candles")
            candle_step = chart._raw_history[1][0] - chart._raw_history[0][0]
            if candle_step != _REQUESTED_INTERVAL.to_seconds():
                raise RuntimeError(f"expected 5m candles, received step={candle_step}")
            if (
                view.top_widget.errors()
                or view.bottom_widget.errors()
                or view.overlay_host.quick_widget.errors()
            ):
                raise RuntimeError("Backtest QML surface reported errors")
    finally:
        if window is not None:
            window.close()
        if engine is not None:
            engine.stop()
        qInstallMessageHandler(previous_message_handler)

    if qt_messages:
        raise RuntimeError(f"Qt warnings/errors during timeframe E2E: {qt_messages}")
    print("BACKTEST_TIMEFRAME_TOOLBAR_E2E_OK")


if __name__ == "__main__":
    main()
