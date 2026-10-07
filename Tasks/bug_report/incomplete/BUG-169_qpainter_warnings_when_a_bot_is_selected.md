# BUG-169 — Selecting a bot prints "QPainter::begin: Paint device returned engine == 0" and a burst of painter warnings

- **Reported:** 2026-10-07 (the owner, chat, in the log of selecting a Spot Grid bot)
- **Severity:** 🟢 P3 — no visible damage yet; something paints on a device that cannot be painted, and the sanity tier would fail on such a Qt message at boot
- **Status:** Open
- **Board:** Selecting a bot logs `QPainter::begin: Paint device returned engine == 0, type: 2` twice, each followed by eleven "Painter not active" warnings (`drawRoundedRect`).
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → `src/modules/bots/` → `ui/` (the painter is not yet identified)
- **Environment:** the owner's Linux desktop, Qt platform `wayland`, DPR 2, screen 1440×900; `master-warrior` after PR #409; the bot's chart had 0 candles.

## Reproduction
1. Start the app on a Wayland desktop and open the Bots mode.
2. Select a Spot Grid bot whose chart has no candles.
3. Expected: no Qt warnings.
4. Actual: the sequence below, twice, right before `[chart-data] ChartCard(BTCUSDT): loaded 0 candles`.

Not yet reproduced off the owner's machine; Xvfb or offscreen may not show it.

## Symptom
```
QPainter::begin: Paint device returned engine == 0, type: 2
QPainter::setRenderHint: Painter must be active to set rendering hints
QPainter::translate: Painter not active
QPainter::setPen / setBrush: Painter not active
QPainter::drawRoundedRect: Painter not active   (three times)
```
Paint device type 2 is `QInternal::Pixmap`. A pixmap that returns no engine is usually a null pixmap: zero width or height.

## Root cause
Not yet established. Known so far:
- No file in `src/` or in the installed `sagittarius_engine` calls `drawRoundedRect`, so the painter is in pyqtgraph or in a Qt style.
- It coincides with a chart that has 0 candles (initial view x-range [0, 1], y-range [0, 1]).
- The DPR is 2, so a pixmap sized from a zero-size item stays null.

## Fix
Not yet done.

## Regression test
Not yet written.

## Verification
Not run.

## Suggested next steps
- Reproduce with `QT_FATAL_WARNINGS=1` under a debugger, or install a Qt message handler that prints a Python stack, to find the caller.
- Check whether the chart's empty state (`EPIC-034A`) removes it. If it does, record that here rather than closing the report without a test.
