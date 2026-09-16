"""Guard: a type the application `resolve()`s must be bound somewhere.

## The blind spot, stated once (`BUG-127`, [`CS-003`](../../../Docs/CASE_STUDIES/
CS-003_the_port_nobody_bound.md))

`BOT-095E1` built a market-rule check for the Backtest screen: fetch a symbol's
exchange filters, cache them, and tell the user whether their capital and symbol
would satisfy Binance's minimum notional, lot step and price tick. Every part of
it exists and every part has a passing test. Two wires are missing — nothing
calls the parser that produces the metadata, and **nothing binds the port that
stores it** — so the screen has answered *"not verified against exchange rules"*
for every symbol since the day it shipped, and the real evaluation below that
branch has never run in production.

The second wire is the one a check can see. The consumer does
`container.resolve(ISymbolMarketMetadataCache)` inside a `try`, with a
constructed adapter in the `except`. Because the port is unbound the `resolve()`
raises *every* time, so what reads as a fallback is the only path — and a reader
sees defensive code and assumes the normal path works.

Six checks were green over it, and the sixth is the interesting one:

  · the parser's own test builds a payload and asserts the parse — a producer's
    test cannot notice it has no callers;
  · the cache adapter's own test builds a cache and asserts `put`/`get` — same
    shape, same blindness;
  · the consumer's tests inject `get_market_metadata` directly, so they prove
    both branches of the logic and ask nothing about who fills the cache;
  · `mypy` cannot help: `IContainer.resolve()` returns `Any`, and
    `src/presentation/` is excluded wholesale (`EPIC-002A` §2) — the same two
    conditions that hid `BUG-124` (`CS-001`);
  · `ruff` sees an unused *import*, never a function with no callers;
  · **`test_a_bus_subscriber_is_constructed.py`** — `CS-002`'s guard, written for
    precisely this disease, *"proving a class works and calling that proof the
    program works"*. It scans **bus subscribers**. A port with no binding is the
    same disease in a different organ, and the narrow guard missed it.

So this is the wider statement of the same rule: if application code asks the
container for a type, something must have taught the container how to build it.
Unbound, `resolve()` raises at runtime — either crashing the caller or, as here,
landing silently in an `except` that makes the defect invisible.

## Why "bound anywhere" rather than "bound by the right module"

Deliberately the weakest claim that still excludes the defect, for the reason
`test_a_bus_subscriber_is_constructed.py` gives for checking *named* rather than
*called*: bindings are registered from several legitimate places during the
strangler period — a module's `composition/`, `binance_bot_module.py`, the
composition root — and a guard that insisted on one of them would fail on
correct code. Measured against this tree the weak form separates cleanly: 43
resolved names, 40 bound, and the three that are not split into two categories
with nothing ambiguous between them.

`ISizingPolicy` is the useful counter-example of what this guard must **not**
flag. It is unbound on purpose and `port_bindings.py` says why — its consumers
hold it as a constructor parameter, and *"a binding nothing resolves is dead
wiring, which is what `BUG-120` was"*. Nothing resolves it, so it never reaches
this guard. Unbound is fine; unbound **and resolved** is the defect.

Stdlib only, like the other architecture guards here. It reads identifiers from
the **AST**, never the file text — the mistake `CS-002`'s first draft made, where
a docstring mention was enough to call a dead class live.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("no pyproject.toml above this file")


_REPO_ROOT = _repo_root()

#: Where a `resolve()` may appear and where a binding may be registered. Both
#: roots, both questions: `scripts/` probes resolve real ports and also bind
#: their own doubles, so excluding them would both miss violations and invent
#: them.
_ROOTS = ("src", "scripts")

#: The container verbs, as `IContainer` names them.
_BINDING_VERBS = frozenset({"bind", "singleton"})
_RESOLVE_VERB = "resolve"

#: Registered by the **Engine**, not by this application, so no `bind()` call
#: exists in this repository to find. `EngineContext.__init__` puts `Scheduler`
#: in the container directly; `ThreadManagerExtension.register()` binds
#: `IThreadManager`. This is a category — "the kernel provides it" — rather than
#: a list of known violations, which is why it is not a ratchet file: a fourth
#: engine service resolved by app code belongs here, with the extension that
#: registers it named. If one is added and the engine *stops* providing it, the
#: failure is a boot crash that no guard can pre-empt.
_ENGINE_PROVIDED = frozenset({"IThreadManager", "Scheduler"})

#: `BUG-127`, and the one entry this guard ships with. `ISymbolMarketMetadataCache`
#: is resolved by `backtest_presenter.py` and bound by nobody, which is the defect
#: the guard was written for — so it lands red and is admitted here, once, naming
#: its exit. **The line is deleted by the commit that binds the port**, and the
#: guard then has no ratchet at all. Anything else added here needs the argument
#: `ci-rule.md` §5.5 demands of a ceiling; this list may only shrink.
_KNOWN_UNBOUND: frozenset[str] = frozenset({"ISymbolMarketMetadataCache"})


def _trees(*roots: str) -> dict[Path, ast.Module]:
    found: dict[Path, ast.Module] = {}
    for root in roots:
        for path in sorted((_REPO_ROOT / root).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                found[path] = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:  # pragma: no cover - a parse error is ruff's job
                continue
    return found


def _shown(path: Path) -> str:
    """A repository-relative path for the failure message, or the path itself.

    `test_the_guard_can_actually_fail` feeds this reader synthetic paths that
    are deliberately outside the repository, and a guard that raises while
    building an error string is a guard that cannot report — so the relative
    form is an improvement on the message, not a requirement of it.
    """
    try:
        return path.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _first_arg_name(call: ast.Call) -> str | None:
    """The abstract type a container call names, when it names one plainly.

    `container.singleton(IPort, Adapter)` gives `IPort`. A call whose first
    argument is an expression rather than a name — a subscript, a variable
    holding a type — is skipped: this guard reports what it can read, and a
    silent skip is safer than a guess, because the non-vacuity test below keeps
    the readable set large enough to matter.
    """
    if not call.args:
        return None
    first = call.args[0]
    return first.id if isinstance(first, ast.Name) else None


def _container_calls(
    trees: Mapping[Path, ast.Module],
) -> tuple[set[str], dict[str, list[str]]]:
    """`(bound type names, resolved type name -> where)`."""
    bound: set[str] = set()
    resolved: dict[str, list[str]] = {}
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            ):
                continue
            name = _first_arg_name(node)
            if name is None:
                continue
            if node.func.attr in _BINDING_VERBS:
                bound.add(name)
            elif node.func.attr == _RESOLVE_VERB:
                resolved.setdefault(name, []).append(f"{_shown(path)}:{node.lineno}")
    return bound, resolved


def _unbound_resolves(trees: Mapping[Path, ast.Module]) -> dict[str, list[str]]:
    """Resolved types with no binding, minus the two categories that are fine."""
    bound, resolved = _container_calls(trees)
    return {
        name: sites
        for name, sites in sorted(resolved.items())
        if name not in bound
        and name not in _ENGINE_PROVIDED
        and name not in _KNOWN_UNBOUND
    }


def test_every_resolved_type_is_bound() -> None:
    """The check `BUG-127` needed. One second, against `src/` and `scripts/`."""
    offenders = _unbound_resolves(_trees(*_ROOTS))

    assert offenders == {}, (
        "these types are asked of the container but nothing binds them, so "
        "`resolve()` raises at runtime — either crashing the caller or landing "
        "in an `except` that hides the defect, which is exactly BUG-127:\n"
        + "\n".join(
            f"  {name}\n" + "".join(f"      {site}\n" for site in sites)
            for name, sites in offenders.items()
        )
        + "\nBind it where it belongs, or stop resolving it. A port whose only "
        "runtime answer is an exception is not wired."
    )


def test_the_guard_has_a_subject() -> None:
    """A path-scanning guard that has lost its subject passes, faster — the
    failure `ui_trees.py` exists to prevent. Locked at "more than twenty"
    resolved names rather than an exact number, because the count moves with
    every port this epic publishes or retires."""
    _, resolved = _container_calls(_trees(*_ROOTS))

    assert len(resolved) > 20, (
        f"only {len(resolved)} resolved type name(s) found across {_ROOTS}. "
        "Either the application stopped asking the container for things — in "
        f"which case the verb `.{_RESOLVE_VERB}(...)` has changed and this "
        "guard reads nothing — or a scan root moved."
    )


def test_the_known_unbound_list_is_still_earning_its_place() -> None:
    """A ratchet entry for a type that is now bound is a stale exemption, and a
    stale exemption is how a guard quietly stops checking. `BUG-127`'s fix must
    delete its line here, not leave it behind."""
    bound, resolved = _container_calls(_trees(*_ROOTS))

    stale = sorted(name for name in _KNOWN_UNBOUND if name in bound)
    assert stale == [], (
        f"{stale} is bound now, so its line in `_KNOWN_UNBOUND` is doing "
        "nothing except excusing a future regression. Delete it."
    )

    unused = sorted(name for name in _KNOWN_UNBOUND if name not in resolved)
    assert unused == [], (
        f"{unused} is not resolved anywhere, so it never reaches this guard "
        "and does not need an exemption. Unbound-and-unresolved is fine "
        "(`ISizingPolicy` is the documented example). Delete the line."
    )


def test_the_guard_can_actually_fail() -> None:
    """Fed a resolve with no binding, the guard must say so; fed the same
    resolve with a binding, it must go quiet.

    A guard never seen red is a guard nobody knows runs, and this one exists
    *because* six checks were green over the defect. Asserting both directions
    is what separates it from them."""
    root = Path("/synthetic/src")
    consumer = ast.parse("cache = container.resolve(IThing)\n")

    unwired = _unbound_resolves({root / "consumer.py": consumer})
    wired = _unbound_resolves(
        {
            root / "consumer.py": consumer,
            root / "bindings.py": ast.parse("container.singleton(IThing, Thing)\n"),
        }
    )

    assert list(unwired) == ["IThing"], (
        f"the guard accepted a resolve with no binding anywhere. Got {unwired}."
    )
    assert wired == {}, f"the guard rejected a type that is bound: {wired}"
