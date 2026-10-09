# EPIC-038F — `preflight`: the machine is checked before the first order, not after the first rejection

**Status:** 🔵 Planned — not started
**Source:** the owner, 2026-10-09; the brief: *a preflight command — clock skew against Binance server time, key permissions, IP, disk space.*
**Risk:** 🟡 — it contacts an exchange (read-only requests) and judges key permissions; a false PASS is worse than none
**Complexity:** M — a runner, a registry hook, eight checks, a report
**Epic:** [EPIC-038](../README.md)
**SPEC:** [SPEC-003](../../../../Docs/SPEC/SPEC-003_check_the_exchange_connection.md) is the nearest journey (`exchange-status`); SPEC-015 (new, 038D) lists `preflight`.
**Design:** [DESIGN §4.1, §12](../DESIGN_2026-10-09_headless_operation.md) · **Research:** [§5, §6, §9, §15](../RESEARCH_2026-10-09_headless_operation.md)
**Depends on:** [038B](EPIC-038B_exit_codes_and_output_formats.md) (reports and exit codes). Reuses `IAccountSnapshot.check_connection()` and `ConnectionStatus.server_time_skew_ms`.

---

## 1. Context and problem
`exchange-status` already checks signature, clock skew, balance and position mode for the Futures Testnet and prints the skew (`exchange_status_formatter.py:38,145`; failure kind `CLOCK_SKEW`). Operators' VPS failures are earlier and plainer: no time sync (`-1021`), a key restricted to an address the VPS does not use (`-2015`, one message for three causes), a key that can withdraw, a full disk that breaks writes while the network works (R5, R6, R9). Nothing checks them together before a bot starts.

## 2. Acceptance criteria
- [ ] `preflight [--venue …] [--json] [--skip …]` runs every registered `IPreflightCheck` and prints PASS/WARN/FAIL with a plain-language reason and a remedy each; exit 0 when none fails, 4 when any FAIL, 5 when credentials are absent, 6 when the exchange is unreachable.
- [ ] `ClockSkewCheck`: reads the exchange's server time through the existing connection check and compares it with the local clock; WARN above 500 ms, FAIL at or above 1000 ms (Binance rejects a timestamp more than 1000 ms ahead of its server time, R5); the remedy names `timedatectl status`/`chronyc tracking` on Linux and `w32tm /query /status` on Windows, and says raising `recvWindow` is not a fix.
- [ ] `CredentialsPresentCheck`: for each venue a bot uses (or `--venue`), reports which source the key came from (environment, systemd credential, file, keyring) — never the value.
- [ ] `KeyPermissionsCheck` and `NoWithdrawPermissionCheck`: read the key's permissions back from the exchange; trading allowed is PASS for a trading venue; **withdrawal enabled is FAIL** with the remedy "create a key without withdrawal" (R4).
- [ ] `OutboundAddressCheck`: reports the address the exchange sees, over the IP family the client uses, and, when the exchange answers `-2015`, prints the three-cause checklist (key, address, permissions) instead of the bare code; it says the restriction is per address (R6).
- [ ] `DiskSpaceCheck` (data root and the log directory; WARN below 1 GiB or 10%, FAIL below 100 MiB), `DataRootWritableCheck` (writes and removes a probe file), `PythonFloorCheck` (the runtime is at or above the supported floor).
- [ ] Every check is isolated: one that raises becomes a FAIL named for the check, and the others still run; a check has a deadline.
- [ ] A new check added by a test-only module through `declare_operations` appears in the report with **no** edit to `PreflightRunner`.
- [ ] `run` runs preflight by default and refuses on FAIL (exit 4) unless `--skip-preflight` is given.
- [ ] All tests use the fake exchange and a fake clock; nothing contacts a real exchange.

## 3. Design
Chain of independent checks collected through the operations registry (the contribution pattern of `declare_cli`); the module that knows a thing owns its check (trading owns the key and the skew, operations owns disk and Python) so operations does not import trading. Results are values (`CheckResult`), rendered by the `Report` of 038B.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/operations/application/preflight_runner.py`, `contracts/i_preflight_check.py` (new) | the runner and the port |
| `src/modules/operations/adapters/` (new) | disk, data root, Python checks |
| `src/modules/trading/adapters/` (new) | clock-skew, credentials, key-permission, withdraw, outbound-address checks, declared by `TradingModule` |
| `src/modules/operations/cli/preflight_cli_handler.py`, `src/config/cli_commands.json` | the command |

## 5. Testing
Tier: unit with the fake exchange (skew, permissions, an error code injectable).
- `test_skew_of_600ms_warns_and_1200ms_fails` · `test_a_withdraw_enabled_key_fails` · `test_error_2015_prints_the_three_cause_checklist`
- `test_a_check_that_raises_is_a_fail_and_the_rest_still_run` · `test_a_slow_check_is_cut_off`
- `test_a_new_check_appears_without_editing_the_runner`
- `test_no_secret_value_appears_in_the_report`
- `test_run_refuses_to_start_when_preflight_fails_and_not_when_skipped`
Not run yet.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: confirm which request returns the key's permissions on each venue (the exchange's account-permission endpoint), against the fake first.
