"""No test mocks another module's port — it uses that port's verified fake.

HLD §10.3 rule 4, which ends *"a guard greps for `Mock(spec=I` against foreign
ports"*. This is that guard. It was missing until `EPIC-025` PR 0.4a-3: the
fake and the contract suite landed, one consumer test was converted, and nothing
stopped the next one from reaching for a `Mock` again.

**Why a mock of a foreign port is different from a mock in general.** A
`Mock(spec=IPort)` agrees with whatever the test asserts. It cannot drift *into*
a failure, so when the real implementation's behaviour changes — or was never
what the consumer assumed — the consumer's test stays green and production
breaks. That is `BUG-026` and `BUG-027`, both of which were hand-written
substitutes that had quietly diverged. A verified fake cannot diverge silently:
it runs the provider's own contract suite, so a divergence fails a test.

**What this guard deliberately permits**, because rule 4 is narrower than "never
mock an interface":

- a module mocking **its own** port in its own test (market_data's tests may
  mock `IExchangeClient` — it is the network, and half those tests are about
  whether it gets called at all);
- an **Engine** interface (`IConfig`, `IEventBus`, `IThreadManager`) — a kernel
  service, not a bounded context's contract;
- a **`core/`** port (`ICommandDispatcher`, `IConfigReader`) — owned by nobody,
  and with no module to ship a fake;
- a **legacy** `application/ports/` one, until its module exists.

So the guard fires on exactly one thing: a test under `tests/**/modules/<A>/`
mocking a port defined in `modules/<B>/contracts/` where B is not A — plus any
test outside a module's own tree mocking a module's port, which is a consumer
reaching past the fake.

Today it scans and finds nothing, because `market_data` is the only module and
its own tests are allowed to mock its own ports. That is the same posture the
other guards took before the first module landed (`test_module_declarations.py`):
live *before* the thing it protects exists, so the first violation is caught by
a test that was already running rather than one written afterwards. The
non-vacuity tests below prove the reader works.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.tests.unit.architecture.mocked_ports import mocked_ports

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TESTS_ROOT = _REPO_ROOT / "tests"


def _owning_module_of_test(path: Path) -> str | None:
    """Which module's own tests a file belongs to, from its path.

    `tests/unit/modules/market_data/...` -> `"market_data"`. Anything else —
    `tests/unit/presentation/`, `tests/integration/golden/` — belongs to no
    module, so every module port it mocks is foreign to it.
    """
    parts = path.relative_to(_TESTS_ROOT).parts
    if "modules" in parts:
        index = parts.index("modules")
        if index + 1 < len(parts):
            return parts[index + 1]
    return None


def _test_files() -> list[Path]:
    return sorted(
        path for path in _TESTS_ROOT.rglob("*.py") if "__pycache__" not in path.parts
    )


def test_there_are_test_files_to_scan() -> None:
    """A guard that scans nothing passes everything (HLD §9.3 rule 4)."""
    files = _test_files()
    assert len(files) > 100, f"only {len(files)} test files found under {_TESTS_ROOT}"


def test_no_test_mocks_a_port_owned_by_another_module() -> None:
    offenders: list[str] = []

    for path in _test_files():
        test_owner = _owning_module_of_test(path)
        for entry in mocked_ports(path.read_text(encoding="utf-8")):
            port_owner = entry.owning_module()
            if port_owner is None or port_owner == test_owner:
                continue
            offenders.append(
                f"  {path.relative_to(_REPO_ROOT).as_posix()}:{entry.line}  "
                f"{entry.name} is owned by `{port_owner}`"
            )

    assert offenders == [], (
        "a test mocks a port owned by another module. Use that module's verified\n"
        "fake from `modules/<owner>/contracts/testing/` instead — a Mock agrees\n"
        "with whatever you assert and cannot tell you the real port changed\n"
        "(HLD §10.3 rule 4; BUG-026, BUG-027). If the guarantee you need is not\n"
        "in the provider's contract suite, add it there — that is the\n"
        "consumer-driven half of the mechanism.\n" + "\n".join(offenders)
    )


# -- the reader works, proven on source this file carries itself -------------


def test_the_reader_sees_a_foreign_module_port() -> None:
    source = (
        "from unittest.mock import Mock\n"
        "from Sagittarius_Elite_Warrior.src.modules.market_data.contracts."
        "i_market_data_repository import IMarketDataRepository\n"
        "repo = Mock(spec=IMarketDataRepository)\n"
    )

    found = mocked_ports(source)

    assert [entry.name for entry in found] == ["IMarketDataRepository"]
    assert found[0].owning_module() == "market_data"


def test_the_reader_ignores_an_engine_interface() -> None:
    """`IConfig` is a kernel service with no owning module and no fake to
    prefer — 17 tests mock it today and all of them are correct to."""
    source = (
        "from unittest.mock import Mock\n"
        "from sagittarius_engine.interfaces.i_config import IConfig\n"
        "config = Mock(spec=IConfig)\n"
    )

    assert mocked_ports(source)[0].owning_module() is None


def test_the_reader_ignores_a_core_port() -> None:
    """`core/` is owned by nobody, so there is no module to ship its fake."""
    source = (
        "from unittest.mock import Mock\n"
        "from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher "
        "import ICommandDispatcher\n"
        "dispatcher = Mock(spec=ICommandDispatcher)\n"
    )

    assert mocked_ports(source)[0].owning_module() is None


def test_the_reader_ignores_a_modules_non_contract_class() -> None:
    """Reaching past `contracts/` is the boundary guard's job, not this one's —
    two guards reporting one import twice makes both noisier."""
    source = (
        "from unittest.mock import Mock\n"
        "from Sagittarius_Elite_Warrior.src.modules.market_data.adapters."
        "persistence.database_manager import DatabaseManager\n"
        "manager = Mock(spec=DatabaseManager)\n"
    )

    assert mocked_ports(source)[0].owning_module() is None


def test_the_reader_sees_every_mock_factory() -> None:
    """`MagicMock` and `create_autospec` substitute a port just as thoroughly as
    `Mock`; a guard that only knew one spelling would be trivial to walk past."""
    source = (
        "from unittest.mock import MagicMock, Mock, create_autospec\n"
        "from Sagittarius_Elite_Warrior.src.modules.market_data.contracts."
        "i_live_stream_service import ILiveStreamService\n"
        "a = Mock(spec=ILiveStreamService)\n"
        "b = MagicMock(spec=ILiveStreamService)\n"
        "c = create_autospec(spec=ILiveStreamService)\n"
    )

    found = mocked_ports(source)

    assert len(found) == 3
    assert {entry.owning_module() for entry in found} == {"market_data"}


def test_a_module_may_mock_its_own_port() -> None:
    """The permission rule 4 grants explicitly, resolved from the test's path."""
    own = _TESTS_ROOT / "unit" / "modules" / "market_data" / "test_x.py"
    foreign = _TESTS_ROOT / "unit" / "modules" / "backtesting" / "test_y.py"
    outside = _TESTS_ROOT / "unit" / "presentation" / "test_z.py"

    assert _owning_module_of_test(own) == "market_data"
    assert _owning_module_of_test(foreign) == "backtesting"
    assert _owning_module_of_test(outside) is None
