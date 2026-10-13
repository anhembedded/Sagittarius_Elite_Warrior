"""Trading's part of the health snapshot, as one object the module holds (`EPIC-038C`).

The recorder that listens to the user-data streams, the declaration that offers
their section to the registry, and the subscription that feeds the recorder.
`TradingModule` holds one of these and names none of its three parts.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    HealthContributorDescriptor,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.health.clock_skew_recorder import (
    ClockSkewRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.health.trading_health_contributor import (
    SECTION_NAME,
    TradingHealthContributor,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.health.user_stream_recorder import (
    UserStreamRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
)


class TradingHealth:
    def __init__(self) -> None:
        self._streams = UserStreamRecorder()
        self._skews = ClockSkewRecorder()

    @property
    def skews(self) -> ClockSkewRecorder:
        """Where the host's clock-skew probe leaves what it measured."""
        return self._skews

    def declaration(self, contributor_id: str) -> HealthContributorDescriptor:
        return HealthContributorDescriptor(
            SECTION_NAME,
            lambda _resolver: TradingHealthContributor(
                self._streams, skews=self._skews
            ),
            contributor_id,
        )

    def subscriptions(
        self,
    ) -> tuple[tuple[type, Callable[[UserStreamHealthEvent], None]], ...]:
        """`(event type, handler)` pairs for the module to attach to the bus: the
        module attaches them, so this application code names no Engine type."""
        return ((UserStreamHealthEvent, self._streams.on_health),)
