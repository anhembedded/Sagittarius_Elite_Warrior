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
Narrowed, not closed. Established (2026-10-07, `EPIC-034` PR-1):
- **The painter is Qt's Fusion style, not this repository.** Drawing `QStyle.PE_IndicatorButtonDropDown` with Fusion into a `QPainter` over a rect with zero width or zero height prints exactly the owner's signature: one `QPainter::begin: Paint device returned engine == 0, type: 2` and eleven "Painter not active" lines, three of them `drawRoundedRect`, twelve messages in all. Fusion paints that primitive into a cache pixmap sized from the rect; a zero dimension makes a null pixmap (type 2, `QInternal::Pixmap`). Reproduced offscreen with a ten-line script over `QApplication.style().drawPrimitive`; no other primitive does it. `drawRoundedRect` appears nowhere in `src/`, `pyqtgraph` or `sagittarius_engine`, which is why a search of the app found nothing.
- **So the owner is a `QToolButton` with a drop-down (`MenuButtonPopup`) that is painted at zero size.** Fusion draws that part only for such a button. `src/` creates no tool button with a menu (`QToolButton` is used twice, in the Trade mode's order form); the candidates are a button Qt makes for a `QToolBar` action, such as the `ChartToolbar`'s, or an engine toolbar.

Not established: which button, and why it has no size while a bot with 0 candles is selected.
- Not reproduced with the real window: the real composition root (`booted_app` and `MainWindow` with every mode built, a created Grid bot selected, 0 candles), on `offscreen` and on `xcb` under Xvfb at `QT_SCALE_FACTOR=2`, with Fusion, prints no such message. The owner's session was Wayland at devicePixelRatio 2 on a 1440×900 screen; whatever differs there is not available here.
- `ChartToolbar` alone, resized from 0 to 900 px wide, prints none either.

## Fix
Not done: a fix before the owner is known would guess. `EPIC-034A`'s empty-chart sentence now replaces the plot of a chart with no candles; whether it removes this is for the owner's machine to say.

## Regression test
Not written. A test of Fusion itself would prove nothing about this app, and the app's own path is not reproduced.

## Verification
Not run on the owner's machine.

## Suggested next steps
- On the owner's Wayland machine, with a bot selected, run the app with a message handler that lists every visible `QToolButton` whose popup mode is `MenuButtonPopup` and whose width or height is 0 (its `objectName`, `parent().objectName()`, `text()`); the first hit is the owner.
- Then give that button a size or hide it while it has none, at the mechanism that lays it out, with a test that renders it under Fusion with `diagnostic_guard`'s Qt-message check.
- Check whether the empty-chart sentence (`EPIC-034A`) already removes it, and record that here.
