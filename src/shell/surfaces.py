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

The `Surface` type itself is `core/contracts/surface.py`: the host that renders
one lives in `support/ui_kit`, which may not import the shell (PR 1.4b). What
stayed here is the policy — which surfaces exist, which gate each one reads, and
`surface_is_open()`, the evaluation, because only the shell knows this run's
`dev.mode`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.surface import Surface

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


def surface_is_open(surface: Surface, *, dev_mode: bool) -> bool:
    """Does this surface exist in this run?

    A function rather than a method on `Surface`, and deliberately: the type is
    the Published Language every zone speaks, while *which key means what* is
    this application's policy. An unknown gate raises rather than defaulting to
    open — a surface silently appearing in a normal user's app is the failure
    worth being loud about.
    """
    if surface.gated_by is None:
        return True
    if surface.gated_by == DEV_MODE_GATE:
        return dev_mode
    raise ValueError(
        f"surface {surface.surface_id!r} has an unknown gate {surface.gated_by!r}"
    )
