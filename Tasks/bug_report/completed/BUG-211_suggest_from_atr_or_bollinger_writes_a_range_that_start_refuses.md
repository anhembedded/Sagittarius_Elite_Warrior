# BUG-211 — Suggest from ATR / Suggest from Bollinger write a range only, so the plan it makes is refused by Start (exits on the wrong side, price outside the range), with no log

- **Reported:** 2026-10-15 (owner, after PR #516 / BUG-210 merged: Spot Mainnet ETHUSDT grid, 6 arithmetic grids, capital 35, stop loss price 2259, take profit price 2805)
- **Severity:** 🟡 P2 — Start refuses the plan, so no order is placed; but the two buttons exist to give a runnable plan and gave one that cannot run. The fix changes the exit prices a bot may later be started with (only on a click, before Start).
- **Status:** Fixed (2026-10-15)
- **Board:** Suggest from ATR/Bollinger gave a plan Start refuses (stop loss 2259 above the new lower limit, take profit 2805 below the new upper limit, price 2368.155 below a Bollinger lower limit 2370) and logged nothing. Cause: the buttons wrote only Lower/Upper and copied the band as it was; no code judged the result. Fix: one domain `suggest_plan` recentres a band that misses the price, moves price-exits the new range invalidates to the middle of the advised distance (said on the panel), judges the result with the unchanged checks and logs `[grid-suggest]`; the blocking messages print plain prices and the quote amount with its unit.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → Module `bots` (`domain/grid/`, `ui/kinds/grid/`) → Domain (a suggested plan, the wording of two checks), UI (applying and showing it)
- **Environment:** Linux container, offscreen Qt; app commit `279255c` (`master-warrior`); the owner's screenshots are not in the repository. No secret in this report.

## Reproduction
1. Spot grid ETHUSDT, 6 arithmetic grids, capital 35, stop loss `price:2259`, take profit `price:2805`; last price 2368.155; stored daily candles.
2. Press Suggest from ATR (range 2227.92–2515.54) or Suggest from Bollinger (band 2370–2825.29).
3. Expected: a plan Start accepts. Actual: "Blocks Start: The stop loss 2259 is at or above the lower limit 2227.92" (ATR); "Blocks Start: The price 2368.15500000 is below the range's lower bound 2370 … 34.10 of the base asset" and "The take profit 2805 is at or below the upper limit 2825.29" (Bollinger).
Reproduced by unit tests on the real panel and the real checks.

## Symptom
Owner (translated): "These two buttons generate a plan that is broken; the generated plan cannot run. What does pressing them do, and why is there no log?" Also: the refusal printed the raw Decimal `2368.15500000` and called a quote amount "the base asset".

## Root cause
Is this a regression? **No: it is the old gap made visible.** `git log -S` shows the suggestion writing only the two range fields since the panel's `_fill_range` (carried through `cde9337`, BUG-193); `279255c` (BUG-210) changed only the rounding of those two fields (`price_text`, `snap_to_tick`) and the wording of the advice, so the advice now says why the take profit is far, which the owner had not read before. What changed on 2026-10-15 is the readability, not the behaviour.

1. **The suggestion is a range, the plan is a range plus exits plus a price.** `GridPanel._fill_range` (`src/modules/bots/ui/kinds/grid/grid_panel.py:354` before the fix) wrote Lower and Upper and left the exits as they were; an exit given as a price (`price:2259`) does not follow the edge, so a range that moves past it is refused by `check_stop_loss` / `check_take_profit` (`grid_checks.py`, `STOP_LOSS_INSIDE_RANGE` / `TAKE_PROFIT_INSIDE_RANGE`). No code judged the result of pressing the button.
2. **The Bollinger band is copied as is.** `_bollinger_suggestion` (`application/queries/get_planner_market/handler.py`) returns the band of the stored daily closes; the ATR range is centred on the last stored daily close. Neither is compared with the live price, so when price is outside the band the written range excludes it (`PRICE_BELOW_RANGE`, which would market-buy 97% of the capital).
3. **No log** was written when a suggestion was applied, so nothing could say which input produced the range.
4. **Messages.** `check_price_against_range` formatted `last` and the bounds as raw `Decimal` (`2368.15500000`) and `opening_quote` (quantity × price, i.e. a quote amount) as "of the base asset"; the stop loss, take profit and price-band refusals printed raw Decimals too.

The gate was green while this was live: tests of the buttons asserted that the range fields were filled and rounded, never that the plan they produce passes the planner's own blocking checks.

## Fix
- `domain/grid/grid_suggestion.py` (new): `suggest_plan(SuggestionRequest) -> PlanSuggestion`, the one place a source's band becomes a whole plan, for ATR, Bollinger and any later source: snap the band to the tick; if it misses the price, recentre it on the price at the same width (documented in the plan's `range_note`); move every exit given as a price that the new range makes invalid or leaves outside `exit_distance_low…high` to the middle of that distance, with `ExitMove` naming the exit, old, new and why; leave an `off` exit and a percentage exit (it follows its edge) alone; judge the result with the unchanged `evaluate_grid` and return the blocking codes still present. Thresholds and checks are untouched.
- `ui/kinds/grid/grid_panel.py`: `_fill_range` becomes `_apply_suggestion`, which calls `suggest_plan` (through `suggest_for` in the new `grid_editor_parts.py`, which also takes the panel's small helpers so the file stays under the 400-line ceiling), writes the range and moved exits, shows one line (`lblGridSuggestion`, hidden on the next edit) and logs one INFO `[grid-suggest]` line (`grid_suggestion_log.py`) on `App.Bots.Grid`: source, band, daily ATR, last price, tick, range, exits moved (old->new), blocking count and codes.
- `domain/grid/grid_range_checks.py`, `grid_checks.py`: the price, the bounds, the stop loss, the take profit and the band refusal print `plain(...)` (no padding zeros, no exponent, the price as the venue gave it) and the opening amount is `figures.money(...)` of the base asset by name (`35 USDT of ETH`).
- `domain/grid/grid_params.py`: `exit_level_of`, the public reader of an exit.
- `SPEC-014`: the suggestion description and test row.

## Regression test
Red on `279255c` (7 failures, each on the sentence, the missing note or the refused plan), green after:
- `tests/unit/modules/bots/domain/grid/test_grid_suggestion.py`: for both sources with the owner's exits and price the plan has zero blocking verdicts; exits move to 5.5% beyond the limit on the tick; a band above or below the price is recentred at the same width and holds the price; off, percentage and already-advised exits are untouched; a blocker the suggestion cannot clear (capital 3) is named.
- `tests/unit/modules/bots/ui/kinds/test_grid_panel.py`: pressing either button on the real panel leaves no REFUSED verdict (the same plan had one before); the panel line names the moved exits and goes with the next edit; an off exit stays off; exactly one `[grid-suggest]` INFO record carries source, band, ATR, price, tick, range, moves and `blocking=0`.
- `tests/unit/modules/bots/domain/grid/test_grid_range_checks.py`: the refusal prints `2368.155`, `2370.`, `35 USDT of BTC`, never "base asset"; the exit refusals print `61000`, not `61000.00000000`.
- The BUG-210 test `test_a_price_is_shown_without_the_zeros_the_exchange_pads_it_with` now uses a price inside its band (it had 65000 beside a 2371–2824 band, which the new behaviour adapts); its assertions are unchanged.

## Verification
Pull request: see the PR for the before/after sequences. `modules/bots` unit tests (3275) green after; commit tier (`ruff`, format, `mypy`, reference check) and architecture guards: see the PR. The GitHub Actions `ci-local.ps1 -Full` run on the PR head is the full gate. Not run against a live venue; no order placed or simulated.

Not covered, by scope: advice distances for a `percent` exit that is itself outside 3–8% stay the user's (they follow the edge and the range cannot make them worse); account-only checks (balance, key permission) are not in the readiness the suggestion counts, since the editor does not hold the account.
