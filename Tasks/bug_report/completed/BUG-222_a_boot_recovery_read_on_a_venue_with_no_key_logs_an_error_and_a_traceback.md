# BUG-222 — A restored bot's boot report on a venue with no API key logs an ERROR and a full traceback

- **Reported:** 2026-10-15 (the owner's VPS, a headless `bot apply` run with no key outside the unit)
- **Severity:** 🟢 P3 — a missing key is a state the operator fixes, yet the log reads as a failed operation and a scan for `ERROR`/`Traceback` fails on it
- **Status:** ✅ Fixed (2026-10-15)
- **Board:** A RECOVERING bot's boot report dispatched an open-orders read on a venue with no key: the engine dispatcher logged `ERROR GetOpenOrdersQuery failed` and the reader a WARNING with a traceback. Fixed: the reader asks `BotOrderGateway.connection_failure()` first and reports "no API key" at INFO without a request.
- **Context:** Boot recovery of a restored Grid (`EPIC-035C`) → `src/modules/bots/` → `application/kinds/grid/recovery/`
- **Environment:** Linux VPS, headless CLI; the venue Spot Mainnet had no key in the process's environment. Engine at `engine.ref`.

## Reproduction
1. Start a Grid with a key, stop the app with the bot RUNNING.
2. Boot again with no key for that venue (the CLI `bot apply`, any command that boots the writable copy).
3. Expected: the bot is RECOVERING and says the exchange was not read because there is no key. Actual: an `ERROR` line and a traceback.

## Symptom
```
App - ERROR - GetOpenOrdersQuery failed: No Spot credentials configured — cannot sign a trading request.
Traceback ... grid_recovery_reader.py:67 → spot_trading_client.py:236 ValueError
```

## Root cause
`GridRecoveryReader.read` (`grid_recovery_reader.py`) called `gateway.tagged_open_orders()` unconditionally. On a venue with no key `SpotTradingClient._resolve_client` raises `ValueError` (`spot_trading_client.py:236`); the Engine's dispatcher logs every handler exception at ERROR (`sagittarius_engine/kernel/dispatcher.py:72`, not this repository's to change), and the reader's catch-all `except Exception` then logged a WARNING with `exc_info`. The state was knowable without a request (`check_connection()` answers NOT_CONFIGURED locally), so the read should not have been attempted.

## Fix
`BotOrderGateway.connection_failure()` returns the failure kind of the venue's account check. `GridRecoveryReader.read` asks it first and, when the account cannot be read (no key, refused key, clock skew…), returns `RecoveryReport.unreadable_because(<few words>)` after one INFO line. `connect_failure_words.kind_state_words` exposes the existing short sentence by kind.

Whether a plan-apply CLI run should boot recovery at all is a separate decision, not taken here: boot is module-generic (the restart rule is D12) and the report is read-only. With the fix it costs one local answer on a keyed-less host and one account check on a keyed one.

## Regression test
`tests/integration/modules/bots/test_a_boot_recovery_without_a_key_on_the_fake_exchange.py::test_a_recovering_bot_on_a_venue_with_no_key_reports_it_without_an_error` — failed before the fix with `reason_detail` "ValueError; see the log" and the ERROR line above; passes after.

## Verification
Test red before / green after on the composed app and the fake exchange; `ruff`, `ruff format`, `mypy` (the gate's invocation) and `check_skill_prompt_references.py` clean; `tests/unit/modules/bots` and the host start-up integration journeys green. The full gate is the PR's `ci-local.ps1 -Full` run.
