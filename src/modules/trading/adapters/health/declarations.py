"""The health probes `trading` owns, as the declaration `TradingModule` hands over (`EPIC-038D`).

`trading` knows the key and the clock the exchange keeps, so it owns the probe that
measures the skew; `operations` runs it. A second probe is one class and one entry.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_health_probe import IHealthProbe
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    HealthProbeDescriptor,
    PortResolver,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.health.clock_skew_probe import (
    PROBE_NAME,
    ClockSkewProbe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.venue_reads import (
    VenueReads,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.health.clock_skew_recorder import (
    ClockSkewRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_key_environment_probe import (
    IKeyEnvironmentProbe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)


def trading_health_probes(
    contributor_id: str, skews: ClockSkewRecorder
) -> tuple[HealthProbeDescriptor, ...]:
    def make(resolver: PortResolver) -> IHealthProbe:
        # mypy cannot pass an abstract port to `type[T]`; the container resolves it.
        contexts = resolver.resolve(IVenueContexts)  # type: ignore[type-abstract]
        probe = resolver.resolve(IKeyEnvironmentProbe)  # type: ignore[type-abstract]
        return ClockSkewProbe(VenueReads(contexts, probe), skews)

    return (HealthProbeDescriptor(PROBE_NAME, make, contributor_id),)
