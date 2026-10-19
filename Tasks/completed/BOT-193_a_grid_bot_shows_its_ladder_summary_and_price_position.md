# BOT-193 — A Grid bot shows its ladder, its summary line and where the price stands

**Status:** ✅ Done (2026-10-19)
**Board:** The Bots tab (a Ladder dock and Plan rows) and `bot show`/`bot show --grids`/`bot list` show a Grid bot's grids, steps, profit per cycle and the distances to the range, exits and last price from the saved record only, never zero for an unknown figure; delivered in [#576](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/576) and [#577](https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/577) (PRO-016); the net after fees came with [BOT-194](completed/BOT-194_the_grid_runtime_saves_the_makers_rate_at_run_start.md).
**Source:** The owner, 2026-10-19: "tui cần biết các grid cách nhau bao nhiêu % giá, mỗi grid sẽ TP được bao nhiêu" ("I need to know how far apart the grids are in percent and how much each grid takes as profit"); accepted [PRO-016](../proposal/PRO-016.md) as written and asked for the UI first.
**Risk:** 🟢 — read-only; no order, bot behaviour, alert or stored field changes (one optional `mark_price_at` is read into `BotProgress`).
**Complexity:** M — one read model, one wording module, a dock, Plan rows, then the commands (a second pull request).
**SPEC (optional):** [SPEC-015](../../Docs/SPEC/SPEC-015_run_the_bots_headless.md) (second pull request)
**Depends on:** BOT-192 (`RunEarnings`, `number_text`), merged.

---

## 1. Context and problem
A running bot's grid spacing and per-grid profit exist only in plan-time checks (`derive`, read at `3eda6b8`); nothing in the tab or the commands shows them for a running bot. Unknowns settled by reading: the saved run holds `mark_price` and `mark_price_at` (kept across stop and halt); the Futures liquidation price is not saved; `RuntimeLevel.ended_at` records orders that ended *unfilled*, so there is no per-level cycle count; the account's maker fee rate is read from the exchange and not saved, so a read-only copy cannot give the net after fees.

## 2. Acceptance criteria
- [x] The ladder rows equal `derive`'s grids; an arithmetic and a geometric bot differ as `grid_spacing.py` says; the ladder follows the bot's current saved parameters (`test_grid_ladder.py`).
- [x] A figure without a price, fee, sizing or run is a blank cell or a sentence, never zero; profit per cycle is before fees until a rate is known, and says so.
- [x] The Bots tab has a Ladder dock (one row per grid: buy, sell, step, net step, profit per cycle, what the saved run says it is doing) and the Plan panel rows grid step, profit per cycle, average booked per cycle, last price heard with its age, lower and upper edge with distances, stop loss, take profit and, on Futures, a liquidation row that says it is not in the record.
- [x] No profit per day, no claim about how often price crosses a level; grid profit wording: net of both legs' fees, Futures funding not included.
- [x] A picture of the booted workbench with a seeded bot and the Ladder in front is in the screenshot artifact at the three sizes (`test_bots_ladder_is_pictured.py`); `preview.py` has `build_ladder_preview`.
- [x] Second pull request: `bot show --grids` (text and `--json` under `ladder`), the summary line in `bot show`, a `GRID STEP` column in `bot list`, runbook and SPEC-015; the figures equal the tab's (`test_bot_ladder_reports.py`). The report layouts have text and JSON only; no key=value renderer is registered.

## 3. Design
`grid_ladder_of(BotSnapshot, now)` (contracts, Qt-free) reads the parameters now (`GridParams.from_config`) and builds the levels with `raw_levels`, so a bot edited with `bot edit` shows the edited ladder; the step and net come from `grid_profits`, extracted from `derive` (one arithmetic). Prices are the raw levels (no tick without the exchange's filters). The run's state per grid comes from `BotProgress.orders` and only when every resting order sits on a rung of the current parameters within half the smallest step; otherwise states are "not recorded" with a note. Profit per cycle is an estimate on `derive`'s own basis (capital over the levels that hold an order; a position venue the one quantity at the highest level). The maker fee is an optional input (`maker_fee`), `None` from both consumers until a follow-up saves it. Distances are per cent of the last price the bot heard.

## 3a. Reuse
`RunEarnings` words style, `MoneyWriter`/`PriceWriter`, `plain_money`/`plain_price` (used); `number_text` (extended with `percent_text`, same rule as the formatter's PERCENT); `derive` arithmetic (extracted as `grid_profits`, not copied); `SpecTable`, `RowTableModel`/`SelectedBotRows`, `MinimumHintSlot`, `plain_label`, `ReadoutForm` (used); `GridParams`, `raw_levels` (used).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/contracts/grid_ladder.py`, `grid_ladder_texts.py` | New read model and wording |
| `src/modules/bots/domain/grid/grid_derived.py` | `_grids` → public `grid_profits` |
| `src/core/vo/number_text.py` | `percent_text` |
| `src/modules/bots/contracts/bot_progress.py`, `.../readiness/bot_progress_reader.py` | `mark_price_at` |
| `src/modules/bots/ui/bots_screen/` `bot_ladder_panel.py`, `bot_ladder_facts.py`, `bots_table_models.py`, `bots_view.py`, `bots_view_model.py`, `bot_detail.py`, `detail_effects.py`, `bot_plan_panel.py`, `preview.py` | Ladder dock, Plan rows, wiring, preview |
| `Docs/MODULES/bots/05-building-blocks.md` | The ladder read model |
| second PR: `contracts/grid_ladder_payload.py`, `contracts/bot_status_report.py`, `.../get_bot_status_report/handler.py`, `cli/bot_status_reports.py`, `cli/bot_verbs.py`, `src/config/cli_commands.json` | `ladder` on the status entry and its JSON, `--grids`, the `GRID STEP` column |

## 5. Testing
Unit: `tests/unit/modules/bots/contracts/test_grid_ladder.py`, `test_grid_ladder_texts.py`, `tests/unit/modules/bots/ui/bots_screen/test_bot_ladder_panel.py` (through the presenter's real wiring, store to table), `test_bots_preview.py`, `test_bots_view.py`. Integration: `test_bots_ladder_is_pictured.py`. Mutation checks: see Implementation notes. The `-Full` run is the full gate.

## 6. Docs touched
`Docs/MODULES/bots/05-building-blocks.md` (this pull request); `Docs/OPERATIONS/headless_runbook.md` (new section on the ladder), `Docs/SPEC/SPEC-015_run_the_bots_headless.md` (a verification row), `Docs/MODULES/bots/07-deployment.md` (the commands' path), all in the second pull request.

## Implementation notes (written when done)
Delivered in two pull requests, each reviewed (PASS) by a separate Opus session with a green `-Full` run on its head: #576 (read model, Bots tab) and #577 (`bot show`, `--grids`, `bot list`). Facts found while building: the saved run holds the last price and its moment; the Futures liquidation price is not saved; `RuntimeLevel.ended_at` records unfilled endings, so no per-level cycle count; the maker rate was not saved, which BOT-194 fixed. The report layouts have text and JSON only (no key=value renderer). Known limit: a sub-cent profit in the Bots tab's table cells still prints `0.00` (the sentences say `less than 0.01`).


