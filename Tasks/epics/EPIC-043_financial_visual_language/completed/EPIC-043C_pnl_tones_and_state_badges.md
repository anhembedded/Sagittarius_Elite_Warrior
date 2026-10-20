# EPIC-043C — B1 + B2: PnL toned everywhere, and state badges

**Status:** ✅ Done (2026-10-20; pull request open)
**Source:** the owner, 2026-10-20, accepting [PRO-009](../../../proposal/PRO-009.md) options A + B (*"OK"*; default System, tick flash off by default)
**Risk:** 🟡 — a UI change that must not reintroduce a style layer; the three guards hold it
**Complexity:** M — see PRO-009 §4
**Epic (optional):** [EPIC-043](../README.md)
**Depends on:** BOT-209 (merged, #648: the Plan dock structure). The tones do not need 043B's Options choice, so this branches from master.

---

## 1. Context and problem
Every PnL, return and change figure on the Bots, trading and market screens takes its colour from `Tone`, with sign and ▲ ▼ kept in the text; a bot's or connection's state is a word plus an icon, coloured by a small extension of the meaning table: running, paused, halted, recovering, disconnected. In the Bots Plan dock, the banner, checks list and figures take their tones from the meaning table on top of BOT-209's structure.

## 2. Acceptance criteria
- [x] Every PnL, return and change figure on the three screens is toned by `Tone` and still carries its sign and arrow. (Bots table: grid profit, total PnL; Ladder: gross, net step, net per cycle; Plan dock: grid profit, total PnL, unrealised, HODL, average per cycle; Positions and Trade History PnL; the account summary's unrealized PnL; the Watchlist's % change. Each through `signed_key` + a tone.)
- [x] Each state in the list has a word, an icon and a tone from the meaning table; no new colour is written outside it. (Running, paused, halted, recovering, awaiting recovery, error; the connection: connected, not connected, failed, connecting. `StateLook`: an icon file stem and a `Tone`; the colours are `tone_colour`'s, written only in `meaning_colours.py`.)
- [x] Readable in light, dark and Windows High Contrast (palette-aware, tested as in `test_meaning_colours.py`). (Every tone is asked of the palette at paint; High Contrast returns none, so the platform's colours stand: `test_table_model_tone.py`, `test_tone_label.py`, `test_tone_delegate.py`. A real Windows High Contrast session is Not run.)
- [x] A before/after `preview.py` frame for each touched screen. (In the pull request.)

## 3. Design
**One arrow-and-sign rule, in the formatter.** No formatter wrote a sign or arrow before (money read `-9.00`, percent `12.50%`). A column or read-out row whose key is a `signed_key` ("pnl.signed", like `ratio_key`) is written `▲ +12.50` / `▼ -9.00`; exactly zero has neither (the Engine's plain percent writer prints `-0.00%`; the signed path drops that minus), while a figure too small for its decimals keeps its direction (`▲ +0.00`), so the text says what `sign_tone` colours it by (review round 1); NaN and infinity have neither arrow nor tone. Sorting is on the raw value. This is in `value_formatter.py` because the UI may not write numeric format specs itself (`test_display_values_go_through_the_formatter.py`). The cost is renaming the PnL columns' keys (`pnl` → `pnl.signed` and so on), a name no table remembers (column keys are used in-process only; no width, order or sort is saved by key); the tests that named them were updated, among them the two CLI parity tests, which compare the figure without the tab's arrow and sign.

**One tone hook for every table.** `RowTableModel._tone(row, column) -> Tone` (default `NEUTRAL`); `data()` turns it into `tone_colour(tone, QGuiApplication.palette())` at each paint, so the colour follows the scheme and High Contrast. The Bots table's private `_foreground`/`sign_tone` copy is gone (`sign_tone` moved to `meaning_colours.py`). Models migrated: Bots, Ladder, Positions, Trade History and the Watchlist, which was the one table painting raw chart bull/bear colours that ignored the palette. **Behaviour change, for the owner to veto:** a Watchlist change of exactly zero was painted as a win; it now has no verdict, like every other figure.

**For what is not a `RowTableModel`.** A label: `paint_label_tone(label, tone)` sets the label's `WindowText` from the meaning table and repaints on `ApplicationPaletteChange` (no style sheet; the colour is never written). A tree or list over a `QStandardItemModel`: a cell names its tone in `TONE_ROLE` and `ToneKindDelegate` paints it (the Plan dock's property table and checks). A read-out row names its tone in `Readout.tones` (the account summary).

**State = word + icon + tone.** `StateLook(icon, tone)` per state, in a table the owning module writes (`bot_state_looks.py`: a complete `EnumLabels` for the words, which also fixes `Awaiting_recovery`; `connect_view.py` for the connection; `market/connection_words.py` for the exchange). `StateBadge` is the stock composite the notice bar is (an icon label and a word label; a QLabel cannot show both), keeping `text()`/`setText()` for readers. The Bots table puts the icon in `DecorationRole`. Two Lucide icons were added (`pause`, `circle-x`) and made required.

**The Plan dock.** The banner's message takes its severity's tone (and "Ready to start" the profit tone, via `PlanStatus.tone`); each check takes its severity's; the figures take their sign's. The structure is BOT-209's, untouched.

## 3a. Reuse
`Tone`, `tone_colour` (extended with `sign_tone`), `RowTableModel`, `EnumLabels`, `NoticeBar`, `IconLoader`, `KindDelegate`, `ReadoutSlot`, `plain_label`: used. `backtest_stat_row._paint` and `metrics_detail_dialog._paint` were two older copies of a label-tone painter that used `tone_colour(tone)` without a palette; they, and the two backtest metric models, are `paint_label_tone` and `_tone` now, which is [BOT-196](../../../completed/BOT-196_backtest_tones_use_the_palette_aware_meaning_table.md) delivered here.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `support/ui_kit/value_formatter.py` | `signed_key`, the arrow-and-sign rule |
| `support/ui_kit/meaning_colours.py`, `table_model.py` | `sign_tone`; the `_tone` hook |
| `support/ui_kit/tone_label.py`, `tone_delegate.py`, `tone_icon.py`, `state_look.py`, `state_badge.py` | new |
| `support/ui_kit/readout_slot.py`, `notice_bar.py`, two icons, `asset_validator_extension.py` | tones on read-outs and notices; `pause`, `circle-x` |
| `modules/bots/ui/bots_screen/…` | tables, facts, plan grid, banner, checks, strip, state looks |
| `modules/trading/ui/…` | Positions, Trade History, Watchlist, account summary, market connection |
| `.claude/rules/ui-presentation-rule.md`, `capabilities.md`, `Docs/MODULES/bots/05-building-blocks.md` | the rule, the catalogue, the design |

## 5. Testing
New: `test_value_formatter.py` (signed), `test_table_model_tone.py`, `test_tone_label.py`, `test_tone_delegate.py`, `test_readout_slot_tones.py`, `test_state_badge.py`, `test_state_icons.py`, `test_bot_state_looks.py`, `test_connection_and_state_badges.py`, `test_plan_dock_tones.py`, and tone/arrow cases in the Bots, Positions, Trade History, Watchlist, account summary, market connection and Plan panel tests. Updated for the new keys and text: the tests that read `pnl`, `change`, `profit`, `net_quote` and the Plan figures. Mutation (testing-rule): removing the tone branch of `data()`, the arrow, each table's `_tone`, the read-out and grid tone writes, the panel's pass-through, the banner and checks tones, the state icon in the table, the Plan state look, the strip's look, the market presenter's look and the badge's icon each turns a test red.
Not run: Windows High Contrast; the glyph `▲ ▼` in the platform's fixed-pitch font (Qt falls back where it is missing).

## 6. Docs touched
`Docs/MODULES/bots/05-building-blocks.md` (a paragraph: how a figure and a state read), `.claude/rules/ui-presentation-rule.md` §1, `.claude/rules/capabilities.md` (generated).

## Implementation notes
Delivery: `claude/epic-043c-pnl-tones-and-badges`, from master after `BOT-209`; a reviewer session reads it; the owner merges. Not in this task (follow-ups for the epic): the Data screen's kline inspector still paints raw bull/bear colours (it is not one of the three screens); the Options → Trading venue connection label and the Strategies table's "Armed" word have no icon. 