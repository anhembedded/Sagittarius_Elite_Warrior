"""Which screens the strangler period still carries (SDD boot step 6).

This tuple replaces the hard-coded list the GUI bootstrapper used to hold
(`app_bootstrapper.py`, five class names in a `for` loop). It started as
those same five classes, and now the **shell** owns the fact that they
exist — which is the whole point of `EPIC-025`: an entry point that boots
the app, and a shell that knows what the app is made of.

`dashboard`/`trading` moved (unchanged mechanism, new address) in `EPIC-025E`
PR 4.4c, `data_management` in PR 4.4b, `backtest` in PR 4.4d — a screen's
*file* move waits on the support packages and port work its own `ui/`
needs, not on the phase number that first named it, and none of the three
retires a line here: `AbstractScreenModule` is still every one's real
registration mechanism, and stays so until Phase 5's `NavigationService`
replaces it for all four at once.

`settings` is the one entry that retires **early**, in PR 4.4e, because its
whole move was a mechanism change rather than a file move: it left
`AbstractScreenModule` entirely for a `ScreenContribution`
(`shell/settings/settings_screen.py`), the same shape `welcome_screen()`
already uses — so this tuple drops to four, not because settings is gone,
but because it no longer speaks this file's dialect.

`shell/modules.py` is the equivalent list for real modules. Two lists, because
they are two different things — a class that wraps a legacy screen and a bounded
context — and merging them would hide which is which.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.module import (
    BacktestScreenModule,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.module import (
    DatabaseScreenModule,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.module import (
    DashboardScreenModule,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trading.module import (
    TradingScreenModule,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.registry import AbstractScreenModule

LEGACY_SCREEN_MODULES: tuple[type[AbstractScreenModule], ...] = (
    DashboardScreenModule,
    TradingScreenModule,
    DatabaseScreenModule,
    BacktestScreenModule,
)
