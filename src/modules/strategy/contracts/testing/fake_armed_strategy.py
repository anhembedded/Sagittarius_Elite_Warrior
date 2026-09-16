"""`FakeArmedStrategy` — `IArmedStrategy`'s verified fake.

A test says what is armed; nothing here builds an engine, takes a lock or
touches the bus. `arm()`/`disarm()` are absent on purpose, exactly as they are
absent from the port: a consumer's test that could arm through this fake would
be exercising a path production does not have, because arming really goes
through `ArmStrategyCommand` and its validation.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.armed_strategy_snapshot import (
    ArmedStrategySnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_armed_strategy import (
    IArmedStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)


class FakeArmedStrategy(IArmedStrategy):
    """The armed state a test says the live session is in."""

    def __init__(
        self,
        config: LiveStrategyConfig | None = None,
        *,
        engine_running: bool | None = None,
    ) -> None:
        #: `None` means "follow the config", which is the ordinary case and
        #: keeps a consumer's test from having to state both. Pass it
        #: explicitly to build the state the real session can be in between
        #: recording a config and finishing the engine — the reason
        #: `ArmedStrategySnapshot` carries two fields at all.
        self._config = config
        self._engine_running = (
            config is not None if engine_running is None else engine_running
        )
        #: How many times the snapshot was read, for the same reason
        #: `FakeStrategyCatalog` counts reads.
        self.reads = 0

    def seed(
        self,
        config: LiveStrategyConfig | None,
        *,
        engine_running: bool | None = None,
    ) -> None:
        self._config = config
        self._engine_running = (
            config is not None if engine_running is None else engine_running
        )

    def armed(self) -> ArmedStrategySnapshot:
        self.reads += 1
        return ArmedStrategySnapshot(
            config=self._config, engine_running=self._engine_running
        )
