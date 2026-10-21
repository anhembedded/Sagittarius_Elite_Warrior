# BOT-213 — The workbench's result chart hides its own timeframe row (EPIC-040 F3)

**Status:** ✅ Done (2026-10-21)
**Board:** The Replay chart keeps no `1m 5m 15m 1h 1d` row of its own beside the interval picker: the replay is at the interval that was run, and a second chooser changed nothing the person ran (and offered `1d`). Decided by the coordinator for the owner, 2026-10-20 ("bạn tự quyết").
**Source:** the delivery coordinator (session_016sGQHsRy729Fp4cY1cTXfu), 2026-10-21: the owner said "OK làm 5 task 1-5 luôn" ("OK, do tasks 1 to 5 now"); item 1 is the follow-up F3 of [EPIC-040](../epics/EPIC-040_backtest_workbench/README.md), found in PR #642's review.
**Risk:** 🟢 — one toolbar's actions hidden
**Complexity:** S — one method on the shared toolbar and one call
**Epic (optional):** [EPIC-040](../epics/EPIC-040_backtest_workbench/README.md)
**Depends on:** None

---

## 1. Context and problem
The result chart is a `ChartCard`, whose toolbar always carries the pinned timeframes and More timeframes…; beside the workbench's interval picker it is a second chooser that changes nothing the person ran.

## 2. Acceptance criteria
- [x] The workbench's result chart shows no timeframe action and no More timeframes… on its toolbar; its zoom actions stay.
- [x] The row stays hidden when the pinned set changes.

## 3. Design
`ChartToolbar.hide_timeframes()` hides the timeframe actions, More timeframes… and the separator after them, and keeps them as actions, so what asks them by name (`menuEquivalent`) still finds them; it is one-way, as a boolean flag argument that changes behaviour is avoided (`quality.md` §7). `BacktestWorkbenchView` calls it on its card.

## 3a. Reuse
`ChartToolbar` (the shared chart toolbar): used and extended.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/charting/chart_card/chart_toolbar.py` | `hide_timeframes`, re-applied on every rebuild |
| `src/modules/bots/ui/backtest_workbench/backtest_workbench_view.py` | calls it on the result card |

## 5. Testing
`test_workbench_interval.py::test_the_result_chart_has_no_timeframe_row_of_its_own`, `test_chart_toolbar_offered_codes.py` (two cases); mutated red.

## 6. Docs touched
`Docs/MODULES/bots/05-building-blocks.md`, `Docs/SPEC/SPEC-014_run_a_grid_bot.md` step 9.

## Implementation notes
Delivered with BOT-211 to BOT-214 in one pull request (`EPIC-040` follow-ups F1 to F4). Frames: the CI artifact `ui-screenshots` of the `-Full` run, `bots~*` files (see the pull request).
