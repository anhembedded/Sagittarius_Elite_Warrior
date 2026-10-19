"""The factories behind this context's `DEV_PROBE` contributions, named by import path.

**Nothing Qt is imported here at module level, and that is the point.** `module.py` imports
this file so it can name a factory in a descriptor, and `contribute()` runs at boot for every
run, including a headless `sync` that never opens a window. Each factory is therefore a
`Deferred` (`core/contracts/deferred.py`), imported only when a surface actually renders the
probe (`test_module_contribution_laziness.py` is the guard, HLD §6.1's declaration rule (e) the
rule, and `test_deferred_targets_resolve.py` checks every target exists, `BOT-148`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.deferred import Deferred

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

#: The `DEV_PROBE` panel showing the live trading session's own state.
TRADING_SESSION_PROBE: Deferred[QWidget] = Deferred(
    "Sagittarius_Elite_Warrior.src.modules.trading.ui.session_probe"
    ":build_trading_session_probe"
)
