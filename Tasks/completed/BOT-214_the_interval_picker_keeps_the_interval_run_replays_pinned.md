# BOT-214 — The interval picker keeps the interval Run replays pinned (EPIC-040 F4)

**Status:** ✅ Done (2026-10-21)
**Board:** The interval Run replays is always on the interval row: choosing an interval pins it and the picker's dialog refuses to unpin it, saying why. Decided by the coordinator for the owner, 2026-10-20 ("bạn tự quyết"): refuse the last unpin; widened 2026-10-21 by the coordinator for the owner after review: the chosen interval stays pinned, because refusing the last pin alone left the row showing an unchecked `1h` while Run replayed 15m.
**Source:** the delivery coordinator (session_016sGQHsRy729Fp4cY1cTXfu), 2026-10-21: the owner said "OK làm 5 task 1-5 luôn" ("OK, do tasks 1 to 5 now"); item 1 is the follow-up F4 of [EPIC-040](../epics/EPIC-040_backtest_workbench/README.md), found in PR #642's review.
**Risk:** 🟢 — a policy that is off unless a host asks
**Complexity:** S — one value object, three small edits
**Epic (optional):** [EPIC-040](../epics/EPIC-040_backtest_workbench/README.md)
**Depends on:** None

---

## 1. Context and problem
Unpinning every interval in the picker left the interval row with only "More timeframes…" while Run still replayed the chosen interval. The first version refused the last unpin; the review of round 1 showed that this still left the row without the interval Run replays (pins `1h` only, chosen `15m`), the very defect, with a text that said the opposite.

## 2. Acceptance criteria
- [x] Under the rule, unticking the chosen interval is refused: the box is checked again, nothing is written to the host's store, and the dialog says why until the person's next change.
- [x] Choosing an interval pins it, and a chosen interval the host never pinned is pinned on the first read: the row always shows what Run replays.
- [x] Any other interval can be pinned or unpinned as before; without the rule every pin can go, as in every other chart's picker.
- [x] The workbench's interval picker has the rule.

## 3. Design
`CurrentStaysPinned(reason)` is handed to `TimeframeSelection` (through `ChartToolbar(keep_current_pinned=...)`). `choose`, `set_current` and `refresh` pin the current interval when it is offered and not pinned (written through to the host); `toggle_pinned` refuses to unpin it, has the views read again (so the cleared box is checked again) and emits `pin_refused(reason)`, which the dialog shows in `lblTimeframePinRefusal` until the next change the person makes. Replaces the first version's `PinFloor(count, reason)`, which counted pins and did not protect the interval chosen. The refusal can only be seen by unticking the chosen interval, which is why the frame unticks the others first.

## 3a. Reuse
`TimeframeSelection`, `TimeframePickerDialog` (the shared picker): used and extended.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/charting/timeframe_picker/selection.py` | `CurrentStaysPinned`, `pin_refused`, the refusal and the pinning of the chosen |
| `src/support/charting/timeframe_picker/dialog.py` | the reason label |
| `src/support/charting/chart_card/chart_toolbar.py` | `keep_current_pinned` parameter |
| `src/modules/bots/ui/backtest_workbench/backtest_workbench_view.py` | the interval toolbar's rule |

## 5. Testing
`test_selection.py` (six cases: the chosen cannot go and the reason is told; another pin can go; choosing pins; a chosen interval never pinned is pinned on the first read; the first pinned may go when another is chosen; no rule, every pin can go), `test_dialog_and_timeframe_actions.py` (the box is checked again and the reason shown, then hidden), `test_workbench_interval.py::test_the_row_always_shows_the_interval_run_replays` (asserts the chosen interval is the checked one, not only a count); the conformance case's frame `bots~interval-picker-chosen-pinned@1366x768.png`. Mutated red: the comparison, the re-read, the pinning of the chosen.

## 6. Docs touched
`Docs/MODULES/bots/05-building-blocks.md`, `Docs/SPEC/SPEC-014_run_a_grid_bot.md` step 9.

## Implementation notes
Delivered with BOT-211 to BOT-214 in one pull request (`EPIC-040` follow-ups F1 to F4). Frames: the CI artifact `ui-screenshots` of the `-Full` run, `bots~*` files (see the pull request).
