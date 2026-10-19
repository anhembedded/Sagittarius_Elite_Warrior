# BOT-192 — The Bots tab, `bot list` and `bot show` lead with the profit the completed cycles earned

**Status:** ✅ Done (2026-10-19)
**Board:** Grid profit and cycles now lead the Bots table, panel, `bot list` and `bot show` (total and unrealised kept apart), from the stored record with no exchange call; one shared Qt-free `RunEarnings` wording, `—` / `no price yet` never zero.
**Source:** The owner, scope corrected by the coordinator (grid profit and cycles first; the owner means profit earned by completed cycles, not PnL with open positions), through the coordinator, 2026-10-19: "the UI and the VPS still do not show how much profit the bot has made". `bot list` and `bot show` printed no profit, cycles or total at all (read at `15379eb`).
**Risk:** 🟢 — read-only; no order, bot behaviour or alert changes. The Bots tab's grid-profit and total-PnL cells now build their text through the shared module, locked by the existing `test_bot_facts.py`.
**Complexity:** S — one value object, one entry field, two report layouts.
**SPEC (optional):** [SPEC-015](../../Docs/SPEC/SPEC-015_run_the_bots_headless.md)
**Depends on:** None

---

## 1. Context and problem
`bot_status_reports.py` printed id, name, state, venue, symbol and reason only. The headless host has no window, so a bot's profit was invisible there. The Bots tab writes the figures in `bot_facts.py` behind Qt, which a headless host does not install (`requirements-headless.txt`).

## 2. Acceptance criteria
- [x] `bot list` has GRID PROFIT, CYCLES and TOTAL PNL columns; `bot show` has Grid profit, Cycles and Total PnL rows; the figures equal the Bots tab's `bot_facts` for the same record.
- [x] From the stored record only: no exchange call, no host, no lock.
- [x] A figure the record cannot give prints the tab's no-value text (`—` with no run record, `no price yet` while the total waits for a price), never zero; `--json` carries `earnings` as exact decimal text, `null` where unknown.
- [x] The commands import no Qt.
- [x] The Bots table has `Grid profit` and `Cycles` columns before `Total PnL`; the panel lists "Profit from completed cycles" first, then cycles, total and "of which unrealised"; `bot show` lists grid profit, cycles, total, unrealised in that order.

## 3. Design
`RunEarnings` (a frozen value object built from `BotProgress`) and the three text functions live in `bots/contracts/run_earnings.py`, Qt-free. The tab and the commands both call them; each passes its money writer (the tab's `write_value`, the commands' `plain_money`), and both writers call the one pair of number rules in `core/vo/number_text.py`, extracted from the formatter (P5: one wording, one place; review round 1, finding 1). `BotStatusEntry.earnings` carries it through the existing status query, so `status` and the Bots-tab-backed queries stay one read model (`EPIC-038C`).

## 3a. Reuse
`BotProgress`/`PnlSummary` (used, unchanged), `Report`/`emit_report` machinery (used), `bot_facts` wording (moved, not copied). `capabilities.md`: no row for "write a run's earnings"; `write_value` is Qt-bound, so it is not used by the commands.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/contracts/run_earnings.py`, `src/core/vo/number_text.py` | New: `RunEarnings`, texts, `plain_money`/`plain_price`; the formatter's money and price rules, Qt-free, now called by both |
| `src/modules/bots/ui/bots_screen/bot_facts.py`, `bot_plan_panel.py`, `bots_table_models.py` | Shared texts; panel order and labels; table columns |
| `src/modules/bots/contracts/bot_status_report.py`, `.../get_bot_status_report/handler.py` | `earnings` on the entry and its payload |
| `src/modules/bots/cli/bot_status_reports.py` | Columns and rows |
| `Docs/OPERATIONS/headless_runbook.md`, `Docs/MODULES/bots/07-deployment.md`, `Docs/SPEC/SPEC-015_run_the_bots_headless.md` | The new figures |

## 5. Testing
`tests/unit/modules/bots/cli/test_bot_earnings_reports.py` (figures equal the tab's, no-price and no-record cases, JSON), `tests/unit/modules/bots/ui/bots_screen/test_plain_money_is_the_tabs_money.py` (parity), `test_bot_verbs.py` (payload keys pinned). Unit tier; the PR's `-Full` run is the full gate.

## 6. Docs touched
The three documents above.

## Implementation notes (written when done)
The Bots tab shows no cycle count today (only Total PnL and "of which grid profit"), so `Cycles` is new wording. Reports have the `text` and `json` formats only; no key=value renderer is registered. Commit tier PASS; unit slices `tests/unit/modules/bots`, `operations`, `presentation`, `tests/integration/presentation` and `tests/unit/architecture`: 6237 passed. `test_workbench_conformance[True-1024x700]` (Backtest window size) fails in this container on a clean `15379eb` too and is unrelated.
