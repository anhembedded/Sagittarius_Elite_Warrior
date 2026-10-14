"""`EPIC-039E` — the Spot venue's settings gate: nothing to ensure.

Spot has no leverage and no margin mode, so a bot's parameters cannot disagree with it.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_settings_gate import (
    IVenueSettingsGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_settings_gate_result import (
    ENSURED,
    GateRequest,
    GateResult,
)


class SpotSettingsGate(IVenueSettingsGate):
    def ensure(self, request: GateRequest) -> GateResult:
        return ENSURED

    def verify(self, request: GateRequest) -> GateResult:
        return ENSURED
