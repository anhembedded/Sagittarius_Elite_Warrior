"""Process-level regression probe for closing the app during Backtest sync."""

from __future__ import annotations

import os
import tempfile
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_client import (
    ExchangeRequestCancelled,
    IExchangeClient,
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
from sagittarius_engine.extensions.pyside_mvc import configure_app_qml
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

_START_TIMEOUT_SECONDS = 5.0
_FINISH_TIMEOUT_SECONDS = 5.0


class _BlockingExchangeClient(IExchangeClient):
    """Deterministic external adapter that exits only through cancellation."""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.finished = threading.Event()

    def get_historical_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_str: str | datetime,
        end_str: str | datetime | None = None,
        progress_callback: Callable[[int], None] | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
    ) -> list[MarketData]:
        del symbol, interval, start_str, end_str, progress_callback
        self.started.set()
        if cancellation_requested is None:
            raise RuntimeError("Shutdown probe requires a cancellation callback")
        while not cancellation_requested():
            self.finished.wait(0.01)
        self.finished.set()
        raise ExchangeRequestCancelled("shutdown probe cancelled")

    def get_available_symbols(self) -> list[str]:
        return []


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    config = ConfigManager()
    config.load_json(str(project_root / "src" / "config" / "app_config.json"))
    config.load_json(str(project_root / "src" / "config" / "user_config.json"))

    with tempfile.TemporaryDirectory(prefix="sagittarius-shutdown-probe-") as db_dir:
        config.load_dict(
            {
                ConfigKeys.DATABASE_DIR.value: db_dir,
                "DEV_BOARD_AUTOSTART_ENABLED": False,
            }
        )
        engine = create_app(config)
        engine.boot()
        exchange = _BlockingExchangeClient()
        engine.container.singleton(IExchangeClient, exchange)

        app = QApplication.instance() or QApplication([])
        app.setQuitOnLastWindowClosed(False)
        configure_app_qml(
            Palette.as_ui_dict(), get_icon_loader(), Palette.as_icon_dict()
        )
        window = MainWindow(engine)
        window.switch_screen("backtest")
        presenter = window._router.get_current_presenter()
        if not isinstance(presenter, BackTestPresenter):
            raise TypeError("Backtest presenter did not load")

        presenter._last_no_data_config = presenter._get_current_config()
        presenter._view_model.requestSync()
        if not exchange.started.wait(_START_TIMEOUT_SECONDS):
            raise RuntimeError("Backtest sync worker did not start")

        window.close()
        app.processEvents()
        engine.stop()
        if not exchange.finished.wait(_FINISH_TIMEOUT_SECONDS):
            raise RuntimeError("Backtest sync worker ignored desktop shutdown")
        print("SHUTDOWN_SYNC_PROBE_OK")


if __name__ == "__main__":
    main()
