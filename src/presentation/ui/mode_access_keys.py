"""`BOT-210` — the access key of each mode's item in View, declared by the mode.

The window gave each title the first letter no earlier title and no View item of its own used, in
mode order, so adding a mode (`Alerts`, `EPIC-036D2`) moved a later mode onto a letter a View
command of another mode already held, and the engine's registry refused the clash at boot. A mode
now declares its letter in its `NavMetadata`; it moves when the mode's own title does, never when
another mode comes or goes. A declaration the window cannot honour is refused by name, at boot:
a letter that is not in the title, one two modes declare, or one the View menu's own items hold.

A mode that declares none (a fake screen in a test) is given the next letter left over, as before.
"""

from __future__ import annotations

from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.core.contracts.nav_metadata import NavMetadata
from sagittarius_engine.extensions.pyside_mvc.workbench.access_key_assignment import (
    assign_access_keys,
)


class ModeAccessKeyError(ValueError):
    """A mode's declared access key cannot be honoured."""


def mode_labels(navs: Sequence[NavMetadata], reserved: Sequence[str]) -> list[str]:
    """Each mode's title with its access key marked by `&`, in `navs`' order.
    @param reserved The letters the View menu's own items hold.
    @raise ModeAccessKeyError A declared letter that is not one letter of its title, that two
    modes declare, or that is in `reserved`."""
    held = {key.lower() for key in reserved}
    declared: dict[str, str] = {}
    for nav in navs:
        if not nav.access_key:
            continue
        key = nav.access_key.lower()
        _check(nav, key, held, declared)
        declared[key] = nav.title
    taken = [*held, *declared]
    undeclared = [nav.title for nav in navs if not nav.access_key]
    assigned = iter(assign_access_keys(undeclared, taken))
    return [
        _marked(nav.title, nav.access_key) if nav.access_key else next(assigned)
        for nav in navs
    ]


def _check(
    nav: NavMetadata, key: str, held: set[str], declared: dict[str, str]
) -> None:
    if len(key) != 1 or key not in nav.title.lower():
        raise ModeAccessKeyError(
            f"mode {nav.title!r} declares access key {nav.access_key!r}, "
            "which is not one letter of its title"
        )
    if key in held:
        raise ModeAccessKeyError(
            f"mode {nav.title!r} declares access key {key!r}, "
            "which an item of the View menu holds"
        )
    if key in declared:
        raise ModeAccessKeyError(
            f"modes {declared[key]!r} and {nav.title!r} both declare access key {key!r}"
        )


def _marked(title: str, key: str) -> str:
    at = title.lower().index(key.lower())
    return f"{title[:at]}&{title[at:]}"
