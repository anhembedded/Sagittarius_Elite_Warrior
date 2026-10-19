# EPIC-033U — The Bots tab colours profit, loss and state from the one meaning table, readable in light, dark and High Contrast

**Status:** ✅ Done (2026-10-19)
**Source:** The owner, 2026-10-19: *"làm task theme UI"* ("do a UI theme task"). The owner's rule defers visual design (D1) and takes dark mode from the OS only (D8), so this is the part of a theme that stays inside the rule; the coordinator pointed the work at EPIC-033 and its D8 row, which still read "Not started / Not yet verified".
**Risk:** 🟢 — display only, behind `ForegroundRole`; no state, command or trading code.
**Complexity:** M — one palette-aware lookup, three table mappings, a High Contrast probe, tests on three schemes.
**Epic (optional):** [EPIC-033](../README.md)
**Depends on:** EPIC-033K, EPIC-033M (done)

---

## 1. Context and problem
Checked at `f83e5a21`. The Bots tab coloured nothing: `Grid profit` and `Total PnL` printed as plain numbers, a state as a word (bold for `HALTED`, `AWAITING_RECOVERY`, `ERROR`), the connection as a label. The app's meaning table (`support/ui_kit/meaning_colours.py`) existed and only backtesting used it; its profit colour (`#26a69a`) is 3.0:1 on a white base and its loss colour 3.5:1, below the 4.5:1 text needs, and a fixed colour on a cell ignores Windows High Contrast, which `ui-presentation-rule.md` §1 requires to stay usable. D8's tracking row had never been updated after EPIC-033M.

## 2. Acceptance criteria
- [x] `tone_colour(tone, palette)` returns a named colour at least 4.5:1 against the palette's `Base` for POSITIVE, NEGATIVE and CAUTION on a light and on a dark base; NEUTRAL returns none.
- [x] With Windows High Contrast on, it returns none for every tone.
- [x] The Bots table colours `Grid profit` and `Total PnL` by sign (zero and unknown none), the `State` column by state (RUNNING positive; PAUSED, RECOVERING, AWAITING_RECOVERY caution; HALTED, ERROR negative), and the ladder's `Per cycle, after fees` column by sign; every cell's text is unchanged, so the word or the minus sign stays beside the colour; the attention states stay bold.
- [x] `tone_colour(tone)` without a palette is unchanged (backtesting).
- [x] No hex literal, style sheet or palette override is added; `tests/unit/architecture` passes (970 tests).
- [x] The preview shows winning and losing bots; D8's tracking row states what is and is not verified.

## 3. Design
`Tone` gains `CAUTION`. With a palette the lookup picks, by the lightness of `QPalette.Base`, a named colour: `darkgreen`, `firebrick`, `saddlebrown` on a light base; `lightgreen`, `lightcoral`, `darkorange` on a dark one (computed 6.7 to 11.8:1 in their own scheme). Named colours are not hex, so `test_stock_controls_only.py` is untouched. The model asks `QGuiApplication.palette()` inside `data()`, so a change of the OS scheme is followed at the next repaint with no signal. `is_high_contrast()` is Qt's own hint, `QGuiApplication.styleHints().accessibility().contrastPreference() == Qt.ContrastPreference.HighContrast` (Qt 6.10 and later; Windows High Contrast and macOS Increase contrast): Qt caches it, so asking it for every coloured cell of a repaint costs nothing (the independent review corrected an earlier hand-written `ctypes` call). Pattern: the `ForegroundRole` of `metrics_detail_model.py`; `CONSTITUTION.md` P5, the existing table is extended, not replaced.

## 3a. Reuse
`Tone`, `tone_colour`, `RowTableModel._role_data`, the backtest's `ForegroundRole` pattern (`capabilities.md`, "Colour something by meaning").

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/ui_kit/meaning_colours.py` | `Tone.CAUTION`, palette-aware `tone_colour`, `is_high_contrast` |
| `src/modules/bots/ui/bots_screen/bots_table_models.py` | `state_tone`, `sign_tone`, `ForegroundRole` for the bots and ladder tables |
| `src/modules/bots/ui/bots_screen/preview.py` | winning and losing sample bots |
| `tests/unit/support/ui_kit/test_meaning_colours.py`, `tests/unit/modules/bots/ui/bots_screen/test_bots_tables_colour_by_meaning.py` | the cases of section 5 |

## 5. Testing
Unit tier. Contrast of each tone on white, `#f3f3f3`, `#1e1e1e` and black is at least 4.5:1, computed in the test; the three tones differ on each base; High Contrast (a replaced probe) gives none; the Bots table gives the tone's colour for a winning, losing and zero bot on a light and a dark base, and the display text is unchanged; mutation checked (HALTED mapped to POSITIVE fails two tests). `tests/unit/architecture`: 970 passed. Not run: a real Windows High Contrast session and a selected row on the Windows styles.

## 6. Docs touched
`Tasks/epics/EPIC-033_windows_workbench/` README, TRACKING and the decision's evidence table (D8). `Docs/MODULES/bots/`: none, because those files do not describe table colours.

## Implementation notes (written when done)
Backtesting still calls `tone_colour(tone)` without a palette at four sites (`metrics_detail_model.py`, `metric_comparison_model.py`, `backtest_stat_row.py`, `metrics_detail_dialog.py`), so its profit colour stays 3.0:1 on white: [BOT-196](../../../backlog/BOT-196_backtest_tones_use_the_palette_aware_meaning_table.md) passes the palette there. A selected row: the item delegate writes the tone into the palette's `Text` role only; the highlighted text role stays the platform's (measured with `QStyledItemDelegate.initStyleOption`: `Text` darkgreen, `HighlightedText` white), so common-style selected text is unchanged; the Windows 11 style was not looked at. Deferred by D1 and D8 and not built: a designed theme, brand colours, an icon set, colour in labels (the connection strip and the detail panel keep their words), a user-chosen scheme, an explicit `+` on a profit. The full gate is the PR's `ci-local.ps1 -Full` run.
