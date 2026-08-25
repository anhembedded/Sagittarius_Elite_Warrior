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

# Must precede any Qt import. `offscreen` is the one accepted realism gap in
# this tier, and it is precisely why the Desktop E2E tier exists.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_DIR = _REPO_ROOT / "src" / "config"

#: Qt messages tolerated during boot, construct and shutdown. Every entry needs
#: a written reason and a bug reference. An empty list is the correct starting
#: state: when this list wants to grow, the tier is reporting something true and
#: the answer is a bug report, not another entry.
_ALLOWED_QT_MESSAGES: list[str] = []

#: Same contract for Python log records at WARNING or above.
_ALLOWED_LOG_MESSAGES: list[str] = []

#: Same contract for `warnings.warn(...)`. One entry, sourced to the exact
#: line: `python-binance`'s `helpers.py:96` calls `asyncio.get_event_loop()`
#: unconditionally inside `Client.__init__` — every one of this tier's 17 use
#: cases that resolves a `PythonBinanceClient` triggers it, verified by
#: isolating a plain `Client()` construction with no app code involved. This
#: is `python-binance`'s own known-deprecated pattern (`asyncio.get_event_
#: loop()` outside a running loop, deprecated since Python 3.10), already
#: allowlisted the same way in `pyproject.toml`'s `filterwarnings` for the
#: rest of the suite — not a defect this tier's own code introduced.
_ALLOWED_WARNING_SUBSTRINGS: tuple[str, ...] = ("There is no current event loop",)


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
def booted_app(qapp):
    """The real composition root, booted once, exactly as production loads it.

    Mirrors `app_bootstrapper.main()`'s configuration step (`app_config.json`,
    then `user_config.json` with `writable=True`) rather than inventing a
    test-only config set. No test in this tier triggers a config save, so the
    writable flag is faithful without being dangerous.

    Only the network boundary is substituted, and D6 draws that boundary at
    the transport, not at the application's own code: the REST side points
    the real `python-binance` `Client` at `binance_fake_server.py` — a local
    server speaking Binance's protocol — by overriding its `API_URL` class
    attribute, a configuration value, not a code path. `PythonBinanceClient`,
    its kline mapping, its pagination, all of `python-binance`'s own HTTP
    behavior still run unchanged; only the endpoint moves. No hand-written
    substitute for `IExchangeClient` exists to fall behind its port, which is
    the class `BUG-026` and `BUG-027` came from. `BUG-045` — the DI graph
    reaching `api.binance.com` merely by being resolved, since `Client()`
    pings on construction by default — is closed by this alone.

    The websocket side is not yet covered by a fake server (a real websocket
    protocol is a materially larger undertaking than a REST GET handler); it
    stays mocked at its two entry points, `AsyncClient`/`BinanceSocketManager`,
    same as before.
    """
    from unittest.mock import patch

    from binance.client import Client
    from Sagittarius_Elite_Warrior.src.main import create_app
    from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

    from binance_fake_server import run_binance_fake_server

    config_manager = ConfigManager()
    config_manager.load_json(str(_CONFIG_DIR / "app_config.json"))
    config_manager.load_json(str(_CONFIG_DIR / "user_config.json"), writable=True)

    app = create_app(config_manager)

    real_client_api_url = Client.API_URL
    with (
        run_binance_fake_server() as fake_url,
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance."
            "binance_websocket_service.AsyncClient"
        ),
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance."
            "binance_websocket_service.BinanceSocketManager"
        ),
    ):
        # A class attribute on a third-party class, not an instance patch —
        # every `Client(...)` constructed anywhere in the app for the rest of
        # this fixture's scope picks it up, restored in `finally` so no other
        # test module (or a human reading `Client.API_URL` mid-session) is
        # left thinking real network access is disabled process-wide.
        Client.API_URL = fake_url
        try:
            app.boot()
            yield app
            app.stop()
        finally:
            Client.API_URL = real_client_api_url


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
    a real defect, which then follows `bug-fix-rule.md` in full, or an
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
