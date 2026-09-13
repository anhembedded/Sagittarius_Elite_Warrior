"""The surfaces this application has, and what each one can hold (SDD).

A **surface** is a place a user navigates to. It is owned either by the shell
(`welcome`, `trading`, `dev_board`, `settings` — the workbench itself) or by the
module whose subject it is (`backtest`, `data_management`). Owning a surface
means declaring it here; it does not mean the owner fills it — any module may
contribute to any surface, which is the whole point of the mechanism.

`accepts` is a contract, checked at `contribute()` time: a module that offers a
`CONSOLE` panel to `settings` has misunderstood what Settings is, and hears so
immediately rather than by finding its panel missing at runtime.

`gated_by` names a run-time condition. A gated surface is **declared even when
it is off**, so contributions to it are *dropped with a log line* instead of
raising — the normal user run drops every Dev Board panel and boots (validation
rule 3). Declaring it conditionally would turn that normal case into a crash.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.place import Place

#: The only gate Phase 0 has. Read once at boot (`shell/dev_mode.py`).
DEV_MODE_GATE = "dev.mode"

_WORKBENCH_PLACES = frozenset(
    {
        Place.HEADER,
        Place.CONTEXT_BAR,
        Place.WORKSPACE,
        Place.RAIL,
        Place.CONSOLE,
        Place.MODAL,
        Place.STATUS_TILE,
    }
)


@dataclass(frozen=True, slots=True)
class Surface:
    surface_id: str
    #: `"shell"` or a `module_id` — who declares it, not who fills it.
    owner: str
    accepts: frozenset[Place]
    #: A config key that must be true for this surface to exist in a run.
    gated_by: str | None = None

    def is_open_in(self, *, dev_mode: bool) -> bool:
        if self.gated_by is None:
            return True
        if self.gated_by == DEV_MODE_GATE:
            return dev_mode
        raise ValueError(
            f"surface {self.surface_id!r} has an unknown gate {self.gated_by!r}"
        )


SURFACES: tuple[Surface, ...] = (
    Surface(
        "welcome", owner="shell", accepts=frozenset({Place.HEADER, Place.WORKSPACE})
    ),
    Surface("trading", owner="shell", accepts=_WORKBENCH_PLACES),
    Surface(
        "dev_board",
        owner="shell",
        accepts=_WORKBENCH_PLACES | {Place.DEV_PROBE},
        gated_by=DEV_MODE_GATE,
    ),
    Surface("settings", owner="shell", accepts=frozenset({Place.SETTINGS_SECTION})),
    Surface(
        "backtest", owner="backtesting", accepts=frozenset({Place.RAIL, Place.MODAL})
    ),
    Surface(
        "data_management",
        owner="market_data",
        accepts=frozenset({Place.RAIL, Place.MODAL}),
    ),
)


def surfaces_by_id() -> dict[str, Surface]:
    return {surface.surface_id: surface for surface in SURFACES}
