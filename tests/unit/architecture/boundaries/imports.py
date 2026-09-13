"""Collecting the modules one source file imports at runtime.

`ast`, never regular expressions (`BOT-133`). Imports inside an
`if TYPE_CHECKING:` block are skipped — that is how a contract names a Qt type
without depending on Qt at runtime (SDD "Design rules"). Relative imports are
resolved against the importing module; absolute imports lose the repository
prefix so every name is dotted and relative to `src/`.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

#: Dotted prefix every absolute import in this repository starts with.
PACKAGE_PREFIX = "Sagittarius_Elite_Warrior.src."


def imported_modules(
    importing_module: str, source: str, *, is_package: bool = False
) -> set[str]:
    """Every module `source` imports at runtime. Names outside the repository
    (`PySide6`, the Engine, the standard library) come back unchanged."""
    found: set[str] = set()
    for node in _runtime_nodes(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(strip_prefix(alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                found.add(
                    resolve_relative(
                        importing_module, is_package, node.level, node.module
                    )
                )
            elif node.module:
                found.add(strip_prefix(node.module))
    return found


def strip_prefix(name: str) -> str:
    if name.startswith(PACKAGE_PREFIX):
        return name[len(PACKAGE_PREFIX) :]
    return name


def resolve_relative(
    importing_module: str, is_package: bool, level: int, name: str | None
) -> str:
    """`from ..ports import x` inside `application.use_cases.x.handler` →
    `application.use_cases.ports`; one dot is the file's own package."""
    base = importing_module.split(".")
    if not is_package:
        base = base[:-1]
    if level > 1:
        base = base[: len(base) - (level - 1)]
    if name:
        base = base + name.split(".")
    return ".".join(base)


def _runtime_nodes(tree: ast.AST) -> Iterator[ast.AST]:
    """`ast.walk` minus the body of every `if TYPE_CHECKING:` block."""
    stack: list[ast.AST] = [tree]
    while stack:
        node = stack.pop()
        yield node
        if _is_type_checking_guard(node):
            stack.extend(node.orelse)
        else:
            stack.extend(ast.iter_child_nodes(node))


def _is_type_checking_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
