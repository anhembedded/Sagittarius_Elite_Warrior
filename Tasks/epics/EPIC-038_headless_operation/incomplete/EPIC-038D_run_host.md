# EPIC-038D — `run`: the app stays up as a service, stops cleanly on a signal, and says how it is

**Status:** 🔵 Planned — not started; waits for the owner's decisions O1, O2 and O8
**Source:** the owner, 2026-10-09 (run bots with no GUI on a VPS); the brief specifies the host: an `IHostedService` that boots, restores bots, runs until SIGTERM/SIGINT (Ctrl+Break on Windows), shuts down cleanly, holds the single-instance lock and logs a periodic health line; what shutdown does to resting orders is the owner's choice.
**Risk:** 🔴 — the code path that decides what happens to money when the process is told to stop, and the one a supervisor restarts in a loop
**Complexity:** L — a host state machine, two signal adapters, two stop policies, a sanity test that signals a real process
**Epic:** [EPIC-038](../README.md)
**SPEC:** SPEC-015 *Run the bots headless* (new, written by this task from `Docs/SPEC/SPEC-000_template.md`); [SPEC-004](../../../../Docs/SPEC/SPEC-004_enable_and_disable_live_trading.md) and [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) are updated if a journey changes.
**Design:** [DESIGN §5.1, §6, §7, §11](../DESIGN_2026-10-09_headless_operation.md) · **Research:** [§1, §2, §3, §7, §8, §10, §13](../RESEARCH_2026-10-09_headless_operation.md) · **Decision:** [O1, O2, O8](../DECISION_2026-10-09_headless_operation.md)
**Depends on:** [038A](EPIC-038A_qt_free_boot_and_guard.md) (Qt-free boot), [038B](EPIC-038B_exit_codes_and_output_formats.md) (exit codes), [038C](EPIC-038C_bot_status_read_model.md) (the snapshot and its publisher), [038G](EPIC-038G_logging_for_unattended_runs.md) (the log line). "Supported for unattended use" waits for `EPIC-036B`, `036C`, `036E`.

---

## 1. Context and problem
Every headless command boots the app, does one thing and calls `app.stop()` (`src/main.py:57-80`); only the interactive REPL keeps the process up, and it waits on a terminal (`shell.wait_for_exit()`). No handler for SIGTERM exists in `src/` (a `kill` skips `BotsModule.shutdown`, which closes the workers); the Engine's two handlers belong to the Qt watchdog and the audit CLI. A restart currently turns RUNNING/PAUSED bots into RECOVERING and waits for a person to open the order session (`bot_restore_service.py`, `SPEC-004` §2). Operators' reports: a live process is not a live bot, a stop may or may not cancel orders depending on how it ended, a read-only copy that looks alive is worse than none, and a restart loop on a configuration error hides it (R1, R3, R13).

## 2. Acceptance criteria
- [ ] `main.py run` (a `declare_cli` entry) acquires the instance lock **first**; if the lock is held it prints why, exits `3` and starts nothing (a read-only host is refused). The test starts two hosts on one data root and asserts the second exits 3.
- [ ] `RunHost` (`IHostedService`) states are BOOTING → SERVING → DRAINING → STOPPED/FAILED as DESIGN §6; each transition is one INFO log line.
- [ ] A first SIGTERM/SIGINT (POSIX) or SIGINT/SIGBREAK (Windows) starts DRAINING: the **stop policy** runs under `--stop-timeout` (default 25 s), then `app.stop()` (`BotsModule.shutdown` logs "workers closed"), the lock is released, the exit code is 0. A second signal skips the wait. Proven by a sanity test that sends a real SIGTERM to a child process (POSIX) and a Ctrl-Break to a child in a new process group (Windows runner or skipped with a stated reason).
- [ ] Policies per O1 (default **LeaveOrdersResting**): it closes workers and leaves orders, logging at INFO the bots left and their orders-resting count; `--on-stop stop-bots` dispatches the existing Stop for each running bot (cancel, confirm, STOPPED), bounded by the timeout, logging at WARNING what did not finish. Neither policy changes the Stop use case.
- [ ] After restart, RECOVERING bots follow O2: by default they stay RECOVERING and `run` logs one WARNING per bot naming `bot resume <id>`; `--resume-recovering` (offered only after the alerting prerequisites, see §3) reconciles and resumes through the existing handlers.
- [ ] `--start-planned` starts the bots whose plan says running and which are at rest, via `StartBotCommand` through `ICommandDispatcher`; before relying on it the task verifies that Start from the CLI can supply what the screen supplies (`command.base`, the venue confirmation for a mainnet venue, O8) and records the answer.
- [ ] Every `--health-interval` (default 60 s) `HealthPublisher` writes one parseable log line and the snapshot (038C): state, uptime, bots by state, last price-tick age, last user-stream event age, clock skew, resident memory. A stale feed makes the line say so.
- [ ] While no alert channel carries bot events (before `EPIC-036B`/`036C`), `run` logs a WARNING at start: *"no alert channel is configured for bot events; nothing will tell you if a bot halts"*. The runbook and README say the host is **not** supported for unattended money until 036B, 036C and 036E have merged.
- [ ] A crash (an unhandled exception) exits 1; there is no retry loop inside the host. Exit codes 3, 4, 5 are configuration/lock outcomes the supervisor must not retry.
- [ ] A host with no bots, an empty data root and no credentials boots, serves, health-lines and stops (the common first run).
- [ ] `IHostSignal` with `NullHostSignal` as the default exists; `SdNotifyHostSignal` (READY, WATCHDOG, STOPPING) is an optional adapter, off by default, Linux-only, documented as not working in a container.

