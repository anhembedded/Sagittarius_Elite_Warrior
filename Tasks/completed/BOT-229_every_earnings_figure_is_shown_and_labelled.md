# BOT-229 — Every earnings figure is shown, in the order that adds up, with its basis

**Status:** ✅ Done (2026-10-21)
**Board:** The owner read Grid profit 1.83 against Total PnL 20.94 as "unreal" because nothing named the realised money from the opening inventory or the held position; `bot show`, the Bots tab Results group and `--json` now list Realised, of which grid cycles, Held, Unrealised, fees, funding and the Total with its sum, from the booked figures with no total changed (decision of the coordinator under the owner's delegation, 2026-10-21).
**Source:** Coordinator session `session_016sGQHsRy729Fp4cY1cTXfu`, 2026-10-21, from the owner's reading of bots `6tszoz` and `6z20d2`.
**Risk:** 🟢 — display only; no figure is computed anew.
**Complexity:** M — one contract, one CLI section, one table group, frames.
**Depends on:** None.

---

## 1. Context and problem
`PnlSummary` already holds `realised`, `unrealised`, `grid_profit`, `commissions` and `funding`; the surfaces showed Grid profit, Cycles, Total PnL and Unrealised, so the realised money that is not a paired cycle had no name, and "Unrealised" was read as all of the gap.

## 2. Acceptance criteria
- [x] `bot show` lists Realised, Grid profit, Cycles, Held, Unrealised, Fees paid, Funding, Total PnL, the sum `= realised + unrealised + funding` and the basis words, from the same booked figures.
- [x] The Bots tab Results group lists them in the same order with the same words, light and dark frames.
- [x] `--json` carries `realised`, `held` and `average_cost` beside the existing keys; no existing key changes.
- [x] `bot list` keeps its columns and gains a legend line saying Grid profit counts only completed cycles and the held part reverses if the price falls back.
- [x] No total changes: `total_pnl`, `grid_profit`, `unrealised` are read as before.

## 3. Design
`RunEarnings` gains `realised`, `held` and `average_cost` (from `PnlSummary.realised` and `BotProgress`); the titles, the basis sentence and the list legend live in `run_earnings.py`, the one place the tab and the commands take their words from. Fees are shown as paid and are already inside realised (sell fees) and the cost of what is held (buy fees), so the sum adds only realised, unrealised and funding.

## 3a. Reuse
`RunEarnings`, `plain_money`, `plain_price`, `PROPERTY_GROUPS`, `BotFacts`: used; no new accounting.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/contracts/run_earnings.py` | new fields, titles, basis and legend sentences, `realised_text`, `held_text` |
| `src/modules/bots/cli/bot_status_reports.py` | `_earnings_rows` for `bot show`, the second legend line of `bot list` |
| `src/modules/bots/contracts/bot_status_report.py` | `realised`, `held`, `average_cost` in the JSON |
| `src/modules/bots/ui/bots_screen/bot_facts.py`, `plan_property_rows.py` | the Results rows in the new order and titles, the basis row |
| `src/modules/bots/ui/bots_screen/plan_dock_frames.py` | the running-bot frame's figures add up |

## 5. Testing
`tests/unit/modules/bots/cli/test_bot_earnings_reports.py` (order, sum line, basis, JSON keys), `test_bot_facts.py` (row order), `test_plan_property_grid.py` (titles). Frames: `BOT-229_assets/results-{light,dark}.png` (a dark Fusion palette stands in for the Windows scheme on the offscreen platform).

## 6. Docs touched
`Docs/SPEC/SPEC-014_run_a_grid_bot.md` (earnings row), `Docs/OPERATIONS/headless_runbook.md` (`bot list`, `bot show`, `--json`, the panel rows), `Docs/MODULES/bots/07-deployment.md` (the earnings paragraph).

## 7. Implementation notes (2026-10-21)
- The coordinator's "Position PnL" figure is not a separate book: it is unrealised plus the realised result of the sells that are not cycles, both already held. The full breakdown replaces it, as the coordinator widened the task.
- The earlier frame of the running bot had a total that left out the funding; it now adds up (42.15 + 7.70 - 0.31 = 49.54).
- Each printed figure is rounded to the cent on its own, so the parts of the sum can differ from the printed total by a cent or two (review round 1); the basis line says so.
- A rare edge: an exit fill that covers more than a SHORT or NEUTRAL position held books only its covered share of the fee into realised while `commissions` counts all of it, so "Fees paid (inside the figures above)" can overstate by the uncovered share in that recovery path.
- Not changed: `Total PnL (net)` column heads and the exchange-basis unrealised row.
