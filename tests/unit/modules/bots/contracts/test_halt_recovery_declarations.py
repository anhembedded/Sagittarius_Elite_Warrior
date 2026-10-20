"""`EPIC-042B` — where the halt-recovery layers are declared, and that opening a kind costs nothing.

A kind that declares nothing recovers nothing of its own (`IBotKind.recovery_layer` is concrete and
empty, so no implementer changed); the Grid declares `rate_limited`, the exchange's pause
(`EPIC-042F`); Spot's venue layer is empty and Futures' clears the lower layers and lists the pause.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    IBotExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    NO_VENUE_RECOVERY,
    SPOT_PROFILE,
    VenueProfile,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_KIND_ID,
    GRID_RECOVERY_LAYER,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    RATE_LIMITED,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class _KindThatDeclaresNothing(IBotKind):
    """The ABC's own abstract members and nothing else: what a new kind starts from."""

    @property
    def kind_id(self) -> str:
        return "nothing"

    def supported_profiles(self) -> frozenset[MarketType]:
        return frozenset()

    def validate(self, inputs: BotKindInputs) -> tuple[Verdict, ...]:
        return ()

    def overlay(self, inputs: BotKindInputs) -> BotOverlay:
        raise NotImplementedError

    def executor_factory(self) -> IBotExecutorFactory:
        raise NotImplementedError


def test_a_kind_that_declares_nothing_has_an_empty_layer_named_after_it() -> None:
    layer = _KindThatDeclaresNothing().recovery_layer()
    assert layer.name == "nothing"
    assert not layer.changes
    assert not layer.withdrawn
    assert not layer.clears_lower_layers


def test_the_grid_declares_its_own_layer_and_it_holds_the_exchanges_pause_only() -> (
    None
):
    assert GRID_RECOVERY_LAYER.name == GRID_KIND_ID
    assert set(GRID_RECOVERY_LAYER.changes) == {RATE_LIMITED}
    assert not GRID_RECOVERY_LAYER.withdrawn


def test_spots_venue_layer_clears_nothing() -> None:
    assert not SPOT_PROFILE.recovery_layer.clears_lower_layers


def test_every_futures_venue_clears_the_lower_layers() -> None:
    for venue in (TradingVenue.FUTURES_MAINNET, TradingVenue.FUTURES_TESTNET):
        profile = venue_profile_of(venue)
        assert profile is not None
        assert profile.recovery_layer.clears_lower_layers
        assert set(profile.recovery_layer.changes) == {RATE_LIMITED}, "the pause only"


def test_a_profile_built_without_a_layer_says_nothing() -> None:
    """The field has a default, so no construction site of `VenueProfile` had to change."""
    rebuilt = VenueProfile(
        market_type=SPOT_PROFILE.market_type,
        directions=SPOT_PROFILE.directions,
        margin_modes=SPOT_PROFILE.margin_modes,
        has_funding=False,
        exposure_kind=SPOT_PROFILE.exposure_kind,
        needs_reduce_only_exits=False,
        title_word="Spot",
    )
    assert rebuilt.recovery_layer is NO_VENUE_RECOVERY
