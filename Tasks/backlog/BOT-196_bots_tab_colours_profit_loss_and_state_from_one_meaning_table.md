# BOT-196 — The Bots tab colours profit, loss and state from the one meaning table, readable in light, dark and high contrast

**Status:** 🔵 Backlog
**Priority:** P3
**Board:** The Bots table colours `Grid profit`, `Total PnL`, the ladder's net columns and the `State` column from the app's meaning table, chosen by the table's light or dark base and left to the platform in high contrast; the word or minus sign stays in every cell ([PRO-018](proposal/PRO-018.md) Part A).
**Source:** The owner, 2026-10-19: *"làm task theme UI, với 1 task là tui muốn dùng rich cho VPS, đánh giá và làm nhé"* ("do a UI theme task, and one task where I want to use `rich` on the VPS"). Part A of PRO-018 only; the rule changes in its Part B are not built.
**Risk:** 🟢 — display only, behind `ForegroundRole`; no state, command or trading code.
**Complexity:** M — one lookup, three table mappings, a high-contrast probe, tests in three schemes.
**SPEC (optional):** none
**Depends on:** [PRO-018](proposal/PRO-018.md) merged.

---

## 1. Context and problem
`BotsTableModel` and `BotLadderTableModel` print money and state in the platform's text colour; only attention states are bold. The app's meaning table (`support/ui_kit/meaning_colours.py`) is used by backtesting alone, and its profit colour is 3.0:1 on a white base (PRO-018 §1), below the 4.5:1 a text colour needs.

## 2. Acceptance criteria
- [ ] `tone_colour(tone, palette)` returns a named colour whose contrast against the palette's `Base` is at least 4.5:1 for POSITIVE, NEGATIVE and CAUTION, for a light base and for a dark base; NEUTRAL returns `None`.
- [ ] When the high-contrast probe says Windows High Contrast is on, the lookup returns `None` for every tone.
- [ ] The Bots table colours `Grid profit` and `Total PnL` by the sign of the figure (zero and unknown stay uncoloured), the `State` column by state (RUNNING positive; PAUSED, RECOVERING, AWAITING_RECOVERY caution; HALTED, ERROR negative; the rest none), and the ladder's net columns by sign; the cell text is unchanged, so a word or a minus sign is always beside the colour; the attention states stay bold.
- [ ] `tone_colour(tone)` without a palette behaves as before (backtesting unchanged).
- [ ] No hex literal, style sheet, palette override or `apply_role` is added (the four architecture guards named in PRO-018 pass).
- [ ] `preview.py` shows a winning and a losing bot.

## 3. Design
`meaning_colours.py` keeps `Tone` and gains `Tone.CAUTION` and a lookup table keyed by tone and scheme, holding named colours only (`"darkgreen"`, `"lightgreen"`, `"firebrick"`, `"lightcoral"`, `"saddlebrown"`, `"darkorange"`). The scheme is the lightness of `QPalette.Base` in the palette passed; no signal is needed because a view reads `data()` on each repaint. High contrast comes from `HighContrastProbe` (Windows `SystemParametersInfoW(SPI_GETHIGHCONTRAST)` through `ctypes`, `False` elsewhere), a class the tests replace. A table maps a row to a `Tone` in a pure function and returns the colour from `_role_data` for `ForegroundRole`, the pattern of `metrics_detail_model.py`. Source: `ui-presentation-rule.md` §1 (meaning table, named colours, never alone, High Contrast), Microsoft `vis-color`, WCAG 2.x 1.4.3 (4.5:1). `CONSTITUTION.md` P5: the existing table is extended, not replaced.

## 3a. Reuse
`Tone`, `tone_colour`, `RowTableModel._role_data` and the `ForegroundRole` pattern of `metrics_detail_model.py` are used. `capabilities.md`: row "Colour something by meaning" is `meaning_colours.py`. Nothing else is needed.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/ui_kit/meaning_colours.py` | `Tone.CAUTION`, palette-aware lookup, `HighContrastProbe` |
| `src/modules/bots/ui/bots_screen/bots_table_models.py` | `ForegroundRole` for the money, state and ladder-net columns |
| `src/modules/bots/ui/bots_screen/preview.py` | a winning and a losing sample bot |
| `tests/unit/support/ui_kit/test_meaning_colours.py` and `tests/unit/modules/bots/ui/bots_screen/` | tests of section 5 |

## 5. Testing
Unit tier, offscreen Qt. Contrast: for each tone and each scheme, the returned colour against `Base` is at least 4.5:1 (computed in the test from the colour's RGB, no literal in `src/`). Schemes are built from `QPalette` objects with a white and a `#1e1e1e` base created in the test. High contrast: a fake probe returns `True` and every tone gives `None`. Table: a model with a winning, a losing, a zero and an unknown bot returns the expected `ForegroundRole` and the same `DisplayRole` text as before. Guards: `tests/unit/architecture` (stock controls, styling, global stylesheet, conformance). Not run: a real Windows High Contrast session (PRO-018 unknowns).

## 6. Docs touched
`Docs/MODULES/bots/`: the UI file that lists the table's columns, if one names colour (checked at build time), else `No design change` in the PR. `.claude/rules/capabilities.md` row for the meaning table if it lists its API.

## Implementation notes (written when done)
Pending.
