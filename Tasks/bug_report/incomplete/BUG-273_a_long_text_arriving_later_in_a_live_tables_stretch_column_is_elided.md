# BUG-273 — A long text that arrives later in a live table's stretch column is elided

- **Reported:** 2026-10-27 (found in the review of [BUG-272](BUG-272_a_live_table_row_longer_than_the_first_batch_is_elided_in_its_column.md); filed at the owner's instruction to be done later)
- **Severity:** 🟢 P3 — a long handler failure text in the Developer log's `Outcome` column can be cut off on screen; nothing is lost in the log file and no trading behaviour is affected.
- **Status:** Open
- **Board:** In a live table fed by inserts, the stretch column (`Outcome` in the Developer log) keeps the Engine's width floor measured at configure, reset and first rows, so a longer text arriving later stays elided; BUG-272 widens the other columns and leaves this one to the Engine.
- **Context:** Developer mode → `src/shell/developer_mode/` and `src/support/ui_kit/` (`SpecTable`, `InsertedRowsColumnGrowth`) → the Engine's `_FirstRowsFitter` and `StretchColumnFiller` (Engine repository, `extensions/pyside_mvc`)
- **Environment:** App at `master-warrior` after BUG-272's fix; Linux, offscreen probe by the BUG-272 reviewer; the Engine at the `engine.ref` pin. Not seen by a person yet.

## Reproduction
Established by the BUG-272 reviewer's probe, not by a user: the Developer log at 700 px wide, then a row whose `Outcome` needs 600 px. After the event loop turns, `Outcome` is 432 px, and after the window narrows it is 132 px, with or without the BUG-272 helper. A real source of such a row is a handler failure text (`failed in <handler>: <exc>: <message>`) arriving after boot. Not yet reproduced with a real failure.

## Symptom
The text in `Outcome` ends with an ellipsis although the column could show it whole. Expected: a later, wider row widens the stretch column as it does the other columns.

## Root cause
Not yet fixed. From the BUG-272 review (Engine read at the `engine.ref` pin): `StretchColumnFiller` sizes the stretch column from a floor it re-measures only on configure, reset and first rows, and its `fill()` on the next viewport `Resize` or `Show` puts the width back to `max(stale floor, viewport − others)`. The app cannot raise that private floor, and `_FirstRowsFitter.on_rows_inserted` fits only when an insert fills an empty model. This is the Engine's documented policy (it removed per-insert measuring on purpose, Engine PR #230), so the mechanism belongs to the Engine.

## Fix
Pending.

## Regression test
Pending: a shown table whose stretch column holds a later, wider row must show it whole after a resize.

## Verification
Not run.

## Suggested next steps
An Engine pull request that moves the grow-only fit, the stretch column included, into `_FirstRowsFitter` and `StretchColumnFiller`; `InsertedRowsColumnGrowth` then retires (its `Retire when:` line). It needs the owner's explicit confirmation first (`ONBOARDING.md` §2: an Engine change is a separate commit and push). Not scheduled; the owner said "later".
