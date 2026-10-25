# BUG-269 — `test_system_shows_the_machines_own_time` goes red when daylight saving ends

- **Reported:** 2026-10-25 (coordinating session; failing `gate (Unit)` job log of PR #731, `1 failed, 19342 passed`)
- **Severity:** 🟡 P2 — `master-warrior` and every open PR are red on a test, though the product is right
- **Status:** ✅ Fixed (2026-10-25)
- **Board:** Root cause: a test wrote down zone abbreviations (`BST`, `EDT`) that change when daylight saving ends. Fix: the test computes the abbreviation at the moment the label is read; no `src/` change.
- **Context:** Display timezone ("System") → `src/support/ui_kit/services/` → test only
- **Environment:** Linux, Python 3.12, app commit `bfae44f`, sandbox clock 2026-10-25 05:00 UTC (no clock freezing needed)

## Reproduction
1. On any date after 2026-10-25 01:00 UTC: `pytest tests/unit/support/ui_kit/services/test_system_display_timezone.py`.
2. Expected: green. Actual: the `Europe/London` case fails. Reproduced on `bfae44f`.

## Symptom
```
>       assert abbreviation in service.get_display_timezone_label(service.SYSTEM_TIMEZONE_KEY)
E       AssertionError: assert 'BST' in 'System (GMT, UTC+00:00)'
FAILED ...::test_system_shows_the_machines_own_time[Europe/London-2026-10-19 13:01:30-BST]
1 failed, 12 passed
```

## Root cause
`tests/unit/support/ui_kit/services/test_system_display_timezone.py` (parametrize of `test_system_shows_the_machines_own_time`, at `bfae44f`) hard-codes the abbreviation (`+07`, `EDT`, `BST`). `get_display_timezone_label` (`display_timezone_service.py:108`) names the machine's zone as of *now* (`get_system_timezone_name`, line 96, by design: it labels the setting). The shown time uses the fixed instant `_PAUSE_END`; the label does not. The service is right; the test mixed a fixed instant with a calendar-dependent value.

## Fix
Test only: the expected abbreviation is `_machine_in(iana_key)(datetime.now(UTC)).tzname()`, read at the moment the label is. The assertion on the displayed time of `_PAUSE_END` is unchanged.

## Regression test
`tests/unit/support/ui_kit/services/test_system_display_timezone.py::test_system_shows_the_machines_own_time` — red on `bfae44f` for the reason above; green after.

## Verification
- Before: `1 failed, 12 passed` on the real clock (2026-10-25 05:00 UTC), output above.
- After: `13 passed`. Mutation (the label names "UTC" instead of the machine's zone): 3 failed, restored.
- Commit tier `ci-local.ps1 -SkipTests`: `RESULT: PASS`; `tests/unit/architecture`: 1107 passed.
- Defect family: no other test writes down a calendar-dependent value; the other zone assertions use fixed instants with IANA keys or an injected machine (listed in the pull request).
