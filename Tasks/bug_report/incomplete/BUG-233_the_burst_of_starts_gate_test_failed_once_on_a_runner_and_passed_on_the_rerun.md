# BUG-233 — `test_a_burst_of_starts_stops_at_the_gate_before_the_exchange_limit` failed once in `gate (Rest)` and passed on the re-run

- **Reported:** 2026-10-19 (the author of PR #585, a red `gate (Rest)` on a diff that does not touch the Futures start path)
- **Severity:** 🟢 P3 — a red gate on an unrelated PR, cleared by one re-run; it costs a CI cycle and trust in a green run. No product behaviour is shown wrong.
- **Status:** Open
- **Board:** The Futures start-burst gate test (`4 <= accepted < 8` over eight starts) failed once on a shared GitHub runner (run 39293995903) and passed on the re-run and three times locally; the cause is not established, the suspect is the one-minute request-weight window.
- **Context:** `Docs/MODULES/bots/` → Module `src/modules/bots/` → test of the venue request-weight gate (`EPIC-029J1b`), `tests/integration/modules/bots/test_many_bots_on_one_venue_cost_on_the_fake_exchange.py`
- **Environment:** GitHub Actions `ubuntu-latest`, Python 3.12, `gate (Rest)` of `ci-local.ps1 -Full`, PR #585 head `c0eeed8` (base `master-warrior` 7401d4b's parent `8d63158`). Locally: Python 3.13, three runs of the file, 16 passed each.

<!-- Follow .claude/rules/create-bug-report-rule.md for filing and closure. -->

## Reproduction
Not yet reproduced. Frequency: 1 failure in the run history seen by this author (one run); the same test passed on the job re-run of the same commit and 3 of 3 times locally.

## Symptom
`gate (Rest)` job 118201651986 of run 39293995903:

```
FAILED Sagittarius_Elite_Warrior/tests/integration/modules/bots/test_many_bots_on_one_venue_cost_on_the_fake_exchange.py::test_a_burst_of_starts_stops_at_the_gate_before_the_exchange_limit - AssertionError: the gate lets about five starts through and refuses the rest
```

The test starts eight Futures bots inside a minute with the real gate (closing at 70% of the exchange's 2,400 weight a minute) and asserts `4 <= accepted < 8`. The accepted count of the failing run was not printed in the grep of the job log (the `MEASURED burst of 8 starts` line is written to the terminal only).

## Root cause
Not yet established. Suspect, unconfirmed: the gate's weight is counted in a one-minute window, so a slow shared runner that spreads the eight starts across a minute boundary lets the window reset and more than seven (or fewer than four) starts be accepted; the assertion bounds the count, not the elapsed time.

## Fix
Pending.

## Regression test
Pending: a deterministic version that drives the gate's clock instead of the wall clock, or an assertion that holds for any placement of the minute boundary.

## Verification
Not run.

## Suggested next steps
- On the next occurrence, keep the `MEASURED` line (`-s`) and the run's wall times for the eight starts.
- Check whether the weight meter's minute window follows the wall clock or an injectable clock (`EPIC-029J1b`).
