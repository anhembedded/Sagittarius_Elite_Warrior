# EPIC-034A — The Bots mode says what it already knows: venue titles, the chart's messages, why an action is disabled

**Status:** ✅ Done (2026-10-07)
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
- [x] Every place that shows a venue shows its title ("Spot Testnet"); the title map lives once, in contracts, and a guard fails on a venue `.value` rendered in a UI module. Evidence: `TradingVenue.display_name`; `test_venue_titles.py`, `test_bots_dialogs.py`, `tests/unit/architecture/test_venues_are_shown_by_title.py` (its probe plants a raw `.value`).
- [x] The bot chart's messages appear to the user, the way the Desk shows them; a chart with no candles says so and names the symbol and timeframe instead of drawing an empty axis. Evidence: `test_bot_chart_host.py` (red with `logged` disconnected), `test_bot_chart.py::test_a_chart_with_no_candles_names_the_symbol_and_timeframe_not_an_axis`.
- [x] A disabled lifecycle action shows why: its tip and a line next to the primary action carry `ActionAvailability.reason`, updated as the reason changes. Evidence: `test_bots_commands.py` (tip, red with the listener removed) and `test_bots_view.py::test_the_plan_says_why_start_is_unavailable_for_a_bot_at_rest`.
- [x] BUG-159's Market fix for an empty chart is reused, not copied. The shared `LiveCandleChart` already draws the empty window and logs "No historical data"; `BotChart._on_history_drawn` hooks that same event, and nothing of the Market's is copied.

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
- **Venue titles:** `TradingVenue.display_name` in `support/binance_gateway/contracts/trading_venue.py` replaces the Strategies panel's `VENUE_TITLES`. Shown by title now: the Bots table, the Plan read-out, the New bot dialog, the Stop question, the Strategies row, the order confirmation, the environment banner, the planner's problem text. The guard scans UI code for `venue.value` outside a log call; each exemption names the identifier it is (object names, command ids, settings keys).
- **Chart messages:** `BotChartHost` connects `logged` per chart. A line goes to `App.Bots.Chart`, which the bot's log tab already reads through `BotLogFeed`; a failure also goes to the status line, first line only (the text can carry an exchange's answer). Not done: the sync failure's text is the feed's `str(exc)`; the Binance classifier lives in the trading adapter and charting cannot import it, so a market-data adapter should word it (a follow-up for `EPIC-034G`, which rewrites this path).
- **Empty chart:** `EmptyChartNotice` (`support/charting/chart_card/`) swaps the plot for a sentence naming the symbol and timeframe, in a `QStackedWidget` so the page floor does not drop (`test_grid_backtest` caught the first version, which hid the plot). The header and its timeframe picker stay.
- **Reasons:** `ICommandBinder` gains `action(id)`; the lifecycle binding sets the tip on the `QAction` and updates it. The Plan panel adds a "Start: ..." line for a draft or stopped bot, skipped when the refusal already reads under the verdicts. This reverses `EPIC-033D`'s accepted trade-off, as the task designed.
- **Not run:** a screenshot on the owner's display.
