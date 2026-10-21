# BOT-212 — A conformance case with a backtestable bot selected (EPIC-040 F2)

**Status:** ✅ Done (2026-10-21)
**Board:** The Bots mode is now measured with a Grid bot selected, on its Live and Backtest tabs at 1024×700, 1366×768 and 1920×1080 (menus, toolbars, scroll areas, size), with frames; it would have caught F1. Found by it, not fixed here: the Bots table, the Ladder and the venue combo run past their edges at some sizes ([BUG-245](../bug_report/incomplete/BUG-245_with_a_bot_selected_the_bots_table_the_ladder_and_the_venue_combo_run_past_their_edges.md)) and the Backtest setup column overlaps its text ([BUG-246](../bug_report/incomplete/BUG-246_the_backtest_tabs_setup_column_draws_its_text_over_itself_at_1024x700_and_1366x768.md)).
**Source:** the delivery coordinator (session_016sGQHsRy729Fp4cY1cTXfu), 2026-10-21: the owner said "OK làm 5 task 1-5 luôn" ("OK, do tasks 1 to 5 now"); item 1 is the follow-up F2 of [EPIC-040](../epics/EPIC-040_backtest_workbench/README.md), found in PR #642's review.
**Risk:** 🟢 — a test and its pictures; no product code
**Complexity:** M — a booted app with the fake exchange, a created and selected bot, two tabs, three sizes
**Epic (optional):** [EPIC-040](../epics/EPIC-040_backtest_workbench/README.md)
**Depends on:** None

---

## 1. Context and problem
`test_workbench_conformance.py` measures the Bots mode with no bot selected, so the workbench page (built on `follow()` with a bot) and its toolbars were in no check; the missing "More timeframes…" command (F1) went unseen.

## 2. Acceptance criteria
- [x] A booted app (Spot Testnet on the fake server) has a Grid bot created through the application's command and selected as a click would; both centre tabs are measured at the three window sizes of the suite.
- [x] The case measures menus (access keys, separators, mnemonics), toolbars (actions only, each in a menu, reading as its menu item, no button repeating a command), scroll areas and the window's fit, ratcheted by `baseline_workbench_conformance.json` (`failing_with_a_bot`, empty).
- [x] Each tab at each size is saved as a frame; View → Chart in front of each tab and the interval picker after its last pin was unticked are saved too.

## 3. Design
The case is `test_trade_mode_conformance.py`'s shape over the same boot (`trade_mode_running`), with a bot made through `ICommandDispatcher` and selected through the view model's `select_requested`, waited on by `qtbot.waitUntil`. It measures the checks the item names and leaves out the tables' column and combo-text checks: with a bot selected the Bots table, the Ladder and the venue combo run past their edges at some sizes (found at the case's first run), a defect of its own, and a column's width depends on the machine's font, which a ratchet read on two machines must not. The baseline gains a section of its own. The left-out checks are not baselined and not expected failures: they name `BUG-245` in `_NOT_YET_MEASURED`, and a test per check fails the day that report leaves `incomplete/`, so the checks come in with the fix. The case keeps its bots in its own data root, per test (`SEW_DATA_ROOT`).

## 3a. Reuse
`trade_mode_running`, `MODE_CHECKS`, `ratchet_problems`, `WINDOW_SIZES`, the screenshot directory convention (`SEW_UI_SCREENSHOTS`): used. No widget is built.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/integration/presentation/ui/test_bots_mode_with_a_bot_conformance.py` | new: the case, the frames |
| `tests/integration/presentation/ui/baseline_workbench_conformance.json` | `failing_with_a_bot` |

## 5. Testing
The case is the test; with `chart_commands` removed from the Bots contribution it fails (checked).

## 6. Docs touched
none, because it adds a test only; the findings below are for the coordinator.

## Implementation notes
Delivered with BOT-211 to BOT-214 in one pull request (`EPIC-040` follow-ups F1 to F4). Frames: the CI artifact `ui-screenshots` of the `-Full` run, `bots~*` files (see the pull request).
