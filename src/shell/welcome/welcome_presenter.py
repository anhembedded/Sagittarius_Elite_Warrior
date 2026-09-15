"""The Welcome screen's Presenter: read configuration, raise one intent.

Deliberately the smallest Presenter in the app. It answers two questions the
view must not answer for itself — *what is this application* and *which venue
does this run talk to* — and it turns **Start** into an intent on the bus
(`start_requested_event.py` says why an intent and not a navigation call).

No Coordinator, no action identity, no background work: nothing here can take
longer than reading three configuration keys, so the machinery
`async-ui-action-rule.md` requires for a background action would be machinery
with nothing to own.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
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
        self._connect_ui_signals()

    def _connect_ui_signals(self) -> None:
        self.view.start_requested.connect(self._on_start_requested)

    def _on_start_requested(self) -> None:
        """Publishes the intent. *Main* decides where Start goes."""
        self.logger.info("[WELCOME] Start requested.")
        self.event_bus.publish(StartRequested())

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
