"""`ArmedStrategyReaderAdapter` — implements trading's `IArmedStrategyReader`
by wrapping `strategy`'s own, unchanged `IArmedStrategy`.

@details `DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`
§8. Bound in `StrategyModule.register()` (`composition/port_bindings.py`);
`strategy.dependencies` already names `"trading"`, so this file importing
`modules.trading.contracts` costs nothing.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.live_strategy_config_translation import (
    to_armed_config,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_armed_strategy import (
    IArmedStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_snapshot import (
    ArmedStrategySnapshot as TradingArmedStrategySnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_armed_strategy_reader import (
    IArmedStrategyReader,
)


class ArmedStrategyReaderAdapter(IArmedStrategyReader):
    """Translates `strategy`'s `ArmedStrategySnapshot` into trading's own."""

    def __init__(self, armed_strategy: IArmedStrategy) -> None:
        self._armed_strategy = armed_strategy

    def armed(self) -> TradingArmedStrategySnapshot:
        snapshot = self._armed_strategy.armed()
        config = (
            to_armed_config(snapshot.config) if snapshot.config is not None else None
        )
        return TradingArmedStrategySnapshot(
            config=config, engine_running=snapshot.engine_running
        )
