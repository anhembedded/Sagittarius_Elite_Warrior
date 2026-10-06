"""The surfaces this application has, and what each one can hold (SDD).

A **surface** is a place a user navigates to. It is owned either by the shell
(`trading`, `developer` — the workbench itself) or by the
module whose subject it is (`backtest`, `data_management`). Owning a surface
means declaring it here; it does not mean the owner fills it — any module may
contribute to any surface, which is the whole point of the mechanism.

`accepts` is a contract, checked at `contribute()` time: a module that offers a
place a surface does not hold has misunderstood that surface, and hears so
immediately rather than by finding its panel missing at runtime.

`gated_by` names a run-time condition. A gated surface is **declared even when
it is off**, so contributions to it are *dropped with a log line* instead of
raising — the normal user run drops every Developer mode probe and boots
(validation rule 3). Declaring it conditionally would turn that normal case into a crash.

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
#: The Developer mode's surface (`EPIC-033P`): the event log central, the
#: probes docked right (HLD §11.2.1, §11.2.5).
DEVELOPER_SURFACE_ID = "developer"

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
    Surface("trading", owner="shell", accepts=_WORKBENCH_PLACES),
    Surface(
        DEVELOPER_SURFACE_ID,
        owner="shell",
        accepts=frozenset({Place.WORKSPACE, Place.DEV_PROBE}),
        gated_by=DEV_MODE_GATE,
    ),
    Surface(
        "backtest",
        owner="backtesting",
        accepts=frozenset(
            {Place.WORKSPACE, Place.NAVIGATOR, Place.RAIL, Place.CONSOLE}
        ),
    ),
    Surface(
        "bots",
        owner="bots",
        accepts=frozenset(
            {Place.WORKSPACE, Place.NAVIGATOR, Place.RAIL, Place.CONSOLE}
        ),
    ),
    Surface(
        "market", owner="trading", accepts=frozenset({Place.WORKSPACE, Place.RAIL})
    ),
    # `EPIC-033I` — the Trade mode's places; each venue's page is a surface of
    # these places under its own id, so each keeps its own layout.
    Surface(
        "trade",
        owner="trading",
        accepts=frozenset({Place.WORKSPACE, Place.HEADER, Place.RAIL, Place.CONSOLE}),
    ),
    Surface(
        "data_management",
        owner="market_data",
        accepts=frozenset({Place.WORKSPACE, Place.CONSOLE}),
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
    return gate_is_open(surface.gated_by, dev_mode=dev_mode, subject=surface.surface_id)


def gate_is_open(gate: str | None, *, dev_mode: bool, subject: str) -> bool:
    """Is `gate` open in this run? One evaluation for a surface and a screen
    (`EPIC-033P`), so the two can never disagree on what a key means.

    @param subject What carries the gate, for the error naming an unknown one.
    """
    if gate is None:
        return True
    if gate == DEV_MODE_GATE:
        return dev_mode
    raise ValueError(f"{subject!r} has an unknown gate {gate!r}")
