# EPIC-034A — The Bots mode says what it already knows: venue titles, the chart's messages, why an action is disabled

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-07 — *"bot không start được tui cũng không biết nó đang thiếu gì"* (the bot does not start and I cannot tell what it lacks); the epic's origin has the rest.
**Risk:** 🟢 — presentation only; no flow changes
**Complexity:** M — three small, independent fixes across the Bots UI and one guard
**Epic:** [EPIC-034](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** None

---

## 1. Context and problem
- The venue reads as its identifier (`spot_testnet`) in the Bots table, the Plan read-out and the New bot dialog (`src/modules/bots/ui/bots_screen/bots_table_models.py:71`, `bot_facts.py:82`, `new_bot_dialog.py:94`). A title map exists only in the Strategies panel (`ui/strategies/strategy_rows.py:38-41`).
- The bot chart's four messages ("Could not open live stream", "Could not sync…", "No historical data…", "not connected live") go out on `LiveCandleChart.logged`, which the Bots module never connects (`support/charting/live_chart/live_chart_coordinator.py:117-170`; the Desk connects it at `trading/ui/desk/desk_presenter.py:214`). An empty chart draws a default axis: −50…50 and 1970-01-01 dates on the owner's screen.
- A disabled action's reason is computed (`bot_action_rules.py:63-87`) and never shown (`bots_command_binding.py:7-10`, accepted in `EPIC-033D`).

## 2. Acceptance criteria
- [ ] Every place that shows a venue shows its title ("Spot Testnet"); the title map lives once, in contracts, and a guard fails on a venue `.value` rendered in a UI module.
- [ ] The bot chart's messages appear to the user, the way the Desk shows them; a chart with no candles says so and names the symbol and timeframe instead of drawing an empty axis.
- [ ] A disabled lifecycle action shows why: its tip and a line next to the primary action carry `ActionAvailability.reason`, updated as the reason changes.
- [ ] BUG-159's Market fix for an empty chart is reused, not copied.

## 3. Design
Move `VENUE_TITLES` to a contracts module both trading and bots import. Connect `logged` in the bots presenter the way `desk_presenter.py:214` does. For the disabled reason, reverse the `EPIC-033D` trade-off with a dynamic tip set on the QAction by the binding, not a per-widget tooltip. Decisions: [DECISION_2026-10-07_bots_mode_flow.md](../DECISION_2026-10-07_bots_mode_flow.md).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/*/contracts/` | the venue title map |
| `src/modules/bots/ui/bots_screen/*` | titles, `logged` connected, reasons on actions |
| `src/support/charting/chart_card/` | the empty-chart message, if not already shared |
| `tests/unit/architecture/` | the raw-venue guard |

## 5. Testing
Unit tests for each criterion on the real presenter and view; the guard with a probe that plants a raw `.value`. Mutation check: disconnect `logged` and the test goes red. Not run.

## Implementation notes (written when done)
Not started.
