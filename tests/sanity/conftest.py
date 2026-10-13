"""
Sanity tier fixtures — the whole fixture surface for this tier, in one place.

Replaces the six near-copies of a boot fixture that used to live one per test
module. Those copies had already drifted: one loaded a different config set and
was the only sanity test that never patched the network boundary, and one used
module scope while the rest used function scope. There is now exactly one
definition to keep correct.

Session scope is not a micro-optimisation. The previous arrangement booted the
real application roughly 24 times to produce 38 assertions, which is why the
tier had to run sequentially in a job of its own. A tier that is expensive gets
excluded from CI, and an excluded tier proves nothing at any price — see
BOT-038 for the version of that lesson this repository has already paid for.

See `Tasks/epics/EPIC-009_sanity_tier_redesign/` for the model these fixtures
serve. Nothing here is verified: it was authored in an environment with neither
PySide6 nor `sagittarius_engine` installed. The first real run is the test.
"""

from __future__ import annotations

import logging
import os
import warnings
from pathlib import Path

import pytest
from binance_fake_server import run_binance_fake_server
from fake_exchange.binance_endpoints import binance_clients_pointed_at
from fake_exchange.stream_transport import fake_websocket_transport
from Sagittarius_Elite_Warrior.tests.unit import network_block

# Must precede any Qt import. `offscreen` is the one accepted realism gap in
# this tier, and it is precisely why the Desktop E2E tier exists.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_DIR = _REPO_ROOT / "src" / "config"

#: Qt messages tolerated during boot, construct and shutdown. Every entry needs
#: a written reason and a bug reference. An empty list is the correct starting
#: state: when this list wants to grow, the tier is reporting something true and
#: the answer is a bug report, not another entry.
_ALLOWED_QT_MESSAGES: list[str] = [
    # PySide6 6.11+ on Windows offscreen: PySide6 wheel no longer ships bundled fonts
    "QFontDatabase: Cannot find font directory",
]

#: Same contract for Python log records at WARNING or above.
_ALLOWED_LOG_MESSAGES: list[str] = []

#: Same contract for `warnings.warn(...)`. Sourced to the exact line:
#: `python-binance`'s `helpers.py:96` calls `asyncio.get_event_loop()`
#: unconditionally inside `Client.__init__` — every one of this tier's 17 use
#: cases that resolves a `PythonBinanceClient` triggers it, verified by
#: isolating a plain `Client()` construction with no app code involved. This
#: is `python-binance`'s own known-deprecated pattern (`asyncio.get_event_
#: loop()` outside a running loop, deprecated since Python 3.10), already
#: allowlisted the same way in `pyproject.toml`'s `filterwarnings` for the
#: rest of the suite — not a defect this tier's own code introduced.
#:
#: `BUG-075` — the same `get_loop()` helper falls back to
#: `asyncio.new_event_loop()` and never closes it when no loop already
#: exists on the current thread. `asyncio.BaseEventLoop.__del__` warns
#: `ResourceWarning: unclosed event loop` whenever the garbage collector
#: eventually reclaims that orphaned loop — not deterministic to any one
#: test, only to whichever one happens to be running when collection fires
#: (reproduced twice in CI, caught on `test_circular_imports.py`, which does
#: nothing but `ast.parse()` a file — an innocent bystander, same pattern
#: `BUG-030` already root-caused for an unrelated leaked resource).
_ALLOWED_WARNING_SUBSTRINGS: tuple[str, ...] = (
    "There is no current event loop",
    "unclosed event loop",
)


@pytest.fixture(scope="session")
def qapp():
    """Overrides the root `qapp` fixture, which SKIPS when PySide6 is missing.

    A skip is wrong for this tier. Sanity exists to prove composition health, so
    an environment that cannot construct a QApplication is a failing result, not
    an absent one — otherwise the whole UI half of the tier disappears silently
    and the run still exits 0.
    """
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture(scope="session")
def refused_destinations():
    """Every non-loopback destination the process tried to reach, for the session.

    The block is installed for the whole session, not per test, because the
    booted application keeps worker threads alive across tests: a chart opened
    in one test syncs after the next has begun. A per-test patch would let those
    requests through between tests.
    """
    patcher = pytest.MonkeyPatch()
    refused = network_block.install(patcher)
    yield refused
    patcher.undo()


@pytest.fixture(scope="session")
def fake_exchange(refused_destinations):
    """The one Binance-protocol server of the tier (`binance_fake_server.py`)."""
    with run_binance_fake_server() as fake_urls:
        yield fake_urls


@pytest.fixture(scope="session")
def stream_transport(refused_destinations):
    """The websocket half of the fake exchange (`stream_transport.py`)."""
    with fake_websocket_transport() as transport:
        yield transport


@pytest.fixture(autouse=True)
def reaches_no_real_host(refused_destinations):
    """A sanity test fails when the process tried to leave the machine.

    Cumulative on purpose: a request refused on a worker thread is recorded when
    it is made, so whichever test is running next sees it, however late the
    thread was.
    """
    yield
    assert not refused_destinations, (
        f"the process tried to reach {sorted(set(refused_destinations))}; the sanity "
        "tier points every Binance client at the fake exchange (conftest.py)"
    )


