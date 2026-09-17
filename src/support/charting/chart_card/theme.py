"""Shared color constants for the chart_card package — single source of truth so
candlestick, volume, price-line and crosshair rendering stay visually consistent.

This module used to say the package "doesn't import the app's global Palette
(kept portable/standalone), so the value is duplicated here rather than
imported". That stopped being true before anyone noticed: `indicator_manager`
imports `src.domain.indicator_scripts`, so the package already depends on the
app it was supposed to be portable from. EPIC-007D settled it in the direction
the code had already gone — chrome reads `Palette`, and the duplication is
gone.

What stays a literal here is what is genuinely not chrome: a candle body is
green because it closed up, not because the theme says so. Those two carry
`token-exempt` with that reason. If this package is ever made portable for
real, the import above is the thing to remove, and these two are already in
the right shape.

`EPIC-025` PR 4.3m: imports `Palette` from `ui_kit/palette.py` rather than
the `assets` package, whose `__init__` also imports `icon_loader` —
Qt-backed, unlike `Palette`'s plain hex strings. `assets/__init__.py`
importing anything runs its own top, so reaching `Palette` through
`assets.palette` would still have paid for `icon_loader`'s `PySide6`
import; only a module outside that package avoids it.
`StrategyChartOverlayService` now reaches this file from the application
layer, wired eagerly in `strategy`'s composition root, and that Qt import
would have landed on every run, headless included
(`tests/unit/architecture/test_module_contribution_laziness.py`)."""

from Sagittarius_Elite_Warrior.src.support.ui_kit.palette import Palette

BULL_COLOR = "#26a69a"  # token-exempt: candle/indicator series colour, not chrome
BEAR_COLOR = "#ef5350"  # token-exempt: candle/indicator series colour, not chrome
CROSSHAIR_COLOR = Palette.MUTED
#: BOT-111 — take-profit exit markers get their own color, distinct from the
#: plain bull/bear entry/exit scheme, so a broker-level TP fill reads
#: differently from a strategy-decided exit at a glance. The domain name is
#: kept even though the value is just the accent token: what a reader needs
#: here is "this is the TP colour", not "this is gold".
TAKE_PROFIT_COLOR = Palette.ACCENT
