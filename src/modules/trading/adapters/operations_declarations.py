"""What `trading` declares for running unattended, in one call (`EPIC-038F`, `EPIC-038D`).

The pre-flight checks about the key and the exchange's clock, the user-stream section of the
health snapshot, and the probe that measures the clock for the host's health line: this
context knows each, `operations` runs them. A further declaration is one line here.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    IOperationsRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.health.declarations import (
    trading_health_probes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.declarations import (
    trading_preflight_checks,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.health.trading_health import (
    TradingHealth,
)


def declare_trading_operations(
    registry: IOperationsRegistry, contributor_id: str, health: TradingHealth
) -> None:
    for descriptor in trading_preflight_checks(contributor_id):
        registry.declare_preflight(descriptor)
    registry.declare_health(health.declaration(contributor_id))
    for probe in trading_health_probes(contributor_id, health.skews):
        registry.declare_probe(probe)
