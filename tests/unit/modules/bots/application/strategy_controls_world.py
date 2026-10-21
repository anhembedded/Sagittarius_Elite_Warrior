"""`EPIC-045G` - a venue's strategy controls as in-memory implementations of their ports (each subclasses the
port it stands for), for the host's arm and disarm handlers."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    ArmedStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_snapshot import (
    ArmedStrategySnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_armed_strategy_reader import (
    IArmedStrategyReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_arming_control import (
    IStrategyArmingControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_strategy_controls import (
    IVenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_arm_result import (
    ArmStrategyBlockReason,
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_disarm_result import (
    DisarmStrategyBlockReason,
    DisarmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_strategy_controls import (
    VenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

SAVED = ArmedStrategyConfig(
    "ema_crossover", "BTCUSDT", "5m", {"fast": 9, "slow": 21}, 10.0, 1.0
)


class MemoryArming(IStrategyArmingControl):
    """Holds what is armed and what was saved; arms or refuses as scripted, and remembers what it was given."""

    def __init__(self, saved: ArmedStrategyConfig | None = SAVED) -> None:
        self.saved = saved or ArmedStrategyConfig("", "", "")
        self.armed: ArmedStrategyConfig | None = None
        self.arm_refusal: ArmStrategyResult | None = None
        self.position_open = False
        self.arm_calls: list[ArmedStrategyConfig] = []
        self.disarm_calls = 0

    def arm(self, config: ArmedStrategyConfig) -> ArmStrategyResult:
        self.arm_calls.append(config)
        if self.arm_refusal is not None:
            return self.arm_refusal
        self.armed = config
        return ArmStrategyResult(armed=True)

    def disarm(self) -> DisarmStrategyResult:
        self.disarm_calls += 1
        if self.position_open:
            return DisarmStrategyResult(
                disarmed=False, block_reason=DisarmStrategyBlockReason.POSITION_OPEN
            )
        self.armed = None
        return DisarmStrategyResult(disarmed=True)

    def saved_selection(self) -> ArmedStrategyConfig:
        return self.saved


class MemoryArmed(IArmedStrategyReader):
    def __init__(self, arming: MemoryArming) -> None:
        self._arming = arming

    def armed(self) -> ArmedStrategySnapshot:
        return ArmedStrategySnapshot(self._arming.armed, self._arming.armed is not None)


class MemoryControls(IVenueStrategyControls):
    """Serves the venues it was given; any other is refused as the real one refuses it."""

    def __init__(self, *venues: TradingVenue) -> None:
        self.arming = {venue: MemoryArming() for venue in venues}

    def get(self, venue: TradingVenue) -> VenueStrategyControls:
        if venue not in self.arming:
            raise VenueNotEnabledError(venue, tuple(self.arming))
        arming = self.arming[venue]
        return VenueStrategyControls(venue, arming, MemoryArmed(arming))


def refused(
    reason: ArmStrategyBlockReason, text: str | None = None
) -> ArmStrategyResult:
    return ArmStrategyResult(armed=False, block_reason=reason, error_message=text)
