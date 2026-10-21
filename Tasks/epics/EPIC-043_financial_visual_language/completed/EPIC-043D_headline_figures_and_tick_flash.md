# EPIC-043D — B3 + B4: headline figures, and the tick flash toggle

**Status:** ✅ Done (2026-10-21; pull request open)
**Source:** the owner, 2026-10-20, accepting [PRO-009](../../../proposal/PRO-009.md) options A + B (*"OK"*; default System, tick flash off by default)
**Risk:** 🟡 — a UI change that must not reintroduce a style layer; the three guards hold it
**Complexity:** M — see PRO-009 §4
**Epic (optional):** [EPIC-043](../README.md)
**Depends on:** 043C (merged, #652)

---

## 1. Context and problem
Equity, the open positions' PnL, how many positions are open and how far the nearest is from liquidation sit in one row above the detail, in a larger, bolder size derived from the system font and the platform's fixed-pitch font for digits. A price cell on the Market watchlist briefly takes the up or down tone on a tick, behind an Options toggle that is off by default; the arrow stays as the non-colour signal.

## 2. Acceptance criteria
- [x] The headline row shows its figures through the application's formatter, derived from the system font, no family set. (`HeadlineStrip` on each Trade desk, in the header under the symbol bar: `equity`, `unrealized_pnl.signed`, `positions`, `liquidation_distance` on Futures; the account value alone on Spot. **Deviation, for the owner to veto: no "today's PnL"** (§3).)
- [x] The tick flash is an Options toggle, off by default; off, a price cell never changes colour on a tick; on, it takes the tone and returns to the platform colour. (Tools → Options → Appearance → Live prices; `TickFlashPreference`; `WatchlistTableModel`.)
- [x] No timer or animation outlives its widget (async-ui-action-rule), checked by a test. (`test_the_timer_is_the_models_child_and_is_gone_with_it`, `test_a_table_that_is_gone_no_longer_listens_to_the_option`, `test_turning_the_flash_off_ends_every_flash_and_the_timer_at_once`, `test_the_real_timer_ends_a_flash_without_anyone_calling_it`.)
- [x] A before/after preview frame for each touched screen. (In the pull request: the desk's preview now holds a headline. The Market mode's flash is a transient; its switch is the Appearance page.)

## 3. Design
**The headline is what the desk already shows, said once more where it is seen first** (`desk_headline.py`). Equity and unrealized PnL come from the account summary the desk shows (`AccountSummaryPresenter.summaryShown`); the number of open positions and the distance to liquidation come from the rows the Positions table was given (`AccountTabsPanel.positionsShown`, emitted by `set_positions`). So the headline cannot disagree with the table beside it and costs no second read. `headline_figures(summary, positions)` is a pure function; `DeskHeadline` holds the two latest inputs and shows its result in the `HeadlineStrip`, a generic widget in `support/ui_kit` (a caption over a figure; the figure is `HEADLINE_SCALE` = 1.5 times its caption, bold, and in the platform's fixed-pitch font when its kind is a digit-aligned one, `kind_font`; the family is never named). Each figure's text is written by the application's formatter and its tone is the meaning table's, so a profit reads `▲ +234.55` in the profit tone and the colour is never the only signal. The equity carries the summary's own name ("Margin balance" on Futures, "Account value" on Spot), so one number has one name. **Freshness (review round 1):** when the summary says "Out of date: …" (a stale event, or a read that failed) the headline says the same in words beside its figures, which stay as the last ones read, and the next summary clears it (`AccountSummaryPresenter.summaryStale`, `HeadlineStrip.mark_stale`).

**Today's PnL is not here (owner may veto).** PRO-009 named it, but nothing in the application reads a profit made today: the account summary has the unrealized figure only. It needs a read of the day's fills in the display time zone, a use case of its own, so it is a later task, not a number made up from the figures at hand (`domain-truth-rule.md`). The headline shows what the account has.

**The liquidation distance is derived, never computed.** The exchange reports each position's liquidation price (`LivePosition.liquidation_price`, which this app never computes); the distance is `|mark − liquidation| / mark` of the nearest position, in percent. No position, or none with a reported price, says `none`. Its tone is plain here: the warning tone and its words are `043E` (B5).

**The tick flash** (`WatchlistTableModel`). With the flash on, a price that moves takes `Tone.POSITIVE` or `Tone.NEGATIVE` through the table's own `_tone` hook for `FLASH_MILLISECONDS` (600), then `NEUTRAL`, which is the platform's colour. The first price a row sees, and a price that did not move, say nothing. The direction is also in words: the `% Change` column keeps its arrow. One single-shot `QTimer`, a child of the model, ends the flashes: `_end_flashes` removes those over and re-arms for the next to end, and the timer stops when none is left. The model reads time from an injected clock, so its tests move time by hand; one test lets the real timer fire. Turning the flash off ends every flash in progress at once.

**The preference** (`TickFlashPreference`) is the colour scheme's shape: one object, subscribers, remembered through `ui_state` (`tick_flash`, `enabled`), registered by `register_remembered_state`, found by `find_tick_flash_preference` (a container with none keeps the flash off). The Market presenter hands it to `follow_tick_flash`, which lets the table follow it and ends the subscription with the table. The Options page gets a check box under "Live prices", changed on OK or Apply like the colour scheme.

**A bug the headline exposed in `paint_label_tone` (043C).** A label inside a toolbar draws its text with `ButtonText`, not `WindowText`; the headline sits in the desk's header toolbar and showed its profit in black. The tone is now written on every text role of the label's palette (`WindowText`, `ButtonText`, `Text`). Found in the preview frame, not by a test; two tests (`test_tone_label.py`, `test_desk_headline.py`) now read the role the label draws with.

## 3a. Reuse
`meaning_colours` (`sign_tone`, `Tone`), `paint_label_tone`, `kind_font`, `write_value` and `signed_key`, `RowTableModel._tone`, `ColourSchemePreference`'s pattern, `AppearanceOptionsPage`, `register_remembered_state`, `build_desk` and `DeskWorld` in the tests: used. New: `HeadlineStrip`, `TickFlashPreference` (both in the capability catalogue).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `support/ui_kit/headline_strip.py` | new: `HeadlineStrip`, `HeadlineFigure` |
| `support/ui_kit/services/tick_flash_preference.py` | new: the preference and its container lookup |
| `support/ui_kit/tone_label.py` | the tone on every text role |
| `modules/trading/ui/desk/desk_screen/desk_headline.py` | new: the figures and `DeskHeadline` |
| `…/desk_screen/desk_view.py`, `desk_presenter.py`, `preview.py` | the strip in the header, the wiring, a headline in the preview |
| `…/account_summary/account_summary_presenter.py`, `…/account_tabs/account_tabs_panel.py` | `summaryShown`, `positionsShown` |
| `modules/trading/ui/market/watchlist_table_model.py`, `watchlist_tick_flash.py`, `market_dependencies.py`, `market_presenter.py` | the flash, its follower, the dependency, one line of wiring (the presenter stays at the 400-line ceiling) |
| `shell/appearance_options/appearance_options_page.py`, `shell/options_pages.py`, `presentation/ui/remembered_state_wiring.py` | the check box, its registration |
| `.claude/rules/ui-presentation-rule.md`, `capabilities.md` | the rule, the catalogue (generated) |

## 5. Testing
New: `test_headline_strip.py`, `test_desk_headline.py` (the pure figures, and the desk's bus events through to the strip), `test_tick_flash_preference.py`, `test_tick_flash_is_remembered.py`, `test_watchlist_tick_flash.py` (off by default, direction, expiry, a second tick, off mid-flash, a symbol that leaves, the real timer, the timer's death with the model, the mode's wiring), page cases in `test_appearance_options_page.py`, a toolbar case in `test_tone_label.py`, the stale mark at strip, desk and presenter level, the zero mark, the timer's re-arm, and two wiring tests against the real graph (`test_options_pages.py`: the Appearance page and the Market mode's dependencies share the one registered preference). Mutation (testing-rule), each turns a test red and was restored: both desk wirings, the strip's place in the header, the PnL tone, nearest → farthest, the distance's base, bold, the scale, the fixed-pitch font, the tone write, the presenter's `follow_tick_flash` line, the table's unsubscribe, the toggle check, the flash's direction and its expiry.
Not run: a real display's dark palette; the glyph `▲ ▼` in the platform's fixed-pitch font.

## 6. Docs touched
`.claude/rules/ui-presentation-rule.md` §1 (one clause), `.claude/rules/capabilities.md` (generated). `Docs/MODULES/` has no `trading` folder, so there is no module design to change.

## Implementation notes
Delivery: `claude/epic-043d-headline-figures-and-tick-flash`, from master after `043C`; a reviewer session reads it; the owner merges. Follow-ups: a headline for the Bots screen (the proposal names "the Bots, trading and market screens"; the Bots screen's figures are in its table and the Plan dock, so it is not forced here); today's PnL (a use case of its own).
