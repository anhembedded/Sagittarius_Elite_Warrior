# EPIC-034G — The chart states whether it is live, and the user starts and stops it

**Status:** ✅ Done (2026-10-07)
**Source:** the owner, 2026-10-07 — *"bot không start được tui cũng không biết nó đang thiếu gì"* (the bot does not start and I cannot tell what it lacks); the epic's origin has the rest.
**Risk:** 🟡 — the shared chart used by Market, Desk, Backtest and Bots
**Complexity:** M — one FSM and its commands
**Epic:** [EPIC-034](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** [EPIC-034A](../incomplete/EPIC-034A_bots_mode_says_what_it_knows.md)

---

## 1. Context and problem
The bot chart goes live only for a started bot (`src/modules/bots/ui/bots_screen/bot_chart_host.py:43,108-110`); the toolbar's "Go live" only scrolls to the newest candle (`viewport_controller.py:28-33`). Nothing tells the user whether candles are arriving.

## 2. Acceptance criteria
- [x] The shared live chart has four states in one `*_fsm_matrix.py`: History, Connecting, Live, Error; each shows a chip with its words (Error with the reason) and the matching command: Go live, Cancel, Stop live, Retry. — `live_chart_fsm_matrix.py`; `test_live_chart_fsm_matrix.py` writes the whole table out a second time, and `test_live_candle_chart_state.py` drives a real `LiveCandleChart` through each command and reads the chip.
- [x] In the Bots mode the chart can go live for a draft bot after Connect (D9); a running bot's chart is Live by itself. — `test_bot_chart_live_state.py`: a draft's chip goes live and draws what streams, Stop live releases only `bot.<id>`, a running bot is Live with one stream. **Deferred, with its reason:** the gate "after Connect" is not here, because the Connect step is `EPIC-034D`, not yet merged; today a draft's Go live is always offered, and `EPIC-034D` disables the command until the account is read.
- [x] Live reports the age of the last update. — `age_text`, refreshed every second by the chip's timer while Live; the clock is injected (`LiveChartPorts.clock`), so the test moves it.
- [x] Market, Desk and Backtest use the same state and commands, or the task records why one does not. — Market and Desk need no wiring: both are `LiveCandleChart`s and show the chip (`test_market_chart_live_state.py`, `test_desk_chart_live_state.py`). Backtest does not: the Backtest mode's chart is a plain `ChartCard` that draws a recorded run and never streams, and the Grid backtest page's `BotChart` passes `live_commands=False` for the same reason (a stream would replace the run's candles).

## 3. Design
The FSM wraps the existing `LiveChartCoordinator` sync-then-stream sequence; it is a view of that lifecycle, not a second one. Decisions: [DECISION_2026-10-07_bots_mode_flow.md](../DECISION_2026-10-07_bots_mode_flow.md).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/charting/live_chart/` | the FSM and its commands |
| the chart's hosts | wired |

## 5. Testing
An FSM table test; presenter tests per host; a desktop E2E picture of each state. A reviewer is required. The desktop E2E picture is **not run**: this session has no windowing display.

## Implementation notes (written when done)
- **The FSM is a view, not a second lifecycle.** `LiveCandleChart` dispatches an event when it asks the coordinator for something (`GO_LIVE_REQUESTED`, `LOAD_RESTARTED`) and when the coordinator reports back (`STREAM_STARTED`, `STREAM_FAILED`, through two private Qt signals, so the state moves on the Qt thread). `LiveChartCoordinator` is unchanged but for one log line that said "enable trading to connect". An event the table does not declare for a state is dropped, which is what keeps a report that was already queued when the user cancelled from moving the chart.
- **Residual race, accepted:** a `stream_started` queued before Cancel, then a second Go live before it is delivered, would read Live a moment early; the new request's own report corrects it. Closing it needs the token on the coordinator's callbacks.
- **The chip** (`live_state_chip.py`) is a label with the state's words plus a `QToolButton` showing one `QAction`, added to the chart card's header and to the plot's context menu. Error writes its reason in the label (60 characters) and whole in the tooltip; Live writes `updated N s ago`.
- **Naming:** the viewport's "Go live", which only scrolls to the newest candle, is now "Follow latest" (`follow_latest`, `FOLLOW_LATEST`, `act_followLatest`). "Go live" means the stream.
- **D9 mechanism:** `BotChart.attach_ticks` listens to the bots' one tick feed from the moment the host builds the chart, so a draft that goes live draws what streams; a chart in History draws no live candle, whoever else streams the symbol.
- **Not done, recorded:** the chip's command is not in the menu bar, and the context menu repeats it (`ui-presentation-rule.md` §6, review H3). A menu entry whose words change with the state needs `ActionMirror` to mirror text, and one per mode (Trade, Market, Bots); that is a follow-up. Keyboard reach today is the tool button's focus.
- **Pre-existing, not from this change:** `test_workbench_conformance[True-1024x700]` fails on `master-warrior` in this container (the Backtest mode needs 719x706 at 1024x700), identically with and without these edits.
- Mutation checks: dropping the failure dispatch, the age clock, the History gate in `BotChart`, `live_commands` and the release on Cancel/Stop each turned a test red; a mutant that kept the previous age across a symbol change survived until `test_a_new_symbol_starts_the_age_again`.
