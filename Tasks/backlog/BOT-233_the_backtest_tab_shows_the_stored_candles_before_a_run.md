# BOT-233 — The Backtest tab shows the stored candles of its period before a run

**Status:** 🟡 In progress
**Board:** The Backtest tab's chart was empty (an unfed chart on the 1970 axis) until a run, and Sync candles appeared only after a refused Run; it now draws the venue's stored candles for the chosen interval and period with no grid parameters, offers Sync candles when some are missing, shows a sentence instead of an empty axis, and names the remedy past 20,000 candles.
**Source:** the owner, 2026-10-22, with a screenshot, via the coordinator (session_016sGQHsRy729Fp4cY1cTXfu): "bug, poor user experience: opening Backtest there is no button to load candles, so no candles are shown" (translated).
**Risk:** 🟢 — a read-only query and a chart draw; a sync is the existing one
**Complexity:** M — one query, one preview collaborator, the presenter split to stay under the file ceiling
**Epic (optional):** [EPIC-040](epics/EPIC-040_backtest_workbench/README.md)
**SPEC (optional):** [SPEC-014](../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** None (shares PR #721 with BOT-232 because both change `src/modules/bots/ui/backtest_workbench/`)

---

## 1. Context and problem
The screenshot: Bots → Backtest, a Futures Testnet BNBUSDT draft with lower price, upper price and capital empty. The Replay chart was empty on pyqtgraph's default axes (x 00.050…00.800, crosshair at 1970-01-01), Run was disabled ("The parameters are refused…"), and `missing_candles`'s Sync offer appears only after a Run (`backtest_workbench_presenter.py` → `_state` at 284a5aa read `refusal.missing_candles` or a result's missing count), so the owner could neither see the price history nor fetch it while designing the grid. `BotChart` already has an empty-chart sentence (`EmptyChartNotice`, `EPIC-034A`) but only for a chart that shows a symbol; the workbench draws handed candles (`draw_history`), which clears it.

## 2. Acceptance criteria
- [x] Opening the tab with a bot followed, and changing the interval or the period, draws the stored candles of the bot's own venue (`BUG-172`) for that window with no grid parameters set and no run.
- [x] When the window's candles are missing or partly stored, a visible **Sync candles** fetches them through the existing sync, off the UI thread and fenced, then draws them (and does not run a backtest); a sync a run's refusal offered still runs it again.
- [x] An empty chart shows a sentence (no bot, reading, none stored, unreadable), never the 1970 axis.
- [x] A window over `MAX_CANDLES` (20,000) is not read and says so with the remedy (shorter period or larger interval); the bound is the Run's own.
- [x] A result keeps the chart until the next run replaces it.

## 3. Design
`GetStoredCandlesQuery` (bots application, a read) returns `StoredCandles`: the candles, the closed candles the period holds (`closed_candles`, the replay's own count, made public), how many are stored, `MAX_CANDLES` and `too_many`. `CandlePreview` runs it on the thread manager with its own `ActionOwnershipTracker`: one read at a time, a new window supersedes the one in flight, a stale answer is dropped and logged (`async-ui-action-rule.md` §1). It is apart from the run's one-action tracker because a read is cheap and the interval may change many times; Sync reuses the run's tracker and `BacktestRunCoordinator.start_sync`. `CandleDrawing` decides what the chart and the line under the commands show from the preview (`candle_preview_words.py`, one pure function so the two cannot disagree); `sync_offer.py` says what the next Sync fetches and whether a run follows. `BotChart.say_empty` is the existing notice made callable. The presenter was 399 lines: `_show_outcome` moved to `outcome_shown.py`, the request build to `workbench_selection.py` → `request_of`, the candle drawing to `candle_drawing.py`.

The preview refuses a period by its *expected* candle count, where a Run refuses by the *stored* count: with 25,000 expected and 100 stored, Run would replay the 100, but a full sync would make Run refuse, so the preview says it before the person syncs (review of `BOT-233`, optional C; kept on purpose). A run's sync offer decides what Sync fetches only while the window it ran is the one on screen (`sync_offer.py` → `sync_plan`); a result keeps the chart after the window changes, and the line under the commands describes the new window (optional D, as the SPEC says).

## 3a. Reuse
`BacktestRunCoordinator.start_sync` and `IMarketDataSync` (the sync), `EmptyChartNotice` (the sentence), `BotChart.draw_history`, `ActionOwnershipTracker`, the run's `MAX_CANDLES`: used. A parallel fetch path: not built.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/queries/get_stored_candles/` | the query, its result and handler; bound in `composition/query_bindings.py` |
| `src/modules/bots/domain/grid/grid_simulator.py` | `closed_candles` public |
| `src/modules/bots/ui/backtest_workbench/candle_preview.py`, `candle_drawing.py`, `candle_preview_words.py`, `candle_window.py`, `sync_offer.py`, `outcome_shown.py` | the preview, its drawing, words, window, sync offer, outcome build |
| `.../backtest_workbench_presenter.py`, `_view.py`, `workbench_state.py`, `workbench_words.py`, `workbench_selection.py`, `backtest_workbench.py` | wiring, `window_changed`, the candles line, `WorkbenchPorts.read_candles` |
| `src/modules/bots/ui/chart/bot_chart.py`, `bots_screen/bots_dependencies.py`, `kinds/grid/backtest/workbench_frames.py` | `say_empty`, the host binding, the frame's sample read |

## 5. Testing
Unit: `test_get_stored_candles.py` (venue, interval, gaps, bound), `test_workbench_stored_candles.py` (no-bot sentence; draw on follow with no run; interval change; longer period; over the bound; sync stores and draws without a run; a result keeps the chart; a stale read dropped; a failed read told once); integration: `test_the_stored_candles_of_a_period_are_read_from_the_real_shards_with_no_grid` (real SQLite). `test_stop_during_a_sync_says_what_it_stored_stays` now also expects Sync candles, because nothing was stored and the offer stands.

## 6. Docs touched
`Docs/MODULES/bots/05-building-blocks.md` (workbench), `Docs/MODULES/bots/06-runtime.md` (the read and its fence), `Docs/SPEC/SPEC-014_run_a_grid_bot.md` step 9.

## Implementation notes (written when done)
Pending the PR's `-Full` run and review.
