"""`EPIC-040B` — the kind catalog the module registers hands out the Grid's backtest by kind id.

@details The wiring is the proof: `GridKind` is constructed by `BotsModule.register`, so a test that
builds its own `GridKind` proves nothing about whether the real one is given a backtester."""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_kind_backtester import (
    GridKindBacktester,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_KIND_ID,
)

from .bots_module_world import registered


def test_the_registered_grid_kind_has_the_grid_backtester(tmp_path: Path) -> None:
    _module, context = registered(tmp_path / "bots")

    catalog = context.container.resolve(IBotKindCatalog)

    assert isinstance(catalog.kind(GRID_KIND_ID).backtester(), GridKindBacktester)
