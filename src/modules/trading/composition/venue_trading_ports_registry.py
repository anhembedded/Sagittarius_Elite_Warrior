"""`EPIC-028B` — `IVenueTradingPorts`, one bundle of venue-bound services
per served venue."""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account.account_activity_service import (
    AccountActivityService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account.account_snapshot_service import (
    AccountSnapshotService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.futures_settings_service import (
    FuturesSettingsService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.order_entry_terms_service import (
    OrderEntryTermsService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.order_submission_service import (
    OrderSubmissionService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.trading_session_service import (
    TradingSessionService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_session_states import (
    VenueSessionStates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_trading_ports import (
    VenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class VenueTradingPortsRegistry(IVenueTradingPorts):
    """@details The services themselves are stateless façades over the
    dispatcher; the only state they reach is the venue's own, owned by
    `VenueSessionStates`. Which venues exist, and which venue is primary, is
    `IVenueContexts`'s answer — this registry never keeps a second copy."""

    def __init__(
        self,
        dispatcher: ICommandDispatcher,
        contexts: IVenueContexts,
        states: VenueSessionStates,
    ) -> None:
        self._dispatcher = dispatcher
        self._contexts = contexts
        self._states = states
        self._ports: dict[TradingVenue, VenueTradingPorts] = {}
        self._lock = threading.Lock()

    def enabled(self) -> tuple[TradingVenue, ...]:
        return self._contexts.enabled()

    def get(self, venue: TradingVenue) -> VenueTradingPorts:
        # Validates first: a venue `IVenueContexts` does not serve gets no
        # ports, and no state is created for it.
        self._contexts.get(venue)
        with self._lock:
            ports = self._ports.get(venue)
            if ports is None:
                ports = self._build(venue)
                self._ports[venue] = ports
            return ports

    def primary(self) -> VenueTradingPorts:
        return self.get(self._contexts.primary().venue)

    def _build(self, venue: TradingVenue) -> VenueTradingPorts:
        return VenueTradingPorts(
            venue=venue,
            order_submission=OrderSubmissionService(self._dispatcher, venue),
            trading_session=TradingSessionService(
                self._dispatcher, self._states.session_state(venue), venue
            ),
            account_snapshot=AccountSnapshotService(self._dispatcher, venue),
            equity_curve=self._states.equity_recorder(venue),
            order_entry_terms=OrderEntryTermsService(self._dispatcher, venue),
            account_activity=AccountActivityService(self._dispatcher, venue),
            futures_settings=FuturesSettingsService(self._dispatcher, venue),
        )
