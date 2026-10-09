# EPIC-038 — The bots run with no GUI: a command-line host on a VPS that starts, reports, stops and restarts like a service

- **Status:** 🔵 Planned — scaffolded 2026-10-09; **not started** (documentation only; the owner asked for a design and a planned epic)
- **Repositories:** Elite. No Engine change is expected; the two that might help are listed as pending decision O7 and need their own confirmation (`ONBOARDING.md` §2).
- **Origin:** the owner, 2026-10-09, relayed by the coordinator session: run bots with no GUI from the command line on a VPS, Linux or a Windows server, with a design that is easy to extend (*"nhớ chú ý design dễ dàng mở rộng SOLID"*, translated: mind a design that is easy to extend, SOLID). [`Docs/PROJECT_INTENT_AND_USER_STORIES.md`](../../../Docs/PROJECT_INTENT_AND_USER_STORIES.md) already says (line 13, translated) that the app must run on a screenless server and that this is "a cross-cutting design constraint, not a side feature" — and nothing enforces it.
- **North star:** [`DESIGN_2026-10-09_headless_operation.md`](DESIGN_2026-10-09_headless_operation.md) (what exists, the proof, components, ports, sequences, extension cases). Real operators' experience: [`RESEARCH_2026-10-09_headless_operation.md`](RESEARCH_2026-10-09_headless_operation.md).
- **Decisions:** [`DECISION_2026-10-09_headless_operation.md`](DECISION_2026-10-09_headless_operation.md) — **no TUI** (D1), reuse the CLI machinery (D2), extend by registration (D3) accepted; D4–D6 proposed; **O1–O8 are pending the owner**, each with a recommendation.
- **Tracking:** [`TRACKING.md`](TRACKING.md).
- **Dependencies:** `EPIC-036` (alerting) — unattended running needs alerts; see §3b for what can land first. `EPIC-035W`'s per-bot health snapshot is embedded by `EPIC-038C`, not duplicated. `EPIC-036A` lifts `ISecretStore` to `core/contracts`; `EPIC-038E` coordinates that single move. `EPIC-036B` deletes `notification_event_handler.py`, which `EPIC-038A` must not rework.

---

## 1. What the coordinator's findings turned out to be (verified 2026-10-09, `master-warrior` `9a6099c`)
| Claim | Result |
| :--- | :--- |
| `main.py` has a headless path with six commands and an interactive REPL, driven by `cli_commands.json` through `ICliCommandTable` / `ICliCommandHandler` | **Confirmed.** |
| Domain, application, adapters and composition import no PySide6; three `core/contracts` files import `QWidget` under `TYPE_CHECKING` only | **Confirmed** at import time. |
| Bot infrastructure is Qt-free; boot recovery, user-stream watch and sleep watch live in `bots/application` | **Confirmed.** |
| The engine has no TUI | **Confirmed** (its UI extension is `pyside_mvc`). |
| `create_app` boots headless | **Refuted.** It cannot boot without PySide6: three UI concerns sit in the shared `create_app` path — a UI-failure event imported from the Engine's Qt package (`src/shell/system_error_report.py:41`), the icon-asset validator (`composition_root.py:284`) and a dependency check that requires `PySide6` and `pyqtgraph` (`composition_root.py:275`). |
| Bots run without the window | **Confirmed once PySide6 is installed** (offscreen, no `QApplication`): 11 modules boot, bots restore and start their watches, shutdown closes the workers. Proven with an empty bot store; no exchange was contacted. A bot with live orders has not been run headless. |

The proof is a throwaway probe (not committed) described in [DESIGN §1.1](DESIGN_2026-10-09_headless_operation.md): Python 3.13.16, the engine at its pinned ref `f4ef582`, three runs (PySide6 absent, PySide6 blocked, PySide6 installed). It also found that on a server image PySide6 needs system libraries (`libEGL.so.1` was missing), so "install Qt and ignore it" has a cost. Other gaps found: no signal handler (a `kill` skips `app.stop()`), failed commands exit 0, `--json` on one command only, no log rotation, and no way to provision a secret on a server except a shell `export`.

