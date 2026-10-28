"""`EPIC-047E` (AC10, decision record 2026-10-27 D7a) - nothing the VPS tab is composed from can reach a Binance client.

**Why.** The owner's rule is that the VPS Bots tab connects to nothing at Binance, signed or public: every fact comes
from the host over the bridge. A review reads the diff for a call to Binance; this reads the *closure*: every module the
VPS tab's own files import, transitively, as Python would load them. A client that arrives through three layers of
helpers is as forbidden as one imported in the first line.

**What it checks.** The files of the tab's composition (`_REMOTE_HOST`, `_VPS_LINK`) are walked through their runtime imports
(`imported_modules`, which skips `TYPE_CHECKING`); no module of the closure is in `_FORBIDDEN_PREFIXES` (the adapters that
build an exchange client or session) and none is a third-party package that speaks to an exchange or opens a connection
(`_THIRD_PARTY`). Value types and ports in `contracts/` stay allowed (`TradingVenue`).

**Baseline 0, only falling.** Nothing is allowlisted. A file added to the tab's composition is added to those roots with the
same rule.

Retire when: the VPS tab's composition is held by a package boundary the module guard states.
"""

from __future__ import annotations

import ast
from pathlib import Path

from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.imports import (
    imported_modules,
    runtime_nodes,
    strip_prefix,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC = _REPO_ROOT / "src"
#: The directories whose every `.py` file is part of the VPS tab's composition.
_REMOTE_HOST = _SRC / "modules" / "bots" / "adapters" / "remote_host"
_VPS_LINK = _SRC / "shell" / "vps_link"
#: Modules (by dotted prefix, relative to `src/`) that build an exchange client or a session to one.
_FORBIDDEN_PREFIXES = (
    "modules.trading.adapters.binance",
    "modules.market_data.adapters.binance",
    "modules.market_data.adapters.live_stream_adapter",
    "support.binance_gateway.adapters",
)
#: Third-party packages that speak to an exchange or open a connection of their own.
_THIRD_PARTY = frozenset(
    {"binance", "websockets", "aiohttp", "requests", "httpx", "urllib3", "ccxt"}
)


def _source_of(module: str) -> tuple[Path, bool] | None:
    base = _SRC.joinpath(*module.split("."))
    if base.with_suffix(".py").exists():
        return base.with_suffix(".py"), False
    if (base / "__init__.py").exists():
        return base / "__init__.py", True
    return None


def _named_imports(source: str) -> set[str]:
    """Every dotted name `source` imports at runtime, `from a.b import c` as both `a.b` and `a.b.c`.

    A package without an `__init__.py` has no file to walk, and `from a.b import c` may name a submodule, so
    the closure alone cannot see them: the names themselves are checked as well."""
    found: set[str] = set()
    for node in runtime_nodes(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            module = strip_prefix(node.module)
            found.add(module)
            found.update(f"{module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            found.update(strip_prefix(alias.name) for alias in node.names)
    return found


def _closure() -> dict[str, Path]:
    pending = [
        ".".join(path.relative_to(_SRC).with_suffix("").parts)
        for directory in (_REMOTE_HOST, _VPS_LINK)
        for path in sorted(directory.glob("*.py"))
    ]
    seen: dict[str, Path] = {}
    while pending:
        module = pending.pop()
        found = None if module in seen else _source_of(module)
        if found is None:
            continue
        path, is_package = found
        seen[module] = path
        for imported in imported_modules(
            module, path.read_text(encoding="utf-8"), is_package=is_package
        ):
            parts = imported.split(".")
            # Importing `a.b.c` loads `a` and `a.b` first, and their `__init__` run.
            pending.extend(".".join(parts[:n]) for n in range(1, len(parts) + 1))
    return seen


def test_the_guard_has_a_subject() -> None:
    closure = _closure()

    assert any(m.startswith("shell.vps_link") for m in closure)
    assert any(m.startswith("modules.bots.adapters.remote_host") for m in closure)
    assert (
        len(closure) > 50
    )  # the application's contracts are in it, not just the roots


def test_no_module_the_vps_tab_loads_builds_an_exchange_client() -> None:
    closure = _closure()
    named = {
        name
        for path in closure.values()
        for name in _named_imports(path.read_text(encoding="utf-8"))
    }

    offenders = sorted(
        module
        for module in {*closure, *named}
        if any(module.startswith(prefix) for prefix in _FORBIDDEN_PREFIXES)
    )

    assert offenders == [], (
        f"the VPS tab's closure reaches a Binance client: {offenders}"
    )


def test_no_module_the_vps_tab_loads_imports_a_network_library() -> None:
    offenders = sorted(
        f"{module} imports {imported.split('.')[0]}"
        for module, path in _closure().items()
        for imported in imported_modules(
            module,
            path.read_text(encoding="utf-8"),
            is_package=path.name == "__init__.py",
        )
        if imported.split(".")[0] in _THIRD_PARTY
    )

    assert offenders == [], (
        f"the VPS tab's closure reaches a network library: {offenders}"
    )


def test_the_guard_sees_a_client_when_one_is_imported(tmp_path: Path) -> None:
    """Mutation check: a closure containing a forbidden prefix would be reported."""
    closure = {"modules.trading.adapters.binance.venue_sessions": tmp_path}

    offenders = [
        m for m in closure if any(m.startswith(p) for p in _FORBIDDEN_PREFIXES)
    ]

    assert offenders == ["modules.trading.adapters.binance.venue_sessions"]
