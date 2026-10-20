"""`EPIC-040E` — the Bots screen's centre in each state worth looking at, for the owner's check
(`ui-presentation-rule.md` §5).

Offline, like `preview.py`: the screen is the Spot preview's (a Grid bot selected, its chart and Plan),
and the Backtest tab holds the real workbench page over a scripted answer
(`ui/kinds/grid/backtest/workbench_frames.py`), so every sentence is the one a user reads.

  live_tab · backtest_tab_ready · backtest_tab_result · backtest_tab_off

Run one with `python -m Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.centre_tab_frames
<frame> [--png path]` (offscreen with `--png`, a window otherwise).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Mapping

from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    NO_BACKTEST_TEXT,
    BotsView,
    TabAvailability,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.preview import (
    build_preview,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.workbench_frames import (
    build_frame as build_workbench_frame,
)


def _screen() -> BotsView:
    view = build_preview()
    if not isinstance(view, BotsView):
        raise TypeError("the Spot preview is the Bots screen")
    return view


def _live() -> BotsView:
    return _screen()


def _backtest_tab(workbench: str) -> BotsView:
    view = _screen()
    view.set_backtest_page(build_workbench_frame(workbench), "")
    view.show_backtest()
    return view


def _backtest_off() -> BotsView:
    """A bot whose kind has no backtest: the tab stays, off, and says why."""
    view = _screen()
    view.set_backtest_page(None, NO_BACKTEST_TEXT)
    view.set_backtest_available(TabAvailability(False, NO_BACKTEST_TEXT))
    return view


FRAMES: Mapping[str, Callable[[], BotsView]] = {
    "live_tab": _live,
    "backtest_tab_ready": lambda: _backtest_tab("idle_ready"),
    "backtest_tab_result": lambda: _backtest_tab("spot_result"),
    "backtest_tab_off": _backtest_off,
}


def build_frame(name: str) -> BotsView:
    """@raise KeyError `name` is not one of `FRAMES`."""
    return FRAMES[name]()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frame", choices=sorted(FRAMES))
    parser.add_argument(
        "--png", metavar="PATH", help="Save the frame instead of showing it."
    )
    args = parser.parse_args()
    app = QApplication.instance() or QApplication(sys.argv)
    widget = build_frame(args.frame)
    widget.resize(1366, 800)
    if args.png:
        widget.grab().save(args.png)
        return
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