## 2. Decisions already made
1. **No TUI** (D1) — a third presentation layer, a source of the "sibling paths drift" class, covered by `status --watch` plus alerts; the conditions to reconsider are in the decision record.
2. **Reuse** (D2) — the CLI grows through `declare_cli` and `cli_commands.json`; bot verbs dispatch through `ICommandDispatcher`, the port the Bots screen uses (`bots_screen/bot_actions_coordinator.py:31`).
3. **Extend by registration** (D3) — a command, a secret backend, an output format, a preflight check, a health contributor, a stop policy or a supervisor integration is one class and one registration.

## 3. Goals — measurable
| Metric | Today (measured 2026-10-09) | When the epic is done |
| :--- | :-: | :-: |
| `create_app` + `boot()` + `stop()` with PySide6 not importable | fails (`ModuleNotFoundError` at `system_error_report.py:41` → engine `thread_affinity.py:6`) | succeeds; a sanity test in CI blocks PySide6, `pyqtgraph` and `shiboken6` and keeps it so |
| A command that runs until told to stop | none (every command calls `app.stop()` and returns) | `run`: boot, restore bots, serve, stop on a signal |
| Signal handlers in `src/` | 0 | SIGTERM and SIGINT (Linux), SIGINT and SIGBREAK (Windows) end in a clean stop: workers closed, lock released, exit 0; a second signal stops at once |
| Exit codes | every outcome exits 0 or by traceback | 9 documented codes (success, error, usage, lock held, preflight failed, configuration, exchange, host not running, host unhealthy) |
| Commands with `--json` | 1 of 6 (`order-preview`) | every report command (`status`, `bot list/show`, `preflight`, `exchange-status`, `order-preview`) through one renderer registry |
| Bot actions from the command line | 0 | `bot list/show/start/stop/pause/resume/apply`, each dispatching the command the screen dispatches, with a parity test |
| A status a script can read | none | `status --json` with host state, progress ages, skew, bot states; exit 10/11 for monitoring |
| Pre-flight before first run | `exchange-status` prints skew for one venue | `preflight`: clock skew, credentials, key permissions (withdraw = FAIL), outbound address, disk, data root, Python floor |
| Ways to provision a server secret | environment variable | + systemd credentials, + a permission-checked file (backend chosen by decision O3) |
| App log growth | unbounded when `log.file` is set | bounded by the journal or the wrapper; documented, with a test that the unit does not set `log.file` |
| Install footprint on a server | PySide6, pyqtgraph, pytest-qt and Qt system libraries | a headless requirements file with none of them (decision O6) |
| Service units | none | a systemd unit and a Windows (NSSM) procedure in a runbook, exercised in a stop/kill/reboot checklist |
| A stop that leaves orders resting without saying so | not applicable (no headless stop) | the policy is named, logged and chosen (O1) |

## 3b. Relation to EPIC-036 (alerting)
Unattended running needs alerts, and today **no bot event reaches the owner** (`EPIC-036` README §2). The dependency is strict only for the *claim*:

