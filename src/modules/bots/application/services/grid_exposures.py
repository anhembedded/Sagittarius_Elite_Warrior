"""`EPIC-039H` — the exposure-shaped collaborators of one Grid executor, chosen by the venue's profile.

@details A Grid's executor is exposure-agnostic except at four joints: how the start takes its
opening, how the stop closes what the bot holds, what a reconcile checks of the holding, and
what flags the ladder's orders carry. Each is a port (`IOpeningStrategy`, `IExposureCloser`,
`IExposureCheck`, `IOrderFlags`); `GridExposure` is the four of one bot, plus the risk watch
a position venue adds (`None` where the exposure has none), and `GridExposures`
builds them from the profile of the bot's venue, exactly as `VenueSettingsGates` picks a
settings gate. No sequence names a market and a third kind of exposure is one more entry.

Plausible extensions, each a local change: a venue profile with another exposure kind (Coin-M,
a margin account) is one more builder in the mapping; a decorator that adds the protective stop
(`EPIC-039L`) wraps the position builder's closer.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.closer_spot import (
    SpotExposureCloser,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.exposure_check_spot import (
    SpotExposureCheck,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_risk_watch import (
    GridRiskWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.opening_spot import (
    SpotOpening,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.order_flags_spot import (
    SpotOrderFlags,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue_profiles_by_market import (
    VenueProfilesByMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_check import (
    IExposureCheck,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_closer import (
    IExposureCloser,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_mark_source import (
    IMarkSource,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_opening_strategy import (
    IOpeningStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_flags import (
    IOrderFlags,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_profiles import (
    IVenueProfiles,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
)


@dataclass(frozen=True, slots=True)
class GridExposure:
    """The exposure-shaped collaborators of one bot's executor."""

    opening: IOpeningStrategy
    closer: IExposureCloser
    check: IExposureCheck
    flags: IOrderFlags
    #: A position venue's liquidation and divergence watch (`EPIC-039F`); `None`: Spot has neither.
    risk_watch: GridRiskWatch | None = None
    #: Where a position venue's stop loss and take profit are judged: the mark price. `None`:
    #: the streamed last price and its range are (Spot).
    exit_marks: IMarkSource | None = None


class ExposureKindNotBuiltError(LookupError):
    """The bot's venue has an exposure kind this build has no collaborators for."""

    def __init__(self, kind: ExposureKind) -> None:
        super().__init__(
            f"This build has no collaborators for a {kind.name} exposure, "
            "so a bot on that venue cannot run."
        )


type ExposureBuilder = Callable[[GridRunContext], GridExposure]


def spot_exposure(context: GridRunContext) -> GridExposure:
    return GridExposure(
        SpotOpening(context),
        SpotExposureCloser(context),
        SpotExposureCheck(context),
        SpotOrderFlags(),
    )


class GridExposures:
    """Builds a bot's `GridExposure` from the exposure kind of its venue's profile."""

    def __init__(
        self,
        profiles: IVenueProfiles,
        by_exposure: Mapping[ExposureKind, ExposureBuilder],
    ) -> None:
        self._profiles = profiles
        self._by_exposure = by_exposure

    def build(self, context: GridRunContext) -> GridExposure:
        """@raise VenueTradesNoMarketError The bot's venue trades no market.
        @raise ExposureKindNotBuiltError The venue's exposure kind has no builder in this build."""
        profile = self._profiles.for_venue(context.state.bot.definition.venue)
        build = self._by_exposure.get(profile.exposure_kind)
        if build is None:
            raise ExposureKindNotBuiltError(profile.exposure_kind)
        return build(context)


def spot_only_exposures() -> GridExposures:
    """The table of a build (or a test) that runs Grids on Spot only."""
    return GridExposures(
        VenueProfilesByMarket(), {ExposureKind.INVENTORY: spot_exposure}
    )
