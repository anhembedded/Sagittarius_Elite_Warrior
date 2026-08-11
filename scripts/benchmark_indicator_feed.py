"""
BOT-036 — benchmarks IndicatorScriptRunner.feed_all() through real Qt
machinery (see `benchmarking/qt_feed_harness.py` for why this replaces the
earlier ad-hoc script that simulated Qt's cost with a hand-rolled list copy).

Run from the Sagittarius_ForkBoy repo root:
    PYTHONPATH=. ./.venv/Scripts/python.exe Sagittarius_Elite_Warrior/scripts/benchmark_indicator_feed.py

To compare before/after a change to feed_all()'s emit strategy, run this
same script at two commits (`git stash` / `git checkout`) rather than
hardcoding two code paths side by side in one file — that way the benchmark
keeps working as a regression check for whatever feed_all() looks like in
the future, instead of going stale the moment its own "old" branch is
deleted.
"""

from __future__ import annotations

import argparse
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication

from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts import (
    Ema20Script,
    Ema50Script,
    Ema100Script,
    Ema200Script,
)
from Sagittarius_Elite_Warrior.scripts.benchmarking.candle_factory import make_mock_candles
from Sagittarius_Elite_Warrior.scripts.benchmarking.qt_feed_harness import (
    run_background_path,
    run_main_thread_path,
)
from Sagittarius_Elite_Warrior.scripts.benchmarking.report import format_result

_DEFAULT_SCRIPT_KEYS = ["ema_20", "ema_50", "ema_100", "ema_200"]


def _build_registry() -> IndicatorScriptRegistry:
    registry = IndicatorScriptRegistry()
    registry.register("ema_20", Ema20Script)
    registry.register("ema_50", Ema50Script)
    registry.register("ema_100", Ema100Script)
    registry.register("ema_200", Ema200Script)
    return registry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candles", type=int, default=10_000)
    parser.add_argument(
        "--scripts",
        nargs="+",
        default=_DEFAULT_SCRIPT_KEYS,
        help="Registered script keys to enable (default: the 4 EMAs, matching "
        "the Dev Board's own defaults).",
    )
    args = parser.parse_args()

    app = QCoreApplication.instance() or QCoreApplication([])
    registry = _build_registry()
    candles = make_mock_candles(args.candles)

    print(f"--- {args.candles:,} candles, scripts={args.scripts} ---\n")

    bg_result = run_background_path(app, registry, args.scripts, candles)
    print(format_result(bg_result))
    print()

    main_result = run_main_thread_path(registry, args.scripts, candles)
    print(format_result(main_result))


if __name__ == "__main__":
    main()