| Can land before `EPIC-036` | Lands with or after |
| :--- | :--- |
| 038A, 038B, 038C, 038E, 038F, 038G, 038I; 038D as a working host with a startup warning | the statement "supported for unattended use" in 038D/038H needs **036B** (bot events become alerts), **036C** (a real channel) and **036E** (the dead man's switch); 038J needs **036F** and decision O4 |

## 4. Sub-tasks, ordered by risk
Each child is one PR, done in the order the dependencies allow (A → B → C → F, G → E → D → I → H → J).

| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-038D](incomplete/EPIC-038D_run_host.md) | The `run` host: `IHostedService`, signals, stop policy, lock refusal, health line, `--start-planned` | Elite | 038A, 038B, 038C, 038G; owner decisions O1, O2, O8 | 🔴 | Planned |
| [EPIC-038E](incomplete/EPIC-038E_headless_secret_backends.md) | Headless secret backends behind `ISecretStore`: systemd credentials, permission-checked file | Elite | owner decision O3; coordinates `EPIC-036A` | 🔴 | Planned |
| [EPIC-038J](incomplete/EPIC-038J_control_of_a_running_host.md) | Control of a running host (only if decision O4 asks for it) | Elite | 038D; `EPIC-036F`; owner decision O4 | 🔴 | Planned; gated |
| [EPIC-038A](incomplete/EPIC-038A_qt_free_boot_and_guard.md) | Qt-free boot: UI wiring leaves the shared path; CI guard with PySide6 blocked; headless requirements | Elite | owner decisions O6, O7 | 🟡 | Planned |
| [EPIC-038C](incomplete/EPIC-038C_bot_status_read_model.md) | Bot status read model, health snapshot file, `status`, `bot list/show` | Elite | 038B | 🟡 | Planned |
| [EPIC-038F](incomplete/EPIC-038F_preflight_command.md) | `preflight`: clock skew, credentials, key permissions, outbound address, disk | Elite | 038B | 🟡 | Planned |
| [EPIC-038G](incomplete/EPIC-038G_logging_for_unattended_runs.md) | Logging for unattended runs: stdout/journal first, bounded files, one parseable health line | Elite | 038A | 🟡 | Planned |
| [EPIC-038I](incomplete/EPIC-038I_bot_plan_files.md) | Bot plan files and `bot apply` (idempotent, no secrets, diff first) | Elite | 038B, 038C | 🟡 | Planned |
| [EPIC-038B](incomplete/EPIC-038B_exit_codes_and_output_formats.md) | Exit codes and the `--json` renderer registry; handlers may return a `CliOutcome` | Elite | None | 🟢 | Planned |
| [EPIC-038H](incomplete/EPIC-038H_service_units_and_runbook.md) | systemd unit, Windows (NSSM) procedure, runbook, upgrade procedure | Elite | 038D, 038E, 038F, 038G; supported-unattended wording waits for 036B/C/E | 🟢 | Planned |

## 5. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| 0 — Qt-free and scriptable (038A, 038B) | `create_app`/`boot`/`stop` pass with PySide6 blocked; handlers return documented exit codes; `--json` through one registry | The sanity guard shown red on `master-warrior` by re-adding one Qt import, then green; exit-code tests; the `-Full` run green on each head. Not run |
| 1 — Observe (038C, 038F, 038G) | `status`, `bot list/show`, `preflight` give the same facts as the GUI and as each other; logs are bounded | Parity test per read; a preflight run against the fake exchange with injected skew and a read-only key; the snapshot test. Not run |
| 2 — Run (038D, 038E, 038I) | `run` survives a SIGTERM, a SIGKILL and a reboot-equivalent in a sanity test; refuses a held lock with exit 3; a secret is provisioned without a shell export | Child tests; a 14-day simulated soak on the fake exchange (memory bounded, health line never stops); the owner's decisions O1–O3 recorded. Not run |
| 3 — Operate (038H) | A fresh Linux VPS and a fresh Windows server each run the checklist: install, preflight, start, kill -9, reboot, upgrade, stop | The checklist signed in the task, on the owner's own machines, testnet only; wording "supported unattended" only after 036B/036C/036E. Not run |
| 4 — Control (038J) | Only if O4 says so: a command reaches a running host through the chosen channel and dispatches the UI's own command once, audited | Owner decision recorded first; `EPIC-036F` merged. Not run |

## 6. Out of scope
- A TUI (D1) and any web UI or HTTP API.
- Alerting itself — `EPIC-036` — and the per-bot health strip — `EPIC-035W`; this epic reads their outputs.
- Engine changes (O7) and a rotating file log in the Engine's logger.
- Docker/Kubernetes packaging (a unit file's equivalent is a later task; the runbook notes that sd_notify does not work in a container, R2).
- Running anything against a real exchange; every test uses the fake exchange.
- Any code. This epic is documentation until a child task is started.

## Notes (newest first)
- **2026-10-09** — Epic scaffolded from the headless-boot proof, the code survey and the operators' research; documentation only, nothing started. Open owner decisions O1–O8 are listed with recommendations in the decision record.
