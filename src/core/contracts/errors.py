"""Failures the contribution contract raises across a module boundary.

A port's failure modes are part of its contract (`architecture-rule.md` §5 and
the SDD's "Errors in `contracts/`"), so they live beside the port rather than in
the implementation that happens to raise them first.
"""

from __future__ import annotations


class ContributionError(Exception):
    """A contribution was rejected at `contribute()` time.

    Always names the contributor, the surface and the place, because the
    information a reader needs is *who asked for what*, not a traceback into the
    registry. Raised for an unknown `surface_id`, a `place` the surface does not
    accept, and a duplicate `(surface_id, place, contributor_id, factory)`.

    Deliberately fatal rather than a warning: an unknown surface id is a typo,
    and a typo that only shows up as a missing panel at runtime is the failure
    mode pluggy's validation exists to prevent (HLD §7.3).
    """
