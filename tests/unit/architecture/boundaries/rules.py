"""The boundary policy: may module A import module B? (HLD §6.1, ADR D1 / D4)

Pure functions over dotted module names. No file system, no AST — the tests
in `test_boundary_rules.py` pin the table row by row.
"""

from __future__ import annotations

from .zones import (
    CONFIG_ZONE,
    LEGACY_ZONES,
    is_contracts_package,
    is_module_entry_point,
    sub_package_of,
    top_of,
    zone_of,
)

#: Support packages a module's `ui/` sub-package may import whole, not only
#: through their `contracts/` (HLD §6.1: charting and the UI kit are UI).
_UI_SUPPORT_ZONES = frozenset({"support/ui_kit", "support/charting"})

#: `support/indicators` minus its `ui/`: the indicator **mathematics**, which any
#: module may read directly rather than through a `contracts/` package.
#:
#: The third widening of the importing side in this epic, and the same shape as
#: the two before it — a rule narrower than the assignment the HLD itself makes.
#: HLD §3.4 puts the indicator library in this support package and §3.4 puts the
#: strategies in `modules/strategy`, and a strategy's whole job is to declare and
#: read indicators. Measured before changing anything (PR 2.1b):
#: `modules/strategy` needs `IIndicator`, `EMA`, `MACDValue`,
#: `SupportResistance` and `scripting.Series` — **14 imports across 8 files** —
#: which is not a corner of the package but its entire public surface.
#:
#: So the alternative was a `support/indicators/contracts/` re-exporting five
#: names for one consumer: an alias file with no decision in it, written to
#: satisfy a rule. PR 1.6f rejected the same construction for `Palette` and
#: widened the table instead; this follows that precedent rather than inventing
#: a second answer.
#:
#: The sub-packages are named, not excluded, so a future `adapters/` under this
#: package is refused by default rather than importable by omission. They are the
#: same four `test_module_domain_is_qt_free.py` declares Qt-free — one fact,
#: stated in two guards, and each file says so.
_COMPUTATION_SUPPORT_ZONES = frozenset({"support/indicators"})
_COMPUTATION_SUB_PACKAGES = frozenset(
    {"indicators", "indicator_scripts", "scripting", "indicator_script_registry"}
)

#: Nothing imports the shell — it is *Main*, so a dependency on it is a cycle by
#: definition. The exception is an **entry point**: a module whose only job is to
#: start the process. The GUI's still lives in the legacy tree and calls the
#: shell for configuration, the module list and the screens; it moves into
#: `shell/` when Phase 1 turns the window into the surface host, and this set is
#: empty again. Listed by module name so the permission covers one file, not a
#: package.
_ENTRY_POINT_MODULES = frozenset({"presentation.ui.app_bootstrapper"})


def import_is_allowed(importing_module: str, imported_module: str) -> bool:
    src_zone = zone_of(importing_module)
    dst_zone = zone_of(imported_module)
    if src_zone is None or dst_zone is None or src_zone == dst_zone:
        return True
    if dst_zone == CONFIG_ZONE:
        return True  # key names are vocabulary, not a dependency
    if src_zone == CONFIG_ZONE:
        return False  # and `config/` itself imports nothing

    if src_zone == "shell":
        return _shell_may_import(dst_zone, imported_module)
    if src_zone in LEGACY_ZONES:
        return _legacy_may_import(importing_module, src_zone, dst_zone, imported_module)
    if dst_zone in LEGACY_ZONES:
        # The new tree never imports the legacy tree; during its own phase a
        # module goes through the allowlist, visibly.
        return False

    src_top = top_of(src_zone)
    if src_top == "core":
        return False  # core imports only core (the equality above)
    if src_top == "support":
        return _support_may_import(
            importing_module, src_zone, dst_zone, imported_module
        )
    if src_top == "modules":
        return _module_may_import(importing_module, dst_zone, imported_module)
    return False


def _legacy_may_import(
    importing_module: str, src_zone: str, dst_zone: str, imported_module: str
) -> bool:
    if dst_zone in LEGACY_ZONES:
        return _legacy_layer_allows(src_zone, dst_zone)
    if dst_zone == "shell":
        return importing_module in _ENTRY_POINT_MODULES
    # Strangler period (Phases 0–4): the old tree may reach the new one through
    # contracts, the Shared Kernel and the support packages.
    dst_top = top_of(dst_zone)
    if dst_top in {"core", "support"}:
        return True
    if dst_top == "modules":
        return is_contracts_package(imported_module)
    return False


