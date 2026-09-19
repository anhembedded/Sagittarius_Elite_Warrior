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
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    ExchangeRequestCancelledError,
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.symbol_market_metadata import (
    SymbolMarketMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_presenter import (
    DataManagementPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.shell.contribution_assembly import (
    assemble_contributions,
)
from Sagittarius_Elite_Warrior.src.shell.screen_wiring import build_screen_registry
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import UIMode
from Sagittarius_Elite_Warrior.src.support.ui_kit.sidebar import Sidebar
from Sagittarius_Elite_Warrior.src.support.ui_kit.theme_bootstrap import (
    seed_app_theme,
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

    def get_symbol_metadata(self) -> list[SymbolMarketMetadata]:
        """`BUG-127` added this to the port. This probe's subject is a sync
        that hangs on shutdown, not exchange filters, so it answers empty —
        spelled out because `IExchangeClient` is an ABC and a missing method is
        a construction-time `TypeError` (`ONBOARDING` §8 trap 11)."""
        return []


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
        # Any process that builds this app's widgets seeds its theme the
        # same way the bootstrapper does — one call, one place
        # (`theme_bootstrap.py`). BOT-132: this used to be a partial copy
        # here (bridge only, no `configure_app_qml()`), which the QML
        # embedding rework turned from silently-wrong into a hard failure.
        seed_app_theme()
        # `EPIC-025F` PR 5.2: every screen (the shell's own Welcome/Settings,
        # and every module's, Database included) now arrives through the
        # same `assemble_contributions()` the real GUI entry point calls —
        # nothing here hand-lists a screen any more, the same way
        # `tests/conftest.py`'s `real_screen_registry` no longer does either.
        contributions = assemble_contributions(engine.context.container, dev_mode=False)
        screen_registry = build_screen_registry(contributions)
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
