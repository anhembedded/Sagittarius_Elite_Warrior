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
        return _support_may_import(dst_zone, imported_module)
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


def _support_may_import(dst_zone: str, imported_module: str) -> bool:
    dst_top = top_of(dst_zone)
    if dst_top == "core":
        return True
    return dst_top == "support" and is_contracts_package(imported_module)


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
        return (
            sub_package_of(importing_module) == "ui" and dst_zone in _UI_SUPPORT_ZONES
        )
    return False


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
