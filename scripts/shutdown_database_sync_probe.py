"""Process-level regression probe for closing the app during Data Management sync (BUG-023)."""

from __future__ import annotations

import os
import sys
import tempfile
import threading
from collections.abc import Callable, Iterator
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
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_presenter import (
    DataManagementPresenter,
)
from sagittarius_engine.extensions.pyside_mvc import configure_app_qml
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

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

    def stream_historical_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_str: str | datetime,
        end_str: str | datetime | None = None,
        progress_callback: Callable[[int], None] | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
    ) -> Iterator[list[MarketData]]:
        del symbol, interval, start_str, end_str, progress_callback
        self.started.set()
        if cancellation_requested is None:
            raise RuntimeError("Shutdown probe requires a cancellation callback")
        while not cancellation_requested():
            self.finished.wait(0.01)
        self.finished.set()
        raise ExchangeRequestCancelled("shutdown probe cancelled")

    def get_available_symbols(self) -> list[str]:
        return ["BTCUSDT", "ETHUSDT"]


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "single_sync"
    project_root = Path(__file__).resolve().parents[1]
    config = ConfigManager()
    config.load_json(str(project_root / "src" / "config" / "app_config.json"))
    config.load_json(str(project_root / "src" / "config" / "user_config.json"))

    with tempfile.TemporaryDirectory(prefix="sagittarius-shutdown-db-probe-") as db_dir:
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

        app_instance = QApplication.instance()
        app = (
            app_instance if isinstance(app_instance, QApplication) else QApplication([])
        )
        app.setQuitOnLastWindowClosed(False)
        configure_app_qml(
            Palette.as_ui_dict(), get_icon_loader(), Palette.as_icon_dict()
        )
        window = MainWindow(engine)
        window.switch_screen("data_management")
        presenter = window._router.get_current_presenter()
        if not isinstance(presenter, DataManagementPresenter):
            raise TypeError("Data management presenter did not load")

        if mode == "single_sync":
            presenter._trigger_single_sync("BTCUSDT", "1h")
        elif mode == "bulk_sync":
            fsm = getattr(presenter, "fsm", None)
            if fsm is not None:
                fsm.transition_to(UIMode.SYNCING)
            presenter._cancellation_token = CancellationToken()
            presenter._thread_manager.submit(
                presenter._run_bulk_sync,
                [("BTCUSDT", "1h")],
                presenter._cancellation_token,
            )

        elif mode == "repair_gap":
            presenter._on_repair_gap(
                "BTCUSDT",
                "1h",
                "2024-01-01T00:00:00",
                "2024-01-02T00:00:00",
            )
        else:
            raise ValueError(f"Unknown mode: {mode}")

        if not exchange.started.wait(_START_TIMEOUT_SECONDS):
            raise RuntimeError(f"Data management {mode} worker did not start")

        window.close()
        app.processEvents()
        engine.stop()
        if not exchange.finished.wait(_FINISH_TIMEOUT_SECONDS):
            raise RuntimeError(
                f"Data management {mode} worker ignored desktop shutdown"
            )
        print(f"SHUTDOWN_DB_SYNC_PROBE_OK_{mode.upper()}")


if __name__ == "__main__":
    main()
