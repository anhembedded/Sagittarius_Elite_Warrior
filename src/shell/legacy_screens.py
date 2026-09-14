"""Which screens the strangler period still carries (SDD boot step 6).

This tuple replaces the hard-coded list the GUI bootstrapper used to hold
(`app_bootstrapper.py`, five class names in a `for` loop). It is the same five
classes, but now the **shell** owns the fact that they exist — which is the
whole point of `EPIC-025`: an entry point that boots the app, and a shell that
knows what the app is made of.

Each entry leaves as its bounded context claims it: `dashboard` and `trading` in
Phase 1, `data_management` in Phase 0's own PR 0.4, `backtest` in Phase 3,
`settings` in Phase 4. The tuple is empty when the migration is done, and this
file goes with `legacy_screen_adapter.py`.

`shell/modules.py` is the equivalent list for real modules. Two lists, because
they are two different things — a class that wraps a legacy screen and a bounded
context — and merging them would hide which is which.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.registry import AbstractScreenModule
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.module import (
    BacktestScreenModule,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.module import (
    DashboardScreenModule,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.module import (
    DatabaseScreenModule,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.module import (
    SettingsScreenModule,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.module import (
    TradingScreenModule,
)

LEGACY_SCREEN_MODULES: tuple[type[AbstractScreenModule], ...] = (
    DashboardScreenModule,
    TradingScreenModule,
    DatabaseScreenModule,
    SettingsScreenModule,
    BacktestScreenModule,
)