def _legacy_layer_allows(src_zone: str, dst_zone: str) -> bool:
    """`architecture-rule.md` §3: Domain → Application → Presentation, with
    Infrastructure outermost; nothing points outward."""
    if src_zone == "application":
        return dst_zone in {"domain", "config"}
    if src_zone == "presentation":
        return dst_zone != "infrastructure"
    if src_zone == "infrastructure":
        return dst_zone != "presentation"
    return False  # domain and config import nothing else


def _support_may_import(
    importing_module: str, src_zone: str, dst_zone: str, imported_module: str
) -> bool:
    dst_top = top_of(dst_zone)
    if dst_top == "core":
        return True
    if dst_top != "support":
        return False
    if is_contracts_package(imported_module):
        return True
    # The two support packages HLD §6.1 calls **UI** may use each other whole,
    # exactly as a module's `ui/` may use them both (`_UI_SUPPORT_ZONES`).
    # `EPIC-025` PR 1.6f is what forced the question and measured the
    # alternatives: `support/charting`'s chart card reads `ui_kit`'s palette,
    # its widget kit, its QML embed host, `theme_bootstrap` and the display
    # timezone service — 20 imports across 12 files. Routing them through
    # `ui_kit/contracts` would mean publishing an ABC façade over `Palette`,
    # `StyleRole`, `apply_role` and `QmlOverlay` for a single consumer, and
    # the only other option is for the charting package to carry its own copy
    # of the kit, which is the duplication this epic exists to delete.
    #
    # PR 1.6g widened the *importing* side once, and only in the way the
    # rules already treat modules: a support package's own `ui/` sub-package is
    # display code, so it may use the UI kit exactly as `modules/X/ui` may.
    # `support/indicators` is the case that forced it — its mathematics is
    # Qt-free (`test_module_domain_is_qt_free.py` names those three
    # sub-packages) while its `ui/` holds a `QAbstractListModel`, and that
    # model needs `AnyIndex` from the kit.
    #
    # Still deliberately narrow, and the three edges that must keep failing
    # are pinned in `test_boundary_rules.py`: `binance_gateway -> ui_kit` has
    # no `ui/` and no reason; `indicators.indicator_scripts -> ui_kit` is the
    # mathematics reaching for a widget, which the Qt-free guard forbids from
    # the other side; and nothing in `support/` may reach a module or the
    # legacy tree at all.
    if dst_zone not in _UI_SUPPORT_ZONES:
        return False
    return src_zone in _UI_SUPPORT_ZONES or sub_package_of(importing_module) == "ui"


def _module_may_import(
    importing_module: str, dst_zone: str, imported_module: str
) -> bool:
    dst_top = top_of(dst_zone)
    if dst_top == "core":
        return True
    if dst_top == "modules":
        return is_contracts_package(imported_module)
    if dst_top == "support":
        if is_contracts_package(imported_module):
            return True
        if _is_computation_library(dst_zone, imported_module):
            return True
        return (
            sub_package_of(importing_module) == "ui" and dst_zone in _UI_SUPPORT_ZONES
        )
    return False


def _is_computation_library(dst_zone: str, imported_module: str) -> bool:
    """The Qt-free half of `support/indicators` — readable from anywhere in a
    module, including its `ui/`, because mathematics has no layer.

    Deliberately not restricted to `domain`: `strategy_engine` reads
    `IIndicator` from `application/services/`, and a rule that let the
    strategies read the library while refusing the engine that runs them would
    be arbitrary. What it does refuse is this package's `ui/` — a module
    reaching for another package's `QAbstractListModel` is the edge
    `test_boundary_rules.py` pins as a failure.
    """
    return (
        dst_zone in _COMPUTATION_SUPPORT_ZONES
        and sub_package_of(imported_module) in _COMPUTATION_SUB_PACKAGES
    )


def _shell_may_import(dst_zone: str, imported_module: str) -> bool:
    dst_top = top_of(dst_zone)
    if dst_top in {"core", "support"}:
        return True
    if dst_top == "modules":
        return is_contracts_package(imported_module) or is_module_entry_point(
            imported_module
        )
    # Strangler period (Phases 0–4): the shell is *Main*, so it wires whatever
    # exists — today that includes the five legacy screens it carries as
    # contributions (`shell/legacy_screen_adapter.py`). Permitted, but not
    # unwatched: `test_module_boundaries.py` records every such import in
    # `baseline_shell_legacy_imports.txt`, shrink-only, and that file is empty
    # once Phase 4 deletes the legacy tree.
    return dst_zone in LEGACY_ZONES
