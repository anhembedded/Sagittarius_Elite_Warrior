# SPEC-015 — Run the bots headless: `main.py run`

- **Status:** 🟡 partly built — the host, its signals, both stop policies, the lock refusal, the pre-flight gate, the health line and the resume of RECOVERING bots are built and proven; `--start-planned` has no plan to read until `EPIC-038I` (`bot apply`) writes one; Ctrl-Break on Windows is proven by the adapter's own test, not by a Windows run; and the host is **not supported for unattended money** until `EPIC-036B`, `036C` and `036E` have merged.
- **Actor:** operator (a person who runs the bots on a server with no window, or the service manager that runs them for that person)
- **Origin:** `EPIC-038D`, from the owner's instruction of 2026-10-09 (run the bots from the command line on a VPS, Linux or Windows); decisions O1, O2, O4, O8 and D9 of `DECISION_2026-10-09_headless_operation.md`.
- **Surfaces:** `main.py run` and its flags; `main.py status` and `bot list` from a second process; the host's log on standard output; `state/health.json`. No window.

## 1. Trigger

*"I want the app to keep my bots running on this machine until I tell it to stop, to stop cleanly when I do, and to tell me how it is."*

## 2. Preconditions

1. The checkout is installed with the headless requirements (`requirements-headless.txt`), the Engine pin installed (`scripts/engine_pin.py install`). No Qt is needed.
2. No other copy of the app holds the data root. A second copy would be read-only and trade nothing, so `run` refuses to be one (§5).
3. Each venue the bots trade on has a key the exchange accepts, read from the environment, a secrets file or the keyring (`credentials-present`). A key that can withdraw is refused (`no-withdraw-permission`). A first run with no key at all is refused with 5, by design; `--skip-preflight` runs it anyway.
4. The machine's clock is within the exchange's tolerance, the disk has room, the data root is writable (`main.py preflight` says each).

## 3. Main flow

1. The operator (or the service manager) starts `main.py run [flags]`.
2. The entry point takes the data root's instance lock first. If another copy holds it, it says why on standard error, exits `3` and builds nothing.
3. It builds the application **without booting it**, and checks what can be checked without the exchange: the flags (`2`), `--resume-recovering` against the alert channels (`5`), and a mainnet `--start-planned` the operator did not confirm with `--confirm-venue` (`2`).
4. It runs the pre-flight, **before the bots are restored** (restoring reads the exchange and may cancel orders), unless `--skip-preflight` is given, which it logs at WARNING. A failed check ends the process with the code a supervisor keys on: `4` the machine, `5` only the operator can fix it (no key, a rejected key, a key that can withdraw), `6` the exchange cannot be reached and a restart can outlast it. Each failed finding is logged at ERROR with its remedy.
5. It starts listening for SIGTERM and SIGINT (SIGINT and SIGBREAK on Windows). A request that arrives while the bots are restored is remembered and honoured as soon as the host serves.
6. The application boots: the bots are restored (a RUNNING or PAUSED bot becomes RECOVERING and places nothing), the watches start, and the host's start-up steps run in order: the alert-channel warning, one WARNING per RECOVERING bot, then `--resume-recovering` and `--start-planned` if given.
7. The host says `BOOTING -> SERVING` (one INFO line per state change), tells the service manager it is ready if `--host-signal sdnotify` was given, and writes a snapshot and one health line at once, then every `--health-interval` (60 s) until it stops. Before each snapshot it asks the exchange its time, so the line's `skew_ms` is a number and `status` reports it.
8. The first SIGTERM or SIGINT starts the drain: `SERVING -> DRAINING`. The stop policy runs for at most `--stop-timeout` (25 s): `leave-orders` (the default) asks the exchange for nothing and logs, at INFO, each active bot it leaves and how many orders it has resting; `--on-stop stop-bots` asks for the Stop the screen asks for, for each active bot, and waits for STOPPED.
9. A second signal while the drain waits skips the wait. A policy that outlasts the timeout is given up on. Either way the host logs, at WARNING, which bots it left, in what state and with how many orders resting; the next start reads each as RECOVERING.
10. The application stops (`DRAINING -> STOPPED`): the scheduler, the host, then the modules, so the bots' workers close (`Bot price streams released, workers closed`) and the last snapshot says `STOPPED`. The entry point releases the lock and the process exits `0`.

