"""The factories behind this context's `DEV_PROBE` contributions.

**Nothing Qt is imported here at module level, and that is the point.**
`module.py` imports this file so it can name a factory in a descriptor, and
`contribute()` runs at boot for every run — including a headless `sync` that
never opens a window. The widget import therefore happens inside the factory,
where it runs only when a surface actually renders the probe
(`test_module_contribution_laziness.py` is the guard, and HLD §6.1's
declaration rule (e) is the rule).

It is the same shape `presentation/ui/screens/*/module.py` already uses for
`create_view()`, which is why `code/quality.md` §2's ban on function-local
imports does not bite here: the lazy import *is* the mechanism, not a shortcut
around a cycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sagittarius_engine.interfaces.i_container import IContainer

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


def build_trading_session_probe(container: IContainer) -> QWidget:
    """The `DEV_PROBE` panel showing the live trading session's own state."""
    from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
        ITradingSession,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.session_probe import (
        TradingSessionProbe,
    )

    return TradingSessionProbe(container.resolve(ITradingSession))
