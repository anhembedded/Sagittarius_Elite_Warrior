# BUG-128 — the time-range picker opens on an inverted range and lets you Apply it

- **Status:** ✅ Fixed, `EPIC-025` PR 4.3d
- **Severity:** medium — no crash, no data loss; a backtest or a sync silently covers nothing
- **Found by:** a regression test written while porting the picker off QML, not by a user
- **Case study:** [`CS-004`](../../../Docs/CASE_STUDIES/CS-004_the_tests_the_gate_never_ran.md)

## 1. Symptom

A screen whose stored range has start **after** end — an abandoned edit, or a field written
before the other — opens the time-range picker on that inverted pair. The dialog shows
`08 Jul → 01 Jul`, the summary computes a negative span as `0 days`, **Apply is enabled**, and
the applied window is one the backend reads as empty: no candles to sync, no candles to backtest,
and nothing on screen saying why.

## 2. Root cause

`TimeRangePickerVM.refresh()`:

```python
if start is None or end is None or start > end:
    end = end or now
    start = start or (end - timedelta(days=_FALLBACK_DAYS))
```

The condition names **three** states. The two lines under it repair the first two: a missing end
becomes `now`, a missing start becomes a week earlier. For the third — both present, inverted —
both values are non-`None`, so both `or`s keep what they had and the function returns the inverted
pair unchanged.

So the guard detected the state and declined to repair it. It is not a missing check; it is a
check whose remedy did not cover the case it tested for.

`can_apply` could not catch it downstream either: it asks whether both ends are *present*, which
an inverted pair satisfies. Ordering was never its question at **either** end of the pair's life,
and that is the second half of the defect — see §4.

## 3. Why the gate was green — and the case study

`TimeRangePickerVM` had 13 unit tests, one of which covered the *unparseable* branch of that very
condition. They lived at `src/presentation/ui/qml/TimeRangePicker/tests/`, and the gate runs
`pytest Sagittarius_Elite_Warrior/tests` — so **no run has ever collected them**. PR 1.4b-2 found
that hole and counted twenty such files; this is the first time it cost something. Five nets and
why each looked away: [`CS-004`](../../../Docs/CASE_STUDIES/CS-004_the_tests_the_gate_never_ran.md).

## 4. The fix — two places, because the pair has two producers

**The seed.** `seed_range()` in `src/support/ui_kit/time_range_picker/range_rules.py` —
**three explicit branches** rather than one condition plus fallbacks, because the defect *was* a
fallback that missed the case its condition named:

1. both present and ordered → unchanged;
2. both present, inverted → keep the end (the more recent edit in every flow that produces this)
   and re-derive the start a week back;
3. anything missing → fill from `now` and a week back.

**The user's own clicks.** Fixing only the seed would have left the same symptom one click away,
which is `fix-bug-rule` §2's "fix the mechanism, not the reported call site": two calendars let a
user pick a From date after the To date, and `can_apply` said yes for exactly the reason it said
yes to the seeded pair. It now requires both ends *and* their order, so Apply greys out, and
`build_summary` words that state — *"The end is before the start"* — instead of clamping the
negative span to `0 days`, which read as a legitimate single instant. The user recovers by moving
the other end, with no reopen.

Found in this pull request's own review, not after it shipped: the dialog's test file said two
calendars "cannot" reach an invalid state, which was true of the state the *previous* picker could
reach and false of the one this shape introduces.

## 5. The regression test, confirmed red first

`test_range_rules.py::test_an_inverted_pair_from_the_host_is_replaced` — written before the fix,
run, and **failed** returning `2026-07-08 → 2026-07-01`; green after. Two more cover the clicked
path: `test_an_inverted_pair_cannot_be_applied`, and
`test_time_range_picker_dialog.py::test_clicking_a_start_after_the_end_refuses_to_apply_and_says_why`,
which drives `QCalendarWidget.clicked` — the signal a real click emits — so deleting the
connection in `_calendar()` makes it fail (verified by breaking that line and running: exactly one
failure). They are 3 of 23 in a suite the gate does run, which is the other half of the fix: the
rules had coverage the gate could not see, and now they have coverage it can.

## 6. The check that closes the class

`tests/unit/architecture/test_no_test_file_lives_under_src.py` — no `test_*.py`, `*_test.py` or
`conftest.py` under `src/`, against a shrink-only baseline of the 22 that remain. A new one fails
the moment it is written; the 22 are inside QML packages ADR D21 deletes over PR 4.3's remaining
steps, and the list reaches zero with the last `.qml`.