## 4. What must be true afterwards

- The exit code is `0` after a requested stop, `3` for a held lock, `4`/`5`/`6` for a failed pre-flight, `2` for a refused request, `1` for a crash. There is no retry loop inside the host: the service manager restarts on `1` and `6` and not on `2`–`5`.
- The lock is free, and `state/health.json` says `STOPPED` (or `FAILED` after a crash), so `status` can tell a clean stop from a process that vanished.
- A bot that was RUNNING when the host stopped is RECOVERING after the next start, and stays RECOVERING until a person resumes it (decision O2). The host never resumes a bot by itself.
- With `leave-orders` the bots' orders are still on the exchange; the host placed and cancelled nothing while stopping.
- No credential appears in the log, the snapshot or any report.

## 5. When it goes wrong

| What goes wrong | What the operator sees | Why it is this and not a crash |
| :--- | :--- | :--- |
| Another copy holds the data root | Exit `3`; "Another copy of Sagittarius is already running on the same data … `run` needs to be the writable copy and starts nothing on a read-only one." | A read-only host would look alive to its supervisor and trade nothing; `3` is in the unit's `RestartPreventExitStatus` |
| A flag is wrong (`--stop-timeout 0`, an unknown `--on-stop`) | Exit `2`, a sentence naming the flag | argparse and `run_options_of` refuse before anything starts |
| `--start-planned` would start a mainnet bot the operator did not confirm | Exit `2`, nothing started; the message names the bot and the `--confirm-venue` it needs | Decision O8: the command line's equivalent of the screen's real-money dialog |
| `--resume-recovering` with no alert channel and no `--i-accept-silent-failures` | Exit `5`, nothing started | Decision O2: nothing resumes unattended while a failure can be silent |
| `--host-signal sdnotify` off Linux, or with no `NOTIFY_SOCKET` | Exit `2` naming the missing piece | The adapter cannot work there; a container without the socket mounted is the usual cause |
| The pre-flight fails | Exit `4`, `5` or `6` per decision D9; each failed finding at ERROR with its remedy | The same mapping `preflight` and `exchange-status` use (`EXIT_CODE_FOR_FAILURE`) |
| The exchange is unreachable at start | Exit `6` | A restart can outlast an outage; the unit restarts with a delay |
| No alert channel carries bot events | A WARNING at start: "no alert channel is configured for bot events; nothing will tell you if a bot halts" | Until `EPIC-036B`, a halt at 3 a.m. is silent, and the log says so first |
| A bot is RECOVERING after the restart | One WARNING per bot naming it and the move that is a person's | Decision O2 |
| The stop policy does not finish in `--stop-timeout`, or a second signal arrives | A WARNING naming the bots left, their state and orders resting; exit `0` | The state is on disk; the next boot treats them as RECOVERING |
| The exchange cannot tell the clock (the probe fails) | `skew_ms=na` on the line; one WARNING per streak, one INFO when it works again | A snapshot must never wait on the exchange |
| The snapshot cannot be written (disk full) | ERROR `[health-snapshot] could not write the snapshot`; the host carries on, and `status` calls it stale | The snapshot reports the work; losing it must not stop the work |
| An unhandled exception | Exit `1`, the traceback on standard error and in the log; the snapshot says `FAILED` | The host adds no retry; the supervisor restarts and boot recovery does what it does after any crash |

## 6. What this use case does NOT promise

- **It is not supported for unattended money.** Bot events reach no alert channel (`EPIC-036B`, `036C`) and nothing watches the host from outside (`EPIC-036E`); until all three have merged a halt is silent. The WARNING at start says so; the runbook says so.
- **Stopping does not watch the orders it leaves.** With `leave-orders`, between the stop and the next start nothing looks at a stop loss or a take profit. This is true under either policy (decision O1; recorded for `EPIC-036`).
- **A running host cannot be controlled.** There is no `bot resume`, no `bot stop` for a running host in v1 (decision O4): control is a restart plus `bot apply`, and a remote control is `EPIC-036F`/`038J`. The WARNING for a RECOVERING bot names the Bots tab, which needs the lock the host holds: resuming a bot by hand means stopping the host first.
- `--start-planned` starts nothing until a plan exists (`EPIC-038I`); the host says so at start.
- One `--confirm-venue` names one venue; a plan holding real-money bots on two venues is started one venue per run.
- `--resume-recovering` opens the venue's order session, which reconciles the bots with the exchange; it does not start a bot and does not resume a HALTED one.
- Windows' Ctrl-Break and the Windows memory reading are implemented and tested on their own, but have not been run on a Windows machine by this task.
- `--host-signal sdnotify` does not work inside a container that does not mount systemd's notify socket.

