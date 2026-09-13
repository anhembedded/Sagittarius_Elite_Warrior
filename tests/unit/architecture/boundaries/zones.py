"""Which *zone* of the source tree a module belongs to (HLD §3, §6.1).

A zone is the unit the boundary rules reason about: one of the four legacy
layers, `config`, or a package of the new tree (`core`, `shell`,
`support/<name>`, `modules/<name>`). Module names are dotted and relative to
`src/`, e.g. `application.ports.i_cqrs`.
"""

from __future__ import annotations

LEGACY_ZONES = frozenset(
    {"domain", "application", "presentation", "infrastructure", "config"}
)

_SINGLE_PACKAGE_ZONES = frozenset({"core", "shell"})
_FAMILY_ZONES = frozenset({"support", "modules"})

#: Index of the sub-package segment in `modules.<name>.<sub_package>...`.
_SUB_PACKAGE_INDEX = 2


def zone_of(module: str) -> str | None:
    """`None` for a module outside the governed tree: third parties, the
    Engine, the standard library, the composition root."""
    parts = module.split(".")
    top = parts[0]
    if top in LEGACY_ZONES or top in _SINGLE_PACKAGE_ZONES:
        return top
    if top in _FAMILY_ZONES and len(parts) > 1:
        return f"{top}/{parts[1]}"
    return None


def top_of(zone: str) -> str:
    """`modules/trading` → `modules`; `domain` → `domain`."""
    return zone.split("/")[0]


def sub_package_of(module: str) -> str | None:
    """`modules.trading.ui.panel` → `ui`; `core.vo` → `None`."""
    parts = module.split(".")
    return parts[_SUB_PACKAGE_INDEX] if len(parts) > _SUB_PACKAGE_INDEX else None


def is_contracts_package(module: str) -> bool:
    return sub_package_of(module) == "contracts"


def is_module_entry_point(module: str) -> bool:
    """`modules.<name>.module` — the one file `shell/` may import from a module."""
    parts = module.split(".")
    return (
        len(parts) == _SUB_PACKAGE_INDEX + 1
        and parts[0] == "modules"
        and parts[-1] == "module"
    )
