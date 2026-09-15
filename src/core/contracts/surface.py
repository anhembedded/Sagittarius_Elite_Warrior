"""What a surface *is*, as the Published Language (HLD §4.6, SDD-01b).

A **surface** is a place a user navigates to, described by an id, an owner and
the set of places it can hold. This file holds the type and nothing else: which
surfaces this application has is `shell/surfaces.py`, because that is policy,
and evaluating a gate needs this run's `dev.mode`, which is the shell's to read.

Why the type is here rather than beside the list: the surface host
(`support/ui_kit/workbench_surface.py`) renders one, and `support/*` may not
import `shell/` — it is *Main*, so a dependency on it is a cycle by definition
(`tests/unit/architecture/boundaries/rules.py`). `Place`, `SizeHint` and
`ContributionDescriptor` are already here for the same reason: they are the
vocabulary a module, the shell and the host all speak.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.place import Place


@dataclass(frozen=True, slots=True)
class Surface:
    """One navigable surface, and what it will accept."""

    surface_id: str
    #: `"shell"` or a `module_id` — who declares it, not who fills it.
    owner: str
    #: Checked at `contribute()` time and again by the host: a module that
    #: offers a `CONSOLE` panel to `settings` has misunderstood what Settings
    #: is, and hears so immediately rather than by finding its panel missing.
    accepts: frozenset[Place]
    #: A config key that must be true for this surface to exist in a run, or
    #: `None`. The *evaluation* is the shell's (`shell/surfaces.py`); carrying
    #: the key here is what lets a gated surface be declared even when it is
    #: off, so its contributions drop with a log line instead of raising.
    gated_by: str | None = None
