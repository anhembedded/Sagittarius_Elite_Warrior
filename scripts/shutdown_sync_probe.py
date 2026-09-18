"""Process-level regression probe for closing the app during Backtest sync."""

from __future__ import annotations

import os
import tempfile
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collections.abc import Iterator

from PySide6.QtWidgets import QApplication
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.module import (
    BacktestScreenModule,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    ExchangeRequestCancelledError,
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.symbol_market_metadata import (
    SymbolMarketMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.module import (
    DatabaseScreenModule,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.module import (
    DashboardScreenModule,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.shell.legacy_screen_adapter import (
    as_screen_descriptor,
)
from Sagittarius_Elite_Warrior.src.shell.settings.settings_screen import (
    settings_screen,
)
from Sagittarius_Elite_Warrior.src.shell.welcome.welcome_screen import welcome_screen
from Sagittarius_Elite_Warrior.src.support.ui_kit.registry import ScreenRegistry
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
        """Mirrors `get_historical_klines` above: blocks until cancelled,
        then raises. `SyncMarketDataCommandHandler` calls this one now
        (BUG-025), so this is what the probe must actually block in for the
        shutdown-during-sync scenario to be real. The real implementation is
        a lazy generator; this one raises synchronously on call instead of
        on first iteration — harmless here, since the handler's own
        `for chunk in self.exchange_client.stream_historical_klines(...)`
        calls and iterates it on the same line."""
        del symbol, interval, start_str, end_str, progress_callback
        self.started.set()
        if cancellation_requested is None:
            raise RuntimeError("Shutdown probe requires a cancellation callback")
        while not cancellation_requested():
            self.finished.wait(0.01)
        self.finished.set()
        raise ExchangeRequestCancelledError("shutdown probe cancelled")

    def get_available_symbols(self) -> list[str]:
        return []

    def get_symbol_metadata(self) -> list[SymbolMarketMetadata]:
        """`BUG-127` added this to the port. This probe blocks on klines and
        never reads the catalog, so an empty answer is the honest one — and it
        is written out rather than inherited, because `IExchangeClient` is an
        ABC and a probe that skipped a method would fail to construct
        (`ONBOARDING` §8 trap 11, which is `BUG-026`)."""
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
        # EPIC-006F: no QML left in this app — apply_role() is the only
        # Any process that builds this app's widgets seeds its theme the
        # same way the bootstrapper does — one call, one place
        # (`theme_bootstrap.py`). BOT-132: this used to be a partial copy
        # here (bridge only, no `configure_app_qml()`), which the QML
        # embedding rework turned from silently-wrong into a hard failure.
        seed_app_theme()
        screen_registry = ScreenRegistry()
        # The shell's Welcome screen carries `is_default` since `EPIC-025`
        # PR 1.5a, and `MainWindow` refuses to open without a default — so a
        # probe that hand-lists the legacy screens has to include it, the same
        # way `tests/conftest.py`'s `real_screen_registry` does. Settings left
        # the legacy `AbstractScreenModule` mechanism in `EPIC-025E` PR 4.4e —
        # it is a `ScreenContribution` now, registered the same way Welcome is.
        screen_registry.register(as_screen_descriptor(welcome_screen()))
        screen_registry.register(as_screen_descriptor(settings_screen()))
        for module_cls in (
            DashboardScreenModule,
            DatabaseScreenModule,
            BacktestScreenModule,
        ):
            screen_registry.register_module(module_cls(), engine.context.container)
        window = MainWindow(engine, screen_registry, sidebar_factory=Sidebar)
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
