# BOT-214 — The picker's dialog refuses to unpin the last interval (EPIC-040 F4)

**Status:** ✅ Done (2026-10-21)
**Board:** Unticking the last pin in the interval picker is refused, and the dialog says why; the row always keeps one interval. Decided by the coordinator for the owner, 2026-10-20 ("bạn tự quyết"). Residual: the pinned interval need not be the one chosen (the frame shows 1h pinned, 15m current).
**Source:** the delivery coordinator (session_016sGQHsRy729Fp4cY1cTXfu), 2026-10-21: the owner said "OK làm 5 task 1-5 luôn" ("OK, do tasks 1 to 5 now"); item 1 is the follow-up F4 of [EPIC-040](../epics/EPIC-040_backtest_workbench/README.md), found in PR #642's review.
**Risk:** 🟢 — a policy that is off unless a host asks
**Complexity:** S — one value object, three small edits
**Epic (optional):** [EPIC-040](../epics/EPIC-040_backtest_workbench/README.md)
**Depends on:** None

---

## 1. Context and problem
Unpinning every interval in the picker left the interval row with only "More timeframes…" while Run still replayed the chosen interval.

## 2. Acceptance criteria
- [x] With a floor of one, unticking the last pin leaves it pinned (the box is checked again), writes nothing to the host's store and shows the reason in the dialog; any other unpin and any pin work as before.
- [x] Without a floor every pin can go, as every other chart's picker.
- [x] The workbench's interval picker has the floor.

## 3. Design
`PinFloor(count, reason)` is handed to `TimeframeSelection` (through `ChartToolbar(pin_floor=...)`): `toggle_pinned` refuses an unpin at the floor, has the views read again (so the cleared box is checked again) and emits `pin_refused(reason)`, which the dialog shows in `lblTimeframePinFloor` until the next change. A floor of one does not make the pinned interval the chosen one (a person may choose an unpinned interval in More timeframes…, so the row can show 1h pinned while 15m runs); the decision was the last unpin, and keeping the chosen interval pinned would be a further rule for the owner to take.

## 3a. Reuse
`TimeframeSelection`, `TimeframePickerDialog` (the shared picker): used and extended.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/charting/timeframe_picker/selection.py` | `PinFloor`, `pin_refused`, the refusal |
| `src/support/charting/timeframe_picker/dialog.py` | the reason label |
| `src/support/charting/chart_card/chart_toolbar.py` | `pin_floor` parameter |
| `src/modules/bots/ui/backtest_workbench/backtest_workbench_view.py` | the interval toolbar's floor |

## 5. Testing
`test_selection.py` (three cases), `test_dialog_and_timeframe_actions.py` (the box is checked again and the reason shown, then hidden), `test_workbench_interval.py`; mutated red (the comparison, the re-read).

## 6. Docs touched
`Docs/MODULES/bots/05-building-blocks.md`, `Docs/SPEC/SPEC-014_run_a_grid_bot.md` step 9.

## Implementation notes
Delivered with BOT-211 to BOT-214 in one pull request (`EPIC-040` follow-ups F1 to F4). Frames: the CI artifact `ui-screenshots` of the `-Full` run, `bots~*` files (see the pull request).
