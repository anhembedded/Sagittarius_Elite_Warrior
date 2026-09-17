"""`StrategyArmingService` — `IStrategyArming`'s implementation.

@details Dispatches `ArmStrategyCommand`/`DisarmStrategyCommand` exactly as
`StrategyArmingCoordinator` used to — same module now, so nothing about
`ICommandDispatcher`'s handler-class-as-lookup-key shape changes. Only the
caller moved: a screen calls this port instead of holding the command and
handler classes itself.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_config_store import (
    LiveStrategyConfigStore,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.arm_strategy import (
    ArmStrategyCommand,
    ArmStrategyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.disarm_strategy import (
    DisarmStrategyCommand,
    DisarmStrategyCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.arm_strategy_result import (
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.disarm_strategy_result import (
    DisarmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_arming import (
    IStrategyArming,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)


class StrategyArmingService(IStrategyArming):
    def __init__(
        self, dispatcher: ICommandDispatcher, config_store: LiveStrategyConfigStore
    ) -> None:
        self._dispatcher = dispatcher
        self._config_store = config_store

    def arm(self, config: LiveStrategyConfig) -> ArmStrategyResult:
        result = self._dispatcher.dispatch(
            ArmStrategyCommandHandler, ArmStrategyCommand(config)
        )
        if not isinstance(result, ArmStrategyResult):
            raise TypeError(
                "ArmStrategyCommand was not answered with ArmStrategyResult but "
                f"with {type(result).__name__} — no handler is bound for it"
            )
        return result

    def disarm(self) -> DisarmStrategyResult:
        result = self._dispatcher.dispatch(
            DisarmStrategyCommandHandler, DisarmStrategyCommand()
        )
        if not isinstance(result, DisarmStrategyResult):
            raise TypeError(
                "DisarmStrategyCommand was not answered with DisarmStrategyResult "
                f"but with {type(result).__name__} — no handler is bound for it"
            )
        return result

    def saved_selection(self) -> LiveStrategyConfig:
        try:
            return self._config_store.load()
        except ValueError:
            # A saved config the domain rejects (leverage 0, an unsupported
            # interval) restores as "nothing selected" rather than raising
            # across the port — the same recovery
            # `StrategyArmingCoordinator.restore_into_view_model()` chose.
            return LiveStrategyConfig(strategy_key="", symbol="", interval="")
