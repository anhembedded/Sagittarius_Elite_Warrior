"""What a verified fake offers *beyond* the port it stands in for.

`ast`, never a regex (`BOT-133`, same reason `mocked_ports.py` gives): the
question is which **class** declares a name, and a regex cannot tell a method
the fake adds apart from one it inherits from the port.

**Why anybody needs to ask.** HLD §10.3 makes a fake verified by running the
provider's contract suite against both the fake and the real implementation.
That verifies exactly the surface the *port declares* — and a fake is free to
declare more. A query helper the port never heard of (`was_asked_for`,
`synced_symbols`) is then a published test API that no contract covers, and a
consumer asserting through it is asserting against nothing (`BUG-120`).

The policy that uses this lives in `test_fake_helpers_are_verified.py`; this
file only reports what is there.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.tests.unit.architecture.boundaries.imports import (
    imported_names,
)


@dataclass(frozen=True)
class Member:
    """One public method or property a class declares in its own body."""

    name: str
    line: int


@dataclass(frozen=True)
class Fake:
    """One fake class: the port it stands in for, and what it declares itself.

    `port_module` is dotted and relative to `src/`, so the caller can resolve
    it to a file the same way every other guard here does. It is `None` when
    no base class looks like a port — a fake that inherits nothing, or that
    subclasses another fake (which is what a consumer's test-local subclass
    does, and those are not published API).
    """

    class_name: str
    line: int
    port_name: str | None
    port_module: str | None
    members: tuple[Member, ...]


def _public_members(node: ast.ClassDef) -> tuple[Member, ...]:
    """Public methods and properties in one class body, in line order.

    Instance attributes set in `__init__` are deliberately **not** collected.
    `FakeMarketDataSync.requests` is the fake's state, and the contract suite
    already reads it — the subclass that wires the fake hands it back as the
    `observed` fixture, so all eleven guarantees run through it. What this
    reports is the *query surface*: code the fake executes and nothing else
    does.
    """
    return tuple(
        Member(name=child.name, line=child.lineno)
        for child in node.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not child.name.startswith("_")
    )


def _port_base(node: ast.ClassDef, imports: dict[str, str]) -> tuple[str, str] | None:
    """The first base class that is an imported `I…` name, with its module.

    The `I` prefix is this repository's own spelling for a port, checked
    against the imports rather than guessed from the name alone: a base the
    file did not import is a locally defined class, which is a test-local
    subclass rather than a port.
    """
    for base in node.bases:
        if not isinstance(base, ast.Name):
            continue
        module = imports.get(base.id)
        if module is not None and base.id.startswith("I"):
            return base.id, module
    return None


def fakes_in(source: str) -> list[Fake]:
    """Every class in `source` whose name starts with `Fake`, in line order."""
    tree = ast.parse(source)
    imports = imported_names(tree)
    found: list[Fake] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or not node.name.startswith("Fake"):
            continue
        port = _port_base(node, imports)
        found.append(
            Fake(
                class_name=node.name,
                line=node.lineno,
                port_name=port[0] if port else None,
                port_module=port[1] if port else None,
                members=_public_members(node),
            )
        )

    return sorted(found, key=lambda fake: fake.line)


def declared_by_port(source: str, port_name: str) -> set[str]:
    """The public member names the port class itself declares.

    Bases of the port are not followed: every port in this repository derives
    straight from `ABC`, and a port that grew a hierarchy would be a change
    worth noticing rather than one to resolve silently.
    """
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and node.name == port_name:
            return {member.name for member in _public_members(node)}
    return set()


def attributes_used(source: str) -> set[str]:
    """Every attribute name `source` reads or calls — `x.foo` gives `"foo"`.

    Attribute access rather than a text search: a helper named in a docstring
    or a comment has not been exercised, and this guard exists precisely
    because something that looks like coverage is not.
    """
    return {
        node.attr
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Attribute)
    }
