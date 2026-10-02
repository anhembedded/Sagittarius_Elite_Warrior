"""`EPIC-028K` — implements trading's `IVenueStrategyControls` over this
module's per-venue arming and sessions.

@details Each venue's arming is `venue_strategy_arming` (commands addressed
to that venue, its own saved configuration) behind the same
`StrategyArmingControlAdapter` the primary venue uses; its armed state is
that venue's `LiveStrategySession` from `VenueStrategySessions`, behind the
same `ArmedStrategyReaderAdapter`. Built once per venue and kept, so a desk
reopened later holds the same instances.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.armed_strategy_reader_adapter import (
    ArmedStrategyReaderAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.strategy_arming_control_adapter import (
    StrategyArmingControlAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.venue_strategy_sessions import (
    VenueStrategySessions,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_arming import (
    IStrategyArming,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_strategy_controls import (
    IVenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_strategy_controls import (
    VenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class VenueStrategyControlsAdapter(IVenueStrategyControls):
    """One `VenueStrategyControls` per venue, built on first use."""

    def __init__(
        self,
        arming_for: Callable[[TradingVenue], IStrategyArming],
        sessions: VenueStrategySessions,
    ) -> None:
        self._arming_for = arming_for
        self._sessions = sessions
        self._controls: dict[TradingVenue, VenueStrategyControls] = {}
        self._lock = threading.Lock()

    def get(self, venue: TradingVenue) -> VenueStrategyControls:
        with self._lock:
            controls = self._controls.get(venue)
            if controls is None:
                # The session first: it refuses a venue that is not served
                # before any arming is built for it.
                armed = ArmedStrategyReaderAdapter(self._sessions.get(venue))
                controls = VenueStrategyControls(
                    venue=venue,
                    arming=StrategyArmingControlAdapter(self._arming_for(venue)),
                    armed=armed,
                )
                self._controls[venue] = controls
            return controls