## 7. Ports and modules it exercises

`operations` (`RunHost`, `HostStateMachine`, `IShutdownSignalSource`, `IShutdownPolicy`, `IHostSignal`, `IHostStep`, `IHostHealth`, `IAlertChannels`, `HealthCadence`, `PreflightGate`, `HealthPublisher`), `bots` (`StartBotForHostCommand`, `StopBotForHostCommand`, `ResumeRecoveringForHostCommand`, `GetBotStatusReportQuery`, `IBotPlan`), `trading` (`IHealthProbe` through `ClockSkewProbe`, `VenueReads`, `ITradingSession.ensure_ready`), the shell (`IHealthProbeTable`, `IInstanceAccess`, `console_log_to`), the support CLI host (`command_requires_writable_instance`, `command_owns_its_lifecycle`, `run_command`).

## 8. Proven by

| Evidence | Where | Tier |
| :--- | :--- | :--- |
| A real SIGTERM and a real SIGINT stop a real `run` process cleanly: workers closed, lock released, the snapshot `STOPPED`, exit `0`, the three transitions in order | `tests/integration/presentation/test_run_process.py` | integration (process) |
| A second signal stops at once and names what was left; a policy that outlasts the timeout is given up on | `tests/integration/presentation/test_run_process.py` | integration (process) |
| A held lock exits `3`, builds nothing and reaches no exchange | `tests/integration/presentation/test_run_process.py` | integration (process) |
| A rejected key exits `5`, an unreachable exchange `6`, a full disk `4`; none boots the bots; `--skip-preflight` starts | `tests/integration/presentation/test_run_process.py` | integration (process) |
| A host with no bot, no key and an empty data root boots, serves, health-lines and stops; a crash exits `1` with `FAILED` and no retry | `tests/integration/presentation/test_run_process.py` | integration (process) |
| `status` from a second process reads the host's snapshot and the skew the host measured | `tests/integration/presentation/test_run_process.py` | integration (process) |
| The log of a real `run` is clean (one named WARNING), its health line parses, the canary credential was read and never logged, no log file is written | `tests/sanity/test_a_headless_boot_logs_cleanly.py` | sanity |
| The host's states, the two signals, the timeout, a failing step or policy | `tests/unit/modules/operations/application/test_run_host.py` | unit |
| Both stop policies against a live Grid on the fake exchange; `leave-orders` places and cancels nothing | `tests/integration/modules/bots/test_the_run_hosts_stop_policies_on_the_fake_exchange.py` | integration |
| `--start-planned` and `--resume-recovering` drive real bots through the screen's own commands | `tests/integration/modules/bots/test_the_run_hosts_start_up_steps_on_the_fake_exchange.py` | integration |
| A mainnet start needs the venue typed; a resume of a mainnet venue too | `tests/unit/modules/bots/application/test_host_bot_requests.py` · `test_resume_recovering_for_host.py` · `tests/unit/modules/operations/application/test_host_steps.py` | unit |
| The composed app: refusals before any boot, a stop during boot honoured, every state published | `tests/integration/modules/operations/test_run_command_on_the_composed_app.py` | integration |
| The health line from the snapshot, a stale feed, the clock probe | `tests/unit/modules/operations/application/test_host_health_line.py` · `test_health_line_logger.py` · `test_health_probes.py` · `tests/unit/modules/trading/application/health/test_clock_skew_probe.py` | unit |
| The user runs it: on a Linux VPS, `main.py run`, then `kill -TERM <pid>` from another shell | the log ends `DRAINING -> STOPPED`, `workers closed`, `echo $?` prints `0`, and `main.py status` says not running | manual |
| The user runs it: on a Windows server, `main.py run` in a console, then Ctrl-Break | the same lines, exit `0` | manual |