@pytest.fixture(scope="session")
def booted_app(qapp, tmp_path_factory, fake_exchange, stream_transport):
    """The real composition root, booted once, exactly as production loads it.

    Mirrors `app_bootstrapper.main()`'s configuration step (`app_config.json`,
    then `user_config.json` with `writable=True`) rather than inventing a
    test-only config set. No test in this tier triggers a config save, so the
    writable flag is faithful without being dangerous.

    Only the network boundary is substituted, and D6 draws that boundary at
    the transport, not at the application's own code. The REST side points
    every endpoint of the real `python-binance` clients — `Client` and the
    `AsyncClient` behind the websocket service, Spot and Futures, mainnet and
    both testnets — at `binance_fake_server.py`, a local server speaking
    Binance's protocol (`binance_endpoints.py`). The websocket side keeps the
    library's own socket manager and replaces only the two methods that touch a
    socket (`stream_transport.py`). `PythonBinanceClient`, its kline mapping,
    its pagination and all of `python-binance`'s own HTTP behaviour run
    unchanged. No hand-written substitute for `IExchangeClient` exists to fall
    behind its port, which is the class `BUG-026` and `BUG-027` came from.
    `BUG-045` — the DI graph reaching `api.binance.com` merely by being
    resolved, since `Client()` pings on construction by default — is closed
    by this.

    `BUG-199`: a boundary that moves one endpoint is a leak for every other, so
    two things hold it shut. The redirect covers every URL the library declares,
    and enters before the application is composed. And `refused_destinations`
    blocks and records every non-loopback connection for the whole session, so
    a path that still gets out fails the test running at the time, by host name.
    """
    from Sagittarius_Elite_Warrior.src.shell.gui_wiring import create_gui_app
    from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

    config_manager = ConfigManager()
    config_manager.load_json(str(_CONFIG_DIR / "app_config.json"))
    config_manager.load_json(str(_CONFIG_DIR / "user_config.json"), writable=True)
    # `EPIC-029B` (PR #318 review): the bots store is the one piece of state
    # this boot *writes* — the restore turns RUNNING bots into RECOVERING — so
    # it points at a fresh directory, never the developer's `state/bots/`.
    # A configuration value, like the network boundary below.
    config_manager.load_dict(
        {"bots.state_dir": str(tmp_path_factory.mktemp("bots_state"))}
    )

    # Class attributes on a third-party class, not instance patches: every
    # client built anywhere in the app for the rest of this fixture's scope
    # picks them up, and the block restores the library's own on exit so no
    # other test module is left thinking real network access is disabled
    # process-wide.
    with binance_clients_pointed_at(fake_exchange):
        # `EPIC-038A` — the graph the GUI entry point boots (`create_app` plus the
        # GUI's additions): this tier proves the application the GUI runs, and its
        # window tests need them. The shared composition alone is booted, with
        # PySide6 blocked, by `test_the_app_boots_without_pyside6.py`.
        app = create_gui_app(config_manager)
        app.boot()
        yield app
        app.stop()


@pytest.fixture(autouse=True)
def diagnostic_guard(request):
    """Fails any sanity test that provokes a complaint on any channel.

    This is the tier's most valuable assertion, and it is the one the old tier
    had no form of. Sanity is the only place where every diagnostic surface of
    the real application is open at once, and the app writes to more than one:

      - Qt's own handler   -> `QBasicTimer::start: Timers cannot be started from
                              another thread` (BUG-031, P1)
                              `qt.qml: Unable to assign [undefined] to double`
                              (BUG-028)
      - Python `logging`   -> the only channel `Invoke-RunLogScan` inspects
      - `warnings`         -> unawaited coroutines, unclosed resources

    Both Qt defects above were audible for their entire lifetime and reached
    users anyway, because the CI log scan greps for `- WARNING -`, which is
    Python's logging format and not the one Qt uses.

    Expect this to go red on its first run. Every message it surfaces is either
    a real defect, which then follows `fix-bug-rule.md` in full, or an
    explicitly justified entry in the allowlists above. It is not evidence that
    the guard is broken.
    """
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler

    problems: list[str] = []
    problem_levels = {
        QtMsgType.QtWarningMsg,
        QtMsgType.QtCriticalMsg,
        QtMsgType.QtFatalMsg,
    }

    def _qt_handler(mode, context, message: str) -> None:
        if mode in problem_levels and not any(
            allowed in message for allowed in _ALLOWED_QT_MESSAGES
        ):
            problems.append(f"[qt/{mode.name}] {message}")

    class _LogTrap(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            text = record.getMessage()
            if not any(allowed in text for allowed in _ALLOWED_LOG_MESSAGES):
                problems.append(f"[log/{record.levelname}] {record.name}: {text}")

    previous_handler = qInstallMessageHandler(_qt_handler)
    trap = _LogTrap(level=logging.WARNING)
    root_logger = logging.getLogger()
    root_logger.addHandler(trap)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        yield problems

    root_logger.removeHandler(trap)
    qInstallMessageHandler(previous_handler)
    problems.extend(
        f"[warning] {w.category.__name__}: {w.message}"
        for w in caught
        if not any(allowed in str(w.message) for allowed in _ALLOWED_WARNING_SUBSTRINGS)
    )

    assert problems == [], (
        f"{request.node.name} provoked {len(problems)} diagnostic(s) on channels "
        f"the application writes to during boot/construct/shutdown:\n  "
        + "\n  ".join(problems)
    )
