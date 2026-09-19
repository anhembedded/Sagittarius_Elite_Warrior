"""Desktop E2E acceptance evidence for `EPIC-025` Phase 0.

Why this exists
---------------
`EPIC-025A` §2 ends Phase 0 with *"the app runs exactly as before"*, and the
epic README §3 ends **every** phase with *the app running*. Neither is a green
gate: the sanity tier proves the app comes into existence and that every
navigable route constructs through the real container, but "constructs" is not
"paints", and the three screens Phase 0 touched are exactly the ones no test
watches on a real display:

- **Data Management** — PR 0.4b-1 rebuilt it from QML into a `QTableView`
  panel with four `QAction`s and a kline-inspector `QDialog`. Its `.qml` files
  are deleted, so a paint failure has nowhere to fall back to.
- **Trading** and **Dev Board** — PR 0.5 moved their sync onto
  `IMarketDataSync`, which is resolved from the real container inside each
  Presenter's constructor. A missing binding raises at construction, and the
  sanity tier catches that; what it cannot catch is a screen that constructs
  and then renders nothing.

This follows `ci-rule.md` §3's Desktop E2E convention and
`python_backtest_pan_desktop_e2e.py`'s shape: opt-in, refuses to run headless,
non-zero exit on a real failure. It is **supplementary** to the user's own
Testnet run, never a substitute — it never places an order, never enables
trading, and never opens a websocket, so it says nothing about behaviour that
needs a live exchange.

Run on a machine with a real display, or on Linux without one:

    PYTHONPATH=.. QT_QPA_PLATFORM=xcb xvfb-run -a -s "-screen 0 1600x1000x24" \\
        .venv/bin/python scripts/epic025_phase0_acceptance_probe.py

Exit 0: every screen under test opened and painted a non-blank window.
Exit 1: one did not — the report names which, and the screenshots are kept.
Exit 2: refused — no real display.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

if os.environ.get("QT_QPA_PLATFORM") in {"offscreen", "minimal"}:
    sys.stderr.write(
        "Phase 0 acceptance needs a real windowing session: under "
        f"{os.environ['QT_QPA_PLATFORM']!r} Qt takes the software path, and a "
        "screen that fails to paint on a compositor can still grab clean "
        "(ci-rule.md §3).\n"
    )
    raise SystemExit(2)

_SUPERPROJECT = Path(__file__).resolve().parent.parent.parent
if str(_SUPERPROJECT) not in sys.path:
    sys.path.insert(0, str(_SUPERPROJECT))

# The sanity tier's own fake-exchange server, reused rather than reinvented:
# `BUG-045` is that resolving the DI graph reaches `api.binance.com` at all,
# because `python-binance`'s `Client()` pings on construction. Pointing its
# `API_URL` at a local server speaking Binance's protocol is the substitution
# the sanity tier already settled on (ADR D6 draws the line at the transport,
# not at the app's own code), so this probe needs no network and no
# credentials.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests" / "sanity"))

# `binance_fake_server` carries a `type: ignore` with its reason, not a bare
# suppression and not a new entry in `[tool.mypy] exclude` — that list is
# frozen 2026-08-21 debt and says so: a new file that fails must be fixed.
# There is nothing to fix in the types. The module lives in `tests/sanity/`,
# which is not on `MYPYPATH` (the gate checks `src` and `scripts`), and it is
# reached through the `sys.path` insert above because that is how the sanity
# tier itself imports it — its own docstring fixes that name and signature for
# exactly this reason. Statically unresolvable, deliberately.
from unittest.mock import patch

from binance.client import Client
from binance_fake_server import (  # type: ignore[import-not-found]
    run_binance_fake_server,
)
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import (
    MainWindow,
)
from Sagittarius_Elite_Warrior.src.shell.app_config import (
    load_app_config,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import (
    create_app,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.sidebar import (
    Sidebar,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.theme_bootstrap import (
    seed_app_theme,
)
from Sagittarius_Elite_Warrior.tests.conftest import (
    real_screen_registry,
)

#: The routes Phase 0 touched. `dashboard` is Dev Board; it is included even
#: though `dev.mode` gates it, because the probe boots with `--dev`.
_ROUTES = ("trading", "dashboard", "data_management")

#: Where the evidence lands. Kept on failure *and* success: a screenshot of a
#: screen that painted is the only artefact this probe produces that a human
#: can check against their own memory of "as before".
_SHOTS = Path(__file__).resolve().parent.parent / "logs" / "phase0_acceptance"

#: A window that paints one flat colour has "painted" by any pixel test and
#: shows the user nothing. Requiring several distinct colours is the cheapest
#: check that something was actually laid out — a table, a toolbar, text.
_MIN_DISTINCT_COLOURS = 12

#: Milliseconds to let Qt lay out, style and paint before grabbing. Generous:
#: this asserts "it painted", not "it painted quickly", and a probe that
#: flakes on a slow runner teaches nobody anything.
_SETTLE_MS = 1500


def _settle(ms: int) -> None:
    """Run the event loop for `ms` — layout, styling and paint all need it.

    `QTest.qWait` would do, but it pulls in `QtTest` for one call; a timer and
    a local event loop is the same thing with one less import and is what the
    Qt documentation itself shows for waiting outside a test harness.
    """
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _distinct_colours(widget) -> int:
    image = widget.grab().toImage()
    if image.isNull() or image.width() == 0:
        return 0
    step = max(1, min(image.width(), image.height()) // 40)
    seen = {
        image.pixel(x, y)
        for x in range(0, image.width(), step)
        for y in range(0, image.height(), step)
    }
    return len(seen)


def main() -> int:
    # `--dev` so Dev Board is registered at all: the surface and every
    # `dev_probe` are gated on `dev.mode`, and a probe that silently skipped
    # the screen it means to check would report success for two of three.
    config_manager, _dev_mode = load_app_config([sys.argv[0], "--dev"])
    app_qt = QApplication.instance() or QApplication(sys.argv)
    # What `app_bootstrapper.py` does before building any widget, and the step
    # this probe was missing on its first run: `apply_role()` reads a
    # first-caller-wins theme-bridge singleton, so a window built before the
    # palette is seeded dies in `_build_qss` rather than painting. The failure
    # was the probe's, not the app's — worth the comment, because a probe that
    # skips a bootstrap step reports a defect that is not there.
    seed_app_theme()
    app = create_app(config_manager)

    _SHOTS.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    real_api_url = Client.API_URL

    # The websocket side has no fake server (a real websocket protocol is a
    # materially larger undertaking than a REST handler), so it stays patched
    # at its two entry points — same boundary, same reason, as the sanity
    # tier's fixture. Opening a screen never starts a stream anyway; this only
    # guarantees that a screen which *would* cannot reach the internet.
    with (
        run_binance_fake_server() as fake_urls,
        patch(
            "Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance."
            "binance_websocket_service.AsyncClient"
        ),
        patch(
            "Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance."
            "binance_websocket_service.BinanceSocketManager"
        ),
    ):
        Client.API_URL = fake_urls.spot
        window = None
        try:
            app.boot()
            registry = real_screen_registry(app.context.container)
            window = MainWindow(app, registry, sidebar_factory=Sidebar)
            window.resize(1560, 960)
            window.show()
            _settle(_SETTLE_MS)

            for route in _ROUTES:
                window.switch_screen(route)
                _settle(_SETTLE_MS)
                if window._stacked.currentWidget() is None:
                    failures.append(
                        f"{route}: navigated but left no widget on the stack"
                    )
                    continue
                colours = _distinct_colours(window)
                shot = _SHOTS / f"{route}.png"
                window.grab().save(str(shot))
                verdict = "ok" if colours >= _MIN_DISTINCT_COLOURS else "BLANK"
                print(f"  {route:<18} {colours:>4} distinct colours  {verdict}  {shot}")
                if colours < _MIN_DISTINCT_COLOURS:
                    failures.append(
                        f"{route}: only {colours} distinct colours — the screen "
                        f"constructed but did not paint anything a user could read"
                    )
        finally:
            if window is not None:
                window.shutdown()
            app.stop()
            app_qt.processEvents()
            Client.API_URL = real_api_url

    if failures:
        sys.stderr.write("\nPhase 0 acceptance FAILED:\n")
        for line in failures:
            sys.stderr.write(f"  - {line}\n")
        return 1

    print(
        f"\nPhase 0 acceptance: {len(_ROUTES)} screens opened and painted. "
        f"Screenshots in {_SHOTS}.\n"
        "This is supplementary evidence — placing an order, enabling trading "
        "and a live stream still need the user's Testnet run."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
