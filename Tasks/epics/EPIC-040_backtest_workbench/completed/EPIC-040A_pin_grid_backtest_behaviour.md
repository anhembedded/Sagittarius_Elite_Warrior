# EPIC-040A — The Grid's backtest page is pinned by tests and preview frames before anything moves

**Status:** ✅ Done (2026-10-20)
**Source:** The owner, 2026-10-14: *"Bạn tạo epic luôn, viết từng task, đánh giá design từng task"* ("create the epic, write each task, assess each task's design")
**Risk:** 🟢 — tests and preview frames only; no product code changes
**Complexity:** S — the page's states are few and already named in its presenter
**Epic:** [EPIC-040](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** None

---

## 1. Context and problem
The Grid's backtest page (`src/modules/bots/ui/kinds/grid/backtest/`, 8 files, about 1,190 lines) is about to be split across a kind-neutral workbench (040D) and a Grid adapter (040F). The 039B oracle pins the simulator's figures, but nothing pins what the page shows in each state:
- idle with a reason;
- running and Cancel;
- refused for missing candles, with Sync offered;
- refused for missing funding, with "Run without funding" offered;
- a Spot result and a Futures result with its funding and liquidation lines;
- cancelled;
- a different bot selected mid-run.

Without that pin, 040F can lose a state silently.

## 2. Acceptance criteria
- [ ] Each state above has a presenter-level test that drives the real presenter and view on the fake exchange's candles and asserts the visible words and which buttons are enabled.
- [ ] `preview.py` gains one frame per state (Spot and Futures), so the owner can compare before and after.
- [ ] Each test is shown to fail when its state's wording or button state is changed (mutation note in the implementation notes).

## 3. Design
**Characterisation tests first** (Feathers' "pin before you move"). They test behaviour at the page's public surface (the presenter's inputs, the view's visible text and actions), never private methods, so they survive 040F's move unchanged. That is the whole value of this task.

**Design assessment**

| Option | Verdict |
| :--- | :--- |
| Pin at the presenter/view surface (chosen) | Survives the move. 040F runs the same tests against the workbench-hosted page. |
| Pin with screenshot diffs | Rejected: brittle across fonts and platforms; the conformance suite already guards layout. |
| Skip and rely on the oracle | Rejected: the oracle covers numbers, not states, and the states are where 039J and 039K added behaviour (funding refusal, brackets wait). |

**Risk:** low. The only trap is testing through private helpers, which would tie the tests to the code 040F deletes. Review check: tests import only the presenter, the view's public names and the preview frames.

## 3a. Reuse
- **Test fixtures:** none of its own. The tests read the frames, and a frame drives the real `GridBacktest` over a scripted query, the market-data `FakeMarketDataSync` and `SampleCandleFeed`. The grid fake exchange of the task text is not used: a backtest never talks to an exchange. The `preview_frames.py` pattern is `EPIC-039J`'s (`bots_screen/preview_frames.py`).
- **Application code:** none, because the task only adds tests and preview frames.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/unit/modules/bots/ui/kinds/test_grid_backtest_states.py` | New: one test per state (re-scoped path: the page's tests live flat in `kinds/`) |
| `src/modules/bots/ui/kinds/grid/backtest/preview_frames.py` | New: one frame per state, the `EPIC-039J` pattern (a frame table beside `preview.py`, which stays the Spot result) |
| `src/modules/bots/ui/kinds/grid/backtest/preview.py` | Its sample's constants lose their leading underscore so the frames reuse them |

## 5. Testing
Unit tier (presenter and view with a real Qt widget, offscreen). Each criterion maps to one test; mutation checks recorded. The commit tier and the architecture suite also run.

## Re-check against master (2026-10-20, `0ccc921`)
The design held. What had moved since 2026-10-14:
- **Most states were already pinned.** `test_grid_backtest.py`, `test_grid_backtest_on_futures.py` and `test_grid_backtest_summary.py` already cover Run, Cancel, another bot, the sync offer, the funding refusal and the Futures summary rows, but by one assertion each, never the page's whole state. What was missing: the full button matrix per state, the running and syncing words, and a Futures result and a liquidation shown *through the page*. Those are what this task added.
- **EPIC-039, EPIC-042, BOT-202 and the strict fake exchange change nothing here.** The page never reads the account or the exchange, so `EPIC-037E` does not reach it; `EPIC-039`'s venue profile is already in the presenter (`venue_profile_of`, `plan_market_of`).
- **The test path.** The tests live flat under `tests/unit/modules/bots/ui/kinds/`, not in a `grid/backtest/` folder.

## Implementation notes
**What shipped.** `preview_frames.py` holds twelve frames of the real page (`idle_no_bot`, `idle_no_market_numbers`, `idle_ready`, `running`, `syncing`, `refused_candles`, `refused_funding`, `spot_result`, `futures_result`, `futures_liquidated`, `cancelled`, `another_bot`). Each is built by `follow` and a click on the page's own buttons over a scripted query and a held thread pool, so every sentence is the presenter's. `test_grid_backtest_states.py` reads each frame's status words and which commands are on. The Futures frames replay five minute candles through `FuturesReplay`, the engine the application composes, so the funding and liquidation lines are the summary's, not written for the frame. Run one with `python -m Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.preview_frames <frame> [--png path]`. No product behaviour changed.

**Surface only.** The tests import the frames and the view's public names (`run_button`, `status`, `summary_text()`, …); no presenter, coordinator or helper. `040F` runs the same file against the workbench-hosted page by changing what `FRAMES` builds.

**Mutation checks (each went red, then restored).** `Stop`→`Cancel` on a sync (one test); Run left off after a refusal (ten); the running sentence reworded (one); the "Run without funding" offer dropped (one); the cancelled sentence reworded (one); the result kept when another bot is selected (one).

**Findings for `040F`, not fixed here (this task changes no behaviour).**
- `GridBacktestView.show_idle("")` writes the status only when it has a reason. So after another bot is selected with no run in flight, the status still reads "Backtest done." while the result is gone, and a page that becomes ready keeps "Select a bot to backtest its parameters.". The tests leave the status of those two states unasserted, on purpose; `040F` fixes the line and pins it.
- Before the first run the result chart reads "No candles are stored for  at 15m." (an empty symbol): the chart is not told the bot's symbol until a result is drawn. Also for `040F`.

**Verified / not.** Commit tier (ruff, format, mypy, reference check), the architecture suite and `tests/unit/modules/bots/ui/kinds` green. Frames rendered offscreen and read as images (`--png`). Not verified: the owner's look at the frames on Windows.
