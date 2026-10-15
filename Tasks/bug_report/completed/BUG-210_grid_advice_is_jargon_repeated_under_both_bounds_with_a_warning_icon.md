# BUG-210 — The New Grid form's advice ("4.72 daily ATRs wide, outside 2–4") is unreadable, repeated under both price fields, wears a warning triangle, and the prices carry trailing zeros

- **Reported:** 2026-10-15 (owner, on the New Grid bot form: ETHUSDT, Lower 2371.98, Upper 2824.11, 7 grids, arithmetic, capital 32)
- **Severity:** 🟡 P2 — no money at risk (advice never blocks Start), but the owner cannot tell what the advice means or what to change, so the advice does not do its job
- **Status:** Fixed (2026-10-15)
- **Board:** Advice said "4.72 daily ATRs wide, outside 2–4" under both price fields behind a warning triangle, prices read `2371.98000000`. Cause: each check wrote a bare ratio (no figure, unit, recommendation or action), a multi-field verdict was written under every field, one icon served advice and warnings, and the tick's padding zeros were printed. Fix: `Advice` (finding, consequence, action) builds every Grid warning, a verdict is told once under its first field, advice wears the information icon, prices print without padding zeros.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → Module `bots` (`domain/grid/`, `ui/kinds/grid/`) → Domain (the wording of the checks), UI (where a verdict is shown, its icon, the price fields)
- **Environment:** Linux container, offscreen Qt; app commit `6b236b7` (`master-warrior`); the owner's screenshot is not in the repository. No secret in this report.

## Reproduction
1. New bot, kind Grid, ETHUSDT on Spot Testnet; Lower 2371.98, Upper 2824.11, 7 grids, arithmetic, capital 32, with daily candles stored (daily ATR about 95.8).
2. Expected: one sentence about the range that says how wide it is in USDT, what ETH usually does in a day, what range to try and what it costs to ignore it; an information sign, not a warning; prices without padding zeros.
3. Actual: the same terse line under Lower price and under Upper price, each behind a warning triangle; the fields show `2371.98000000` after Suggest from ATR.
Reproduced by unit tests (below) on the real checks and the real panel; not reproduced against a live venue.

## Symptom
The owner (translated from Vietnamese): "It's advice, but I can't understand it at all. Why don't I see the 96 USD number? Too much is implicit." Advice should not wear the yellow warning triangle.

## Root cause
Three independent faults that the one screenshot shows together, each at a single mechanism:
1. **Wording is written per check, as a bare ratio.** `check_range_against_atr` (`src/modules/bots/domain/grid/grid_checks.py:269`) computed `multiple = (upper − lower) / daily_atr` and wrote only that ratio and the threshold; `daily_atr` itself, the range width, the advised width in price, the consequence and the action never reached the sentence. "ATR" was never defined. Every other warning in the file had the same shape (`check_min_step`, `_exit_distance`, the foreign-orders and spacing checks, `SOME_GRIDS_LOSE`): a ratio or a count, no unit, no recommendation. Nothing required a message to carry them.
2. **A verdict about several fields is told under every one.** `field_errors` (`src/modules/bots/ui/kinds/grid/grid_field_errors.py`) wrote each verdict's text under every field `FIELDS_OF_CODE` lists, and `RANGE_OUTSIDE_ATR_BAND` lists `(LOWER, UPPER)`, so one verdict about the range read as two.
3. **Advice and a warning share an icon.** `GridPanel._mark` (`src/modules/bots/ui/kinds/grid/grid_panel.py`) chose `SP_MessageBoxWarning` for everything that does not block, so a verdict the user may ignore looked like danger.
4. **Padding zeros.** `_to_tick` returned `round(price / tick) × tick` as a `Decimal`, and `Decimal('2371.98') × Decimal('0.01000000')` prints `2371.98000000`: the exchange pads its tick to eight places and the field printed the product as it came; a draft saved from such a field carried the text back.

The gate was green while this was live: `test_grid_checks.py` and `test_grid_field_errors.py` asserted the code and the severity of each verdict and that both bounds were marked, never what the sentence told a person. No case study: the check that closes it is the contract below, in the same change, and the blind spot ("the text of a verdict is untested") is not open for the other kinds, whose verdict wording is not in this file.

## Fix
- `domain/grid/grid_advice.py` (new): `Advice(finding, consequence, action)`, whose `text` adds `ADVICE_TAIL`; a blank part raises, so advice cannot be written without all of them. `Figures` writes a number to the venue's tick without padding zeros and with the symbol's own asset names.
- `domain/grid/grid_advice_texts.py` (new): the words of each advice, from the numbers a check measured. Each recommendation is the value the threshold itself asks for, so following it clears the advice (a test follows each one). `grid_checks.py` keeps every comparison and threshold unchanged and only calls it; the verdicts' `numbers` also carry the new figures (`daily_atr`, `range_width`, `suggested_lower`, `suggested_upper`, `suggested_grids`).
- `MarketView` gains `base_asset` and `quote_asset` (defaults `""`; the sentence then says "The asset" and "quote", never an invented name); `planner_numbers.py` fills them for a symbol quoted in the budget asset, the only quote the bots trade.
- `grid_field_errors.field_errors` tells a verdict once, under the first field of its code (the one to change first, also what `focus_field` brings forward).
- `grid_panel.marker_icon` is the one place severity becomes an icon: the stop sign for a verdict that blocks Start, the stock information icon for advice. Stock `QStyle` icons only.
- `grid_panel._price_text` shows a price without padding zeros, for a suggested range (snapped to the tick) and for a saved draft's text.
- `SPEC-014` row for the advice updated; the Bots-screen preview's `MarketView` names the assets so its frames show the new sentences; the bots-screen test fixture's daily candles now have a realistic day range (the shared builder gave an ATR as wide as the price, which put a long advice under every field of every screen test).

## Regression test
Red before the fix (24 failures on `6b236b7`, each on the sentence or the field, none on a missing import after the module stubs), green after:
- `tests/unit/modules/bots/domain/grid/test_grid_advice_words.py`: the ATR advice names the width, the ATR, the 2–4 day figures in USDT, the recommended range and "Suggest from ATR", wide and narrow; each recommendation (range, grids) clears the same check when followed; every other rewritten advice names its figure, unit and action; a symbol with no asset names gets no invented name.
- `tests/unit/modules/bots/ui/kinds/test_grid_field_errors.py`: a range verdict is told once, in `field_errors` and on the panel; advice renders the information icon (pixel-compared with the style's own) and a blocking verdict does not; `marker_icon`.
- `tests/unit/modules/bots/ui/kinds/test_grid_panel.py`: a tick of `0.01000000` writes `2371.98`; a saved `2371.98000000` shows `2371.98`.

## Verification
Pull request: see the PR for the before/after sequences. Unit and integration tiers of `modules/bots` (3442 tests) green after. The commit tier and the PR's GitHub Actions run: see the PR. Not run against a live venue.

Not covered, by scope: the advice of `futures_grid_checks.py` and `grid_account_checks.py` (liquidation buffer, leverage, funding, the price above the range) keeps its wording; filed as a follow-up.
