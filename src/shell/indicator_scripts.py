"""The chart indicator scripts the application ships, registered by id (`PRO-014`).

Moved out of `composition_root.py`, which registered them at every boot: nine script classes
(and the indicator maths behind them) were imported by `bot list` to fill a registry only a
chart reads. `create_app` binds the registry to `build_indicator_script_registry` by `Deferred`,
so the scripts load when a chart first asks for the registry.

Extension case: a new script - one `register` line here and its class beside the others.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.dev_indicator_script import (
    DevIndicatorScript,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_20_script import (
    Ema20Script,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_50_script import (
    Ema50Script,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_100_script import (
    Ema100Script,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_200_script import (
    Ema200Script,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_cross_script import (
    EmaCrossScript,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_ribbon_script import (
    EmaRibbonScript,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.macd_full_script import (
    MacdFullScript,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.rsi_14_script import (
    Rsi14Script,
)


def build_indicator_script_registry() -> IndicatorScriptRegistry:
    """The registry with every shipped script in it."""
    script_registry = IndicatorScriptRegistry()
    script_registry.register("rsi_14", Rsi14Script)
    script_registry.register("ema_20", Ema20Script)
    script_registry.register("ema_50", Ema50Script)
    script_registry.register("ema_100", Ema100Script)
    script_registry.register("ema_200", Ema200Script)
    script_registry.register("macd_full", MacdFullScript)
    script_registry.register("ema_ribbon", EmaRibbonScript)
    script_registry.register("ema_cross", EmaCrossScript)
    script_registry.register("dev_showcase", DevIndicatorScript)
    return script_registry
