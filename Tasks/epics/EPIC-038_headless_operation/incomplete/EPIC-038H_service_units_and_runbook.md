# EPIC-038H — A systemd unit, a Windows procedure and a runbook, exercised with kill, reboot and upgrade

**Status:** 🔵 Planned — not started; the draft can start after 038D–G, the "supported unattended" wording waits for `EPIC-036B`, `036C` and `036E`
**Source:** the owner, 2026-10-09; the brief: *a systemd unit and a Windows option (Task Scheduler or NSSM — research which); log rotation; upgrade and migration of state between versions.*
**Risk:** 🟢 — files and a document; the risk is a runbook that was never run
**Complexity:** S — a unit, a wrapper recipe, a checklist
**Epic:** [EPIC-038](../README.md)
**SPEC:** none.
**Design:** [DESIGN §12](../DESIGN_2026-10-09_headless_operation.md) · **Research:** [§1, §2, §8, §9, §10, §15](../RESEARCH_2026-10-09_headless_operation.md) · **Decision:** [O5](../DECISION_2026-10-09_headless_operation.md)
**Depends on:** [038D](EPIC-038D_run_host.md), [038E](EPIC-038E_headless_secret_backends.md), [038F](EPIC-038F_preflight_command.md), [038G](EPIC-038G_logging_for_unattended_runs.md); owner decision O5.

---

## 1. Context and problem
The sources agree on what a service needs: restart on failure with a delay and no start limit, no restart on a configuration error, a stop timeout longer than the app's drain, secrets outside the code directory and out of the process environment where possible, a dedicated no-login account, a memory ceiling, bounded logs (R1, R4, R8, R9). On Windows the wrapper stops a console app with Ctrl-C first and waits 1.5 s by default (R10). Freqtrade's updating page says nothing about migrating state (R15); this app's state is the bots' files, the snapshot and the data root.

## 2. Acceptance criteria
- [ ] A systemd unit (`deploy/linux/sew-run.service`, new) with: `Restart=on-failure`, `RestartSec=10`, `StartLimitIntervalSec=0`, `RestartPreventExitStatus=3 4 5`, `TimeoutStopSec` above `--stop-timeout`, `LoadCredential=` per key (if O3 chooses it), `MemoryMax=`, a dedicated no-login `User=`, `WorkingDirectory` and `SEW_DATA_ROOT` outside the checkout, no `log.file`. A test parses the unit and asserts each setting; the exit codes in `RestartPreventExitStatus` are generated from the `ExitCode` enum of 038B.
- [ ] The Windows procedure per O5 (recommended: NSSM as an external tool, Task Scheduler as the stated fallback): `AppExit` Restart, `AppStopMethodConsole` raised above the drain, `AppRotate`/`AppRotateBytes` set, the service account, `SEW_DATA_ROOT`. The procedure states that NSSM stops with Ctrl-C first, which the host handles (`SIGINT`), and what Task Scheduler cannot do.
- [ ] A runbook `Docs/OPERATIONS/headless_runbook.md` (new): install (headless requirements, Python floor), provision secrets (O3), `preflight`, first `run` on the testnet, `status`, stop (`systemctl stop`, `nssm stop`), upgrade, rollback, what the exit codes mean, what to do on each preflight FAIL, how to read the health line.
- [ ] **Upgrade procedure:** stop (`--on-stop` per O1) → copy the data root's `state/` → upgrade → `preflight` → start → `status`. `status` and `preflight` warn when a bot file carries a schema this build cannot read (the restore service already refuses and leaves it untouched); a test seeds one.
- [ ] A **checklist** the owner signs on a fresh Linux VPS and a fresh Windows server, testnet only: survives `kill -9` (restarts, bots RECOVERING, alerts per 036), survives a reboot, stops cleanly on `stop`, the second copy exits 3 and is not restarted, a bad clock fails preflight, a disk-full volume is reported, the dead man's switch fires when the host is stopped on purpose (needs 036E).
- [ ] The runbook's first page states what is **not** supported until `EPIC-036B`, `036C` and `036E` have merged, and links them.
- [ ] A container note: sd_notify does not work in Docker (R2); a Dockerfile is out of scope.

## 3. Design
Documentation and configuration as code: the unit and the wrapper recipe are the artefacts the tests parse, so the runbook cannot drift from them (the repository's pinned-sentence pattern). Windows: NSSM supervises and rotates and tries a graceful stop first; Task Scheduler's restart settings are coarse and it has no stop-signal control (R10) — documented as the fallback, not the recommendation. Decision O5.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `deploy/linux/sew-run.service` (new) | the unit |
| `deploy/windows/nssm-install.ps1` (new) | the recipe (idempotent) |
| `Docs/OPERATIONS/headless_runbook.md` (new) | the runbook and checklist |
| `tests/unit/.../test_service_unit_settings.py` (new) | the parse test |

## 5. Testing
Tier: unit for the parse tests; the checklist is manual and recorded in the task.
- `test_the_unit_restarts_on_failure_without_a_start_limit_and_never_on_a_configuration_exit` · `test_the_unit_stop_timeout_exceeds_the_hosts_drain` · `test_the_unit_sets_no_log_file`
- `test_the_wrapper_stop_wait_exceeds_the_hosts_drain`
- `test_a_bot_file_from_a_newer_schema_is_reported_not_rewritten`
- Manual: the signed checklist, two machines. Not run yet.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: ask the owner O5, then write the unit and its parse test.
