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
from sagittarius_engine.extensions.pyside_mvc import get_theme_bridge
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_client import (
    ExchangeRequestCancelledError,
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.components.sidebar import Sidebar
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.presentation.ui.registry import ScreenRegistry
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.module import (
    BacktestScreenModule,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.module import (
    DashboardScreenModule,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_presenter import (
    DataManagementPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.module import (
    DatabaseScreenModule,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.module import (
    SettingsScreenModule,
)

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
        raise ExchangeRequestCancelledError("shutdown probe cancelled")

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
        raise ExchangeRequestCancelledError("shutdown probe cancelled")

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
        # EPIC-006F: no QML left in this app — apply_role() is the only
        # remaining reader of get_theme_bridge(), and it must be seeded
        # directly before the first widget is constructed (see
        # app_bootstrapper.py's own bootstrap sequence, which this probe
        # mirrors). configure_app_qml() used to do this as a side effect of
        # creating the first QML-hosted view; there is no such view anymore.
        # Same engine-annotation gap as `scripts/preview_qml.py` — see the
        # comment there. Runtime takes the size tokens fine.
        get_theme_bridge(Palette.as_ui_dict())  # type: ignore[arg-type]
        screen_registry = ScreenRegistry()
        for module_cls in (
            DashboardScreenModule,
            DatabaseScreenModule,
            SettingsScreenModule,
            BacktestScreenModule,
        ):
            screen_registry.register_module(module_cls(), engine.container)
        window = MainWindow(engine, screen_registry, sidebar_factory=Sidebar)
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
