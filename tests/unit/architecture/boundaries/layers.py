"""Layer direction **inside** one bounded-context module (`EPIC-030E`).

`rules.import_is_allowed` answers "may zone A import zone B?" and returns
`True` for any two modules in the same zone (`rules.py`'s `src_zone ==
dst_zone`), so `modules.strategy.domain` importing `modules.strategy.ui` was
never asked about. This file asks it. Pure functions over dotted names, the
same shape as `rules.py`; `scan.find_layer_violations` applies it to the tree.

A module's layer is its sub-package (`zones.sub_package_of`): `domain`,
`application`, `contracts`, `adapters`, `ui`, `composition`, `cli`, … and
`module` for the top-level `module.py`. Dependencies point inward
(`architecture-rule.md` §3): the inside — `domain`, `application`, `contracts`
— never names the outside that is built around it.

`contracts → domain` stays allowed: `src/modules/strategy/contracts/
i_sizing_policy.py` (its `default_sizing_policy` docstring) records the
decision, with `market_data/contracts/i_market_data_repository.py` as the
precedent — a contract may hand out its own module's domain types.

Layers not named below (`config`, the package `__init__`) are unrestricted
here; the cross-zone rules in `rules.py` still apply to them.
"""

from __future__ import annotations

from .zones import sub_package_of, zone_of

#: The layer name of a module's top-level `module.py` (its entry point).
MODULE_ENTRY_LAYER = "module"

_OUTER_LAYERS = frozenset({"adapters", "ui", "composition", "cli", MODULE_ENTRY_LAYER})

#: Layer → the layers of the **same** module it may not import.
FORBIDDEN_LAYER_IMPORTS: dict[str, frozenset[str]] = {
    "domain": _OUTER_LAYERS | {"application"},
    "application": _OUTER_LAYERS,
    "contracts": _OUTER_LAYERS | {"application"},
}


def layer_of(module: str) -> str | None:
    """`modules.trading.ui.panel` → `ui`; `modules.trading.module` →
    `module`; `modules.trading` (the package) → `None`; outside `modules/` →
    `None`."""
    zone = zone_of(module)
    if zone is None or not zone.startswith("modules/"):
        return None
    return sub_package_of(module)


def layer_import_is_allowed(importing_module: str, imported_module: str) -> bool:
    """`False` only when both modules sit in the same `modules/<name>` zone
    and the importer's layer forbids the imported one. Cross-zone imports
    are `rules.import_is_allowed`'s question, not this one."""
    if zone_of(importing_module) != zone_of(imported_module):
        return True
    src_layer = layer_of(importing_module)
    dst_layer = layer_of(imported_module)
    if src_layer is None or dst_layer is None:
        return True
    return dst_layer not in FORBIDDEN_LAYER_IMPORTS.get(src_layer, frozenset())
