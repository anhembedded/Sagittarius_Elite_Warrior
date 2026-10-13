"""`EPIC-039E` — the settings gate of a bot's venue, chosen by the venue's profile.

The bots module holds one `IVenueSettingsGate`; this is it. It asks the profile
(`IVenueProfiles`) what the venue exposes and hands the request to that kind's gate, so a
caller never names a market and a third kind is one more entry in the mapping.
"""

from __future__ import annotations

from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_profiles import (
    IVenueProfiles,
    VenueTradesNoMarketError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_settings_gate import (
    IVenueSettingsGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_settings_gate_result import (
    GateOutcome,
    GateRequest,
    GateResult,
)


class VenueSettingsGates(IVenueSettingsGate):
    def __init__(
        self,
        profiles: IVenueProfiles,
        by_exposure: Mapping[ExposureKind, IVenueSettingsGate],
    ) -> None:
        self._profiles = profiles
        self._by_exposure = by_exposure

    def ensure(self, request: GateRequest) -> GateResult:
        gate = self._gate_for(request)
        return gate.ensure(request) if isinstance(gate, IVenueSettingsGate) else gate

    def verify(self, request: GateRequest) -> GateResult:
        gate = self._gate_for(request)
        return gate.verify(request) if isinstance(gate, IVenueSettingsGate) else gate

    def _gate_for(self, request: GateRequest) -> IVenueSettingsGate | GateResult:
        try:
            profile = self._profiles.for_venue(request.venue)
        except VenueTradesNoMarketError:
            return GateResult(
                GateOutcome.SETTINGS_UNREADABLE,
                f"{request.venue.display_name} trades no market",
            )
        return self._by_exposure[profile.exposure_kind]
