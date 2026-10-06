# BUG-152 — A green gate's log ends with "ResourceWarning: gc: 5 uncollectable objects at shutdown"

- **Reported:** 2026-10-06 (the CI timing measurement for the user, reading the green `ci-local.ps1 -Full` run of PR #372)
- **Severity:** 🟢 P3 — no test fails, but `ci-rule.md` §1's prescribed grep for `ResourceWarning` matches on every green run, so the grep can no longer tell a new leak from this one
- **Status:** Open
- **Context:** The sanity tier's process (`tests/sanity/`) → interpreter shutdown → objects the garbage collector cannot free; owning module Not yet established
- **Environment:** GitHub Actions `ubuntu-24.04`, Python 3.12.14, run 37409274117 (job 112093859516) on `3e78162`; the same line in a local sanity run in the cloud container on the same day.

## Reproduction
1. Run the gate, or the sanity tier alone: `pwsh -NoProfile -File scripts/ci-local.ps1 -Full`, or `PYTHONPATH=.. QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/sanity -q`.
2. Grep the run's `LOG_FILE` for `ResourceWarning`.

**Expected:** no `ResourceWarning`; the run is green and its log is clean.
**Actual:** the line below, after the sanity tier's summary, on a run whose verdict is `RESULT: PASS`.

**Frequency:** every run seen (CI and local, 2026-10-06). When it began: Not yet established.

## Symptom
From the run's log file (`ci-local-logs` artifact, `logs/ci-local-latest.log`, lines 18884–18889):

```
============================= 38 passed in 44.65s ==============================
gc:0: ResourceWarning: gc: 5 uncollectable objects at shutdown; use gc.set_debug(gc.DEBUG_UNCOLLECTABLE) to list them
  ✅  Tests passed
  ✅  Sanity passed
```

## Root cause
Not yet established. Not investigated.

## Fix
Not started.

## Regression test
Not written.

## Verification
Not run.

## Suggested next steps
- Run the sanity tier with `gc.set_debug(gc.DEBUG_UNCOLLECTABLE)` to list the five objects and their types.
- Decide which test or fixture leaves them: bisect the 38 sanity tests.
- Once it is fixed, the gate's log scan could fail on this line, so the prescribed grep regains its meaning.
