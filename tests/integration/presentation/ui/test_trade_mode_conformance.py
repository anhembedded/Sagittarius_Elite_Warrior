"""`EPIC-033I` — the Trade mode with both venues built passes every check of
the conformance suite, at each window size, with each venue shown; and each
is pictured for a reviewer (`pr-review` SKILL §5.1).

The conformance suite boots the app as configured, with no trading venue
enabled, so it measures the Trade mode's notice alone. Here the app runs
with Futures and Spot Testnet enabled against the fake Binance server
(`trade_mode_boot.py`), so both pages, their docks, toolbars and tables
exist. Known failures only shrink, as the suite's do: they are
`baseline_workbench_conformance.json`'s `failing_with_venues`, keyed
`trade~<venue>`, and ratcheted by the suite's own `ratchet_problems`.

Retire when: the conformance suite's own boot enables the venues.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_screen import (
    TRADE_ROUTE,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.test_workbench_conformance import (
    BASELINE_FILE,
    MODE_CHECKS,
    WINDOW_SIZES,
    ratchet_problems,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.trade_mode_boot import (
    FUTURES,
    SPOT,
    Boot,
    choose,
    trade_mode_running,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_layout_checks import (
    fit_problems,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_screenshots import (
    SCREENSHOT_DIR_ENV,
    is_blank,
)


def _baseline() -> dict[str, list[str]]:
    data = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    baseline: dict[str, list[str]] = data["failing_with_venues"]
    return baseline


@pytest.fixture
def trade_boot(request: pytest.FixtureRequest) -> Boot:
    return Boot.from_request(request)


def _settle() -> None:
    for _ in range(3):
        QApplication.processEvents()


@pytest.mark.parametrize(
    "size", [QSize(*s) for s in WINDOW_SIZES], ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_the_trade_mode_conforms_with_each_venue_shown(
    trade_boot: Boot, size: QSize, tmp_path: Path
) -> None:
    out_dir = Path(os.environ.get(SCREENSHOT_DIR_ENV) or tmp_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    label = f"{size.width()}x{size.height()}"
    report: dict[str, dict[str, list[str]]] = {}
    with trade_mode_running(trade_boot) as desk:
        window = desk.window
        window.resize(size)
        _settle()
        host = window.hosts[TRADE_ROUTE]
        for venue in (FUTURES, SPOT):
            choose(window, venue)
            _settle()
            # Pictured as the person sees it on choosing the venue, before
            # the checks rearrange and reset the layout.
            path = out_dir / f"{TRADE_ROUTE}~{venue.value}@{label}.png"
            assert window.grab().save(str(path)), path
            assert not QImage(str(path)).isNull()
            assert not is_blank(host.centralWidget().grab().toImage()), venue
            checks = {name: check(window, host) for name, check in MODE_CHECKS.items()}
            checks["fits_the_window"] = fit_problems(window, host, size)
            report[f"{TRADE_ROUTE}~{venue.value}"] = checks

    problems = ratchet_problems(_baseline(), report, size)
    assert not problems, "\n".join(problems)
