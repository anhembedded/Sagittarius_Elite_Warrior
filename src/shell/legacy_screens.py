"""Which screens the strangler period still carries (SDD boot step 6).

This tuple replaces the hard-coded list the GUI bootstrapper used to hold
(`app_bootstrapper.py`, five class names in a `for` loop). It is the same five
classes, but now the **shell** owns the fact that they exist — which is the
whole point of `EPIC-025`: an entry point that boots the app, and a shell that
knows what the app is made of.

Each entry leaves as its bounded context claims it: `dashboard` and `trading`
moved in `EPIC-025E` PR 4.4c, `data_management` in PR 4.4b, both later than
Phase 0/1 first planned — a screen's move waits on the support packages and
port work its own `ui/` needs, not on the phase number that first named it.
`backtest` and `settings` are Phase 4's own remaining moves. The tuple is
empty when the migration is done, and this file goes with
`legacy_screen_adapter.py`.

`shell/modules.py` is the equivalent list for real modules. Two lists, because
they are two different things — a class that wraps a legacy screen and a bounded
context — and merging them would hide which is which.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.market_data.ui.module import (
    DatabaseScreenModule,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.module import (
    DashboardScreenModule,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trading.module import (
    TradingScreenModule,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.module import (
    BacktestScreenModule,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.module import (
    SettingsScreenModule,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.registry import AbstractScreenModule

LEGACY_SCREEN_MODULES: tuple[type[AbstractScreenModule], ...] = (
    DashboardScreenModule,
    TradingScreenModule,
    DatabaseScreenModule,
    SettingsScreenModule,
    BacktestScreenModule,
)
