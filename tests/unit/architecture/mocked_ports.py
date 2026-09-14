"""Finding `Mock(spec=IPort)` calls, and whose port each one names.

Pure functions over one file's source, `ast` and never a regex (`BOT-133`) —
a regex over `Mock(spec=...)` cannot tell `ISymbolCatalogRepository` imported
from `modules/market_data/contracts/` apart from a same-named class imported
from anywhere else, and that distinction is the whole rule.

The policy that uses this lives in `test_no_foreign_port_is_mocked.py`; this
file only reports what is there.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.imports import (
    strip_prefix,
)
from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.zones import (
    is_contracts_package,
    zone_of,
)

#: The factories that produce a stand-in from a class. `create_autospec` is
#: included because it is the same act with a different spelling — HLD §10.3
#: rule 4 is about substituting a foreign port at all, not about one function.
_MOCK_FACTORIES = frozenset({"Mock", "MagicMock", "AsyncMock", "create_autospec"})


@dataclass(frozen=True)
class MockedPort:
    """One `Mock(spec=X)` call, with where `X` was imported from."""

    line: int
    #: The name as written, e.g. `IMarketDataRepository`.
    name: str
    #: The dotted module it was imported from, relative to `src/`, or `None`
    #: when the file never imports it (a locally defined class, or a string).
    imported_from: str | None

    def owning_module(self) -> str | None:
        """The `module_id` whose `contracts/` defines this port, if any.

        `None` for anything that is not a module contract: an Engine interface
        (`IConfig`, `IEventBus`), a `core/` port (`ICommandDispatcher`), a
        legacy `application/ports/` one, or a locally defined class. Those are
        not what rule 4 is about.
        """
        if self.imported_from is None:
            return None
        zone = zone_of(self.imported_from)
        if zone is None or not zone.startswith("modules/"):
            return None
        if not is_contracts_package(self.imported_from):
            return None
        return zone.split("/", 1)[1]


def _imported_names(tree: ast.AST) -> dict[str, str]:
    """`{local name: dotted module it came from}` for every `from X import Y`.

    Plain `import X` is not collected: a `Mock(spec=...)` written through a
    dotted path (`module.IPort`) is not a bare `Name` node and is handled as
    "not imported here", which fails open rather than closed. Every import in
    this repository is `from X import Y` (Ruff enforces the style), so the gap
    is theoretical; it is recorded rather than hidden.
    """
    names: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            module = strip_prefix(node.module)
            for alias in node.names:
                names[alias.asname or alias.name] = module
    return names


def mocked_ports(source: str) -> list[MockedPort]:
    """Every `Mock(spec=SomeName)` in `source`, in line order."""
    tree = ast.parse(source)
    imports = _imported_names(tree)
    found: list[MockedPort] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        factory = node.func
        factory_name = (
            factory.id
            if isinstance(factory, ast.Name)
            else factory.attr
            if isinstance(factory, ast.Attribute)
            else None
        )
        if factory_name not in _MOCK_FACTORIES:
            continue

        for keyword in node.keywords:
            if keyword.arg != "spec":
                continue
            if not isinstance(keyword.value, ast.Name):
                continue
            name = keyword.value.id
            found.append(
                MockedPort(line=node.lineno, name=name, imported_from=imports.get(name))
            )

    return sorted(found, key=lambda entry: entry.line)
