"""Which contribution table, if any, a run has (`EPIC-033P`).

Qt-free on purpose: it was written for the Dev Board's screen module, which
`contribute()` imported on a headless run
(`test_module_contribution_laziness.py`), where `surface_building.py`'s Qt
import would cost a widget module nobody opened. The Developer mode's
presenter is its one reader since `EPIC-033P` deleted the Dev Board.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_contribution_table import (
    IContributionTable,
)
from sagittarius_engine.exceptions import DependencyResolutionError
from sagittarius_engine.interfaces.i_container import IContainer


def contribution_table(container: IContainer) -> IContributionTable | None:
    """The run's contribution table, or `None` when it has none.

    Both `None` cases are real runs, not defensive padding (moved here from
    the Dev Board's screen in `EPIC-033P`):

    - **Nothing bound it.** `assemble_contributions()` binds the port in the
      GUI entry point only; a container built without it raises
      `DependencyResolutionError`, which is the answer "this run has no
      surfaces", not a failure.
    - **A `Mock()` container.** The smoke tests that build every navigable
      route pass one, and a `Mock` reaching a factory would build a `Mock`
      widget and place it on the screen. The `isinstance` check is what
      tells a real table from that.
    """
    try:
        table = container.resolve(IContributionTable)
    except DependencyResolutionError:
        return None
    return table if isinstance(table, IContributionTable) else None
