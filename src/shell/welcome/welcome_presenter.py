"""The Welcome screen's Presenter: configuration in, one intent out.

It answers two questions the view must not answer for itself — *what is this
application* and *which venue does this run talk to* — turns **Start** into an
intent on the bus (`start_requested_event.py` says why an intent and not a
navigation call), and owns the developer-mode switch: the write, and the
restart that is the only thing which applies it (ADR D14).

No Coordinator, no action identity, no background work: nothing here takes
longer than reading a few configuration keys or writing one, so the machinery
`async-ui-action-rule.md` requires for a background action would be machinery
with nothing to own. The restart is the exception that proves it — it does not
*wait* for anything, it replaces the process.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_writer import IConfigWriter
from Sagittarius_Elite_Warrior.src.shell.welcome.restart import restart_now
from Sagittarius_Elite_Warrior.src.shell.welcome.start_requested_event import (
    StartRequested,
)
from Sagittarius_Elite_Warrior.src.shell.welcome.welcome_view import WelcomeView
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    resolve_market_data_venue,
    resolve_trading_venue,
)
from sagittarius_engine.extensions.pyside_mvc import BasePresenter
from sagittarius_engine.interfaces.i_container import IContainer

_UNNAMED = "Sagittarius"
_UNKNOWN_VERSION = "unknown"


def _start_detached(arguments: Sequence[str]) -> bool:
    """Qt's own launcher, with its answer narrowed to "did it start".

    `QProcess.startDetached` answers `(started, pid)` in PySide6 — the type
    gate caught a lambda handing that tuple straight back as a `bool`, which
    Python would have treated as truthy forever and so would have reported
    every failed start as a success.
    """
    started, _pid = QProcess.startDetached(arguments[0], list(arguments[1:]))
    return bool(started)


class WelcomePresenter(BasePresenter):
    """@brief Fills the Welcome screen and publishes what the user asks for."""

    def __init__(self, view: WelcomeView, container: IContainer) -> None:
        super().__init__(view, container)
        self.view: WelcomeView = view

        self.view.show_application(
            str(self.config.get(ConfigKeys.APP_NAME.value, _UNNAMED)),
            str(self.config.get(ConfigKeys.APP_VERSION.value, _UNKNOWN_VERSION)),
        )
        self.view.show_venue(self._venue_description())
        self.view.show_developer_mode(enabled=self._developer_mode_now())
        self._connect_ui_signals()

    def _connect_ui_signals(self) -> None:
        self.view.start_requested.connect(self._on_start_requested)
        self.view.dev_mode_toggled.connect(self._on_dev_mode_toggled)
        self.view.restart_requested.connect(self._on_restart_requested)

    def _on_start_requested(self) -> None:
        """Publishes the intent. *Main* decides where Start goes."""
        self.logger.info("[WELCOME] Start requested.")
        self.event_bus.publish(StartRequested())

    def _developer_mode_now(self) -> bool:
        return bool(self.config.get(ConfigKeys.DEV_MODE.value, False))

    def _on_dev_mode_toggled(self, enabled: bool) -> None:
        """Writes the switch through `IConfigWriter`, then says what it takes.

        The write happens first and the notice second: the notice is a fact
        about the file on disk, and a failed write with a cheerful "restart to
        apply" beside it would be a lie the user acts on. A failure is logged
        and left visible in the switch's own position — nothing here pretends
        it succeeded.
        """
        try:
            writer = self.container.resolve(IConfigWriter)
            writer.set(ConfigKeys.DEV_MODE.value, enabled)
            writer.save()
        except (OSError, ValueError):
            self.logger.exception(
                "[WELCOME] Could not save developer mode = %s. The setting is "
                "unchanged on disk.",
                enabled,
            )
            self.view.show_developer_mode(enabled=self._developer_mode_now())
            return
        self.logger.info("[WELCOME] Developer mode written as %s.", enabled)
        self.view.show_restart_is_needed()

    def _on_restart_requested(self) -> None:
        """Starts a fresh process and quits this one.

        Qt's own two calls, injected into `restart_now()` so the decision —
        which arguments the next process gets — is testable without spawning
        anything. `sys.executable` plus this process's own `sys.argv`, because
        the app may have been started as a script or as `python -m`, and the
        next one has to start the way this one did.
        """
        restart_now(
            [sys.executable, *sys.argv],
            dev_mode_enabled=self._developer_mode_now(),
            start_detached=_start_detached,
            quit_application=QApplication.quit,
        )

    def _venue_description(self) -> str:
        """Which venue this run reads prices from, and which it could send an
        order to — two independent settings (ADR §2), so both are named.

        A user who does not know whether they are on Testnet is a user one
        click away from a real order, which is why this is on the first screen
        rather than buried in Settings.
        """
        market = resolve_market_data_venue(self.config)
        trading = resolve_trading_venue(self.config)
        return f"market data: {market.value} · trading: {trading.value}"