## 3. Design
The host only sequences; it knows no bot. Strategy for the stop policy and the signal source; Observer for the health contributors (038C); the engine's `IHostedService` for lifecycle. The pattern follows Freqtrade's worker (signals, an optional systemd integration) and Hummingbot's explicit `exit` versus window-close difference, made a named option (R2, R3). The host adds no supervision logic: restart belongs to the service manager, and the exit codes tell it which failures to retry. **Alert prerequisite for O2(b):** `--resume-recovering` is implemented behind the flag but its documentation says to use it only once bot events reach the owner; the flag refuses to start (exit 5) unless an alert channel is configured **or** `--i-accept-silent-failures` is given (a deliberate typed acknowledgement, not a default).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/operations/application/run_host.py` (new) | `RunHost` |
| `src/modules/operations/contracts/` (new) | `IShutdownSignalSource`, `IShutdownPolicy`, `IHostSignal`, `HostState` |
| `src/modules/operations/adapters/` (new) | `PosixSignalSource`, `WindowsSignalSource`, `FakeSignalSource` (testing), `LeaveOrdersResting`, `StopBotsFirst`, `NullHostSignal`, `SdNotifyHostSignal` |
| `src/modules/operations/cli/run_cli_handler.py` (new), `src/config/cli_commands.json` | `run` and its flags |
| `src/main.py` | the exit-code mapping from 038B; `run` shares the lock acquisition |
| `Docs/SPEC/SPEC-015_run_the_bots_headless.md` (new) | the journey |

## 5. Testing
Tier: unit with `FakeSignalSource` and a fake clock for the state machine; sanity for the real signal.
- `test_a_second_host_on_one_data_root_exits_three_and_starts_nothing`
- `test_a_first_signal_drains_then_stops_and_releases_the_lock` · `test_a_second_signal_skips_the_wait`
- `test_leave_orders_resting_places_and_cancels_nothing` (the fake exchange records zero calls)
- `test_stop_bots_first_dispatches_the_existing_stop_and_logs_what_timed_out`
- `test_recovering_bots_stay_recovering_by_default_and_are_named_in_the_log`
- `test_resume_recovering_refuses_without_an_alert_channel`
- `test_start_planned_dispatches_start_for_planned_bots_at_rest_only`
- `test_the_health_line_is_parseable_and_reports_a_stale_feed`
- `test_a_host_with_nothing_configured_boots_serves_and_stops`
- sanity: `test_sigterm_to_a_real_run_process_exits_zero_and_closes_the_bot_workers`; `test_sigkill_then_restart_recovers_the_bots_from_their_files`
- soak: 14 simulated days, stream deaths at the 24 h boundary, 10-minute outages; resident memory within a stated bound; the health line never stops.
Not run yet. Never against a real exchange.

## Implementation notes (written when done)
Not started.

## Resume
Not started. Blocked on O1, O2, O8 for the policy defaults; the state machine and the signal sources can start once 038A–038C have merged.
