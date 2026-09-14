"""A verified fake's extra helpers are verified too, by its own module's tests.

`BUG-120`. HLD §10.3 ships every published port with a fake and a contract
suite, and calls the fake *verified* because the suite runs against both it and
the real implementation. That verifies the surface the **port declares**. A
fake may declare more, and `FakeMarketDataSync` did: `was_asked_for()` became
the only positive assertion in three screens' tests
(`test_chart_coordinator.py`, `test_sync_coordinator.py`,
`test_dashboard_presenter.py`), and hard-coding it to `return True` left all
152 of those tests green. A helper that cannot fail is not a stronger
assertion than the `Mock` it replaced — it is the same nothing with a better
name.

**Why the module's own tests, and not the consumer's.** Three consumers called
`was_asked_for` and none of them verified it; that is the defect, not an
accident of where they live. A consumer calls a helper to say something about
*itself*. Whether the helper answers truthfully is the provider's guarantee,
so it belongs beside the contract suite, in
`tests/unit/modules/<module>/contracts/` — the same place, and the same
reasoning, that puts the contract suite there rather than in each consumer.

**What this does not ask for.** The port's own methods are left alone: the
contract suite covers `sync()` eleven ways, and a second opinion here would be
a weaker copy. Nor does it look at instance state — `requests` is read by the
suite through its `observed` fixture. Only members the fake adds and the port
never declared, which is the exact set nothing else checks.

**A fake with no extra helpers passes silently, and should.**
`FakeMarketDataRepository` and `FakeSymbolCatalog` declare nothing beyond
their ports, so this guard has one thing to check today. It is written to be
live before the second one arrives — Phase 1 adds `IHistoricalKlines` and
`IMarketStream`, and three market_data ports still have no suite at all.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.tests.unit.architecture.fake_helpers import (
    attributes_used,
    declared_by_port,
    fakes_in,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC = _REPO_ROOT / "src"
_TESTS = _REPO_ROOT / "tests"

#: Where a module's fakes live, by HLD §10.3.
_FAKE_GLOB = "modules/*/contracts/testing/fake_*.py"


def _fake_files() -> list[Path]:
    return sorted(
        path for path in _SRC.glob(_FAKE_GLOB) if "__pycache__" not in path.parts
    )


def _module_of(fake_path: Path) -> str:
    """`src/modules/market_data/contracts/testing/fake_x.py` -> `market_data`."""
    return fake_path.relative_to(_SRC / "modules").parts[0]


def _port_source(port_module: str) -> str | None:
    """The port's own source, from the dotted module the fake imported it from."""
    path = _SRC / Path(*port_module.split(".")).with_suffix(".py")
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _names_exercised_by(module_id: str) -> set[str]:
    """Every attribute the module's own contract tests read or call."""
    root = _TESTS / "unit" / "modules" / module_id / "contracts"
    used: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        used |= attributes_used(path.read_text(encoding="utf-8"))
    return used


def test_there_are_fakes_to_scan() -> None:
    """A guard that scans nothing passes everything (HLD §9.3 rule 4)."""
    files = _fake_files()
    assert files, f"no fake found under {_SRC}/{_FAKE_GLOB}"


def test_every_fake_names_the_port_it_stands_in_for() -> None:
    """A fake that inherits no port cannot be checked against one — and it is
    also not a verified fake, because the contract suite would have nothing to
    run it as."""
    nameless: list[str] = []

    for path in _fake_files():
        for fake in fakes_in(path.read_text(encoding="utf-8")):
            if fake.port_name is None:
                nameless.append(
                    f"  {path.relative_to(_REPO_ROOT).as_posix()}:{fake.line}  "
                    f"{fake.class_name} inherits no imported port"
                )

    assert nameless == [], (
        "a fake under `contracts/testing/` does not implement a port:\n"
        + "\n".join(nameless)
    )


def test_a_fakes_extra_helpers_are_exercised_by_its_own_modules_tests() -> None:
    unverified: list[str] = []

    for path in _fake_files():
        module_id = _module_of(path)
        exercised = _names_exercised_by(module_id)

        for fake in fakes_in(path.read_text(encoding="utf-8")):
            if fake.port_module is None or fake.port_name is None:
                continue
            port_source = _port_source(fake.port_module)
            if port_source is None:
                continue
            from_port = declared_by_port(port_source, fake.port_name)

            for member in fake.members:
                if member.name in from_port or member.name in exercised:
                    continue
                unverified.append(
                    f"  {path.relative_to(_REPO_ROOT).as_posix()}:{member.line}  "
                    f"{fake.class_name}.{member.name}() — not on "
                    f"{fake.port_name}, and never called under "
                    f"tests/unit/modules/{module_id}/contracts/"
                )

    assert unverified == [], (
        "a verified fake declares a helper nothing verifies. The contract\n"
        "suite covers what the *port* declares; a helper the fake adds is\n"
        "covered by nobody, and a consumer asserting through it asserts\n"
        "nothing — `BUG-120`, where `was_asked_for()` could return a constant\n"
        "`True` with 152 tests still green. Either give it a test beside the\n"
        "contract suite, or delete it: a helper with no consumer and no test\n"
        "is dead published API.\n" + "\n".join(unverified)
    )


# -- the reader works, proven on source this file carries itself -------------


_A_FAKE = """
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_thing import (
    IThing,
)


class FakeThing(IThing):
    def __init__(self) -> None:
        self.calls = []

    def do_it(self) -> None:
        self.calls.append(1)

    @property
    def how_many(self) -> int:
        return len(self.calls)

    def _private(self) -> None:
        pass
"""

_THE_PORT = """
from abc import ABC, abstractmethod


class IThing(ABC):
    @abstractmethod
    def do_it(self) -> None: ...
"""


def test_the_reader_separates_the_ports_methods_from_the_fakes_own() -> None:
    fake = fakes_in(_A_FAKE)[0]

    assert fake.class_name == "FakeThing"
    assert fake.port_name == "IThing"
    assert fake.port_module == "modules.market_data.contracts.i_thing"

    from_port = declared_by_port(_THE_PORT, "IThing")
    extra = {member.name for member in fake.members} - from_port

    assert from_port == {"do_it"}
    assert extra == {"how_many"}, (
        "a property counts: it runs code the port never declared"
    )


def test_the_reader_ignores_private_members_and_instance_state() -> None:
    """`_private()` is not API, and `self.calls` is state the contract suite
    reads through its own fixture rather than a helper anyone calls."""
    names = {member.name for member in fakes_in(_A_FAKE)[0].members}

    assert names == {"do_it", "how_many"}


def test_the_reader_does_not_take_a_test_local_subclass_for_a_port() -> None:
    """`_ReportingSync(FakeMarketDataSync)` in a consumer's test file is the
    shape: a base the file defines or imports from another fake is not a port,
    so the class is reported with `port_name=None` rather than checked against
    a class that does not exist."""
    source = (
        "class FakeLocal(SomethingDefinedHere):\n    def helper(self) -> None: ...\n"
    )

    assert fakes_in(source)[0].port_name is None


def test_the_reader_counts_a_call_but_not_a_mention() -> None:
    """The distinction the guard rests on: a helper named in a docstring looks
    like coverage and is not."""
    assert attributes_used("sync.was_asked_for('BTCUSDT')") == {"was_asked_for"}
    assert attributes_used('"""was_asked_for is great"""') == set()
