# BUG-218 — A stream of position reports with new figures postponed the divergence re-read indefinitely, and logged a line for each

- **Reported:** 2026-10-15 (found in the evidence of `BUG-216`: the owner's testnet log held ~20 `re-reading in 5 s` lines in 12 s; split out on the independent review of PR #528)
- **Severity:** 🟡 P2. A real foreign position or mismatch is confirmed by a re-read before the bot halts on it; a busy account could keep that re-read from ever running. Money-safe in the other direction (a halt is never wrongly raised), but the safeguard could be starved.
- **Status:** ✅ Fixed (2026-10-15)
- **Board:** A bot receiving a new pair of position figures with every fill replaced its pending divergence re-read each time, resetting its timer, so the re-read never ran while the reports kept coming (and the log filled with `re-reading in 5 s`). Cause: `GridRiskWatch.on_divergence` replaced `_pending` whenever the figures differed. Fix: one pending re-read, moved by a newer report to at most three recheck delays after the first; only the first report logs at INFO.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → `bots` (`application/kinds/grid/watch/grid_risk_watch.py`)
- **Environment:** `master-warrior` at `94f578a8`, unit tier. Not run on a live exchange.

## Reproduction
1. A Futures bot is RUNNING with a risk watch; `position_recheck_delay` is 5 s.
2. Trading reports a divergence each second with different figures (`cause` is `(derived, exchange)`), for 16 s, with a beat each second.

Expected: the re-read runs. Actual before the fix: it never runs while the reports continue, since each report sets `due_at = now + 5 s`.

## Symptom
```text
19:34:16 .. 19:34:28: ~20 x "position_mismatch ... exchange wins" WARNINGs and ~20 x "re-reading in 5 s before acting"
```

## Root cause
`GridRiskWatch.on_divergence` (`grid_risk_watch.py:123`, before the fix) returned early only for the same `cause`; any other figures replaced `_pending` with `due_at = now + delay`. A stream that never goes quiet therefore pushed the due time forward on every report, and logged at INFO each time.

## Fix
`_Pending` carries `latest_due_at` (the first report's time plus `MAX_RECHECK_DELAYS` = 3 delays); a newer report moves the one pending re-read, never past it (`moved_to`). Only the first report of a pending re-read logs at INFO; the others at DEBUG. The re-read itself (`IPositionRecheck`) is unchanged.

## Regression test
`tests/unit/modules/bots/application/services/test_grid_risk_watch_burst.py`: a run of reports for 16 s is read once, by the third delay (red before: `rechecks == 1` failed; it was never read); only the first of five reports is told at INFO (red before: every line at INFO); a burst that goes quiet is read once after its last report (green before and after: it pins the case the cap must not break).

## Verification
Two of the three tests red on `master-warrior` and all green after; commit tier and `tests/unit/architecture` green (see the pull request). Positive proof: the single `rechecks == 1` in the 16 s run.
