# EPIC-034G — The chart states whether it is live, and the user starts and stops it

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-07 — *"bot không start được tui cũng không biết nó đang thiếu gì"* (the bot does not start and I cannot tell what it lacks); the epic's origin has the rest.
**Risk:** 🟡 — the shared chart used by Market, Desk, Backtest and Bots
**Complexity:** M — one FSM and its commands
**Epic:** [EPIC-034](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** [EPIC-034A](EPIC-034A_bots_mode_says_what_it_knows.md)

---

## 1. Context and problem
The bot chart goes live only for a started bot (`src/modules/bots/ui/bots_screen/bot_chart_host.py:43,108-110`); the toolbar's "Go live" only scrolls to the newest candle (`viewport_controller.py:28-33`). Nothing tells the user whether candles are arriving.

## 2. Acceptance criteria
- [ ] The shared live chart has four states in one `*_fsm_matrix.py`: History, Connecting, Live, Error; each shows a chip with its words (Error with the reason) and the matching command: Go live, Cancel, Stop live, Retry.
- [ ] In the Bots mode the chart can go live for a draft bot after Connect (D9); a running bot's chart is Live by itself.
- [ ] Live reports the age of the last update.
- [ ] Market, Desk and Backtest use the same state and commands, or the task records why one does not.

## 3. Design
The FSM wraps the existing `LiveChartCoordinator` sync-then-stream sequence; it is a view of that lifecycle, not a second one. Decisions: [DECISION_2026-10-07_bots_mode_flow.md](../DECISION_2026-10-07_bots_mode_flow.md).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/charting/live_chart/` | the FSM and its commands |
| the chart's hosts | wired |

## 5. Testing
An FSM table test; presenter tests per host; a desktop E2E picture of each state. A reviewer is required. Not run.

## Implementation notes (written when done)
Not started.
