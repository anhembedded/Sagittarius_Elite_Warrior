# EPIC-038G — Logs for an unattended run cannot fill the disk and can be read by a machine

**Status:** 🔵 Planned — not started
**Source:** the owner, 2026-10-09; the brief: *log rotation; the host sends a periodic health line to the log.*
**Risk:** 🟡 — the run-log scan in CI reads `- (WARNING|ERROR|CRITICAL) -` records (`ci-rule.md` §3); a format change can blind it
**Complexity:** S — mostly configuration and a documented line format; an Engine change only if the owner asks (O7)
**Epic:** [EPIC-038](../README.md)
**SPEC:** none.
**Design:** [DESIGN §6, §12](../DESIGN_2026-10-09_headless_operation.md) · **Research:** [§9](../RESEARCH_2026-10-09_headless_operation.md) · **Decision:** [O7](../DECISION_2026-10-09_headless_operation.md)
**Depends on:** [038A](EPIC-038A_qt_free_boot_and_guard.md). The log line itself is produced by the host in [038D](EPIC-038D_run_host.md).

---

## 1. Context and problem
The Engine's file log is a plain `logging.FileHandler` (`std_logger.py:56`): no rotation, no size cap. Console logging is on by default (`app_config.json`, `log.console.enabled`). A full disk "stops the database write, not the network call, so the symptoms are strange" (R9). The dev/debug mode already writes a full session log to `<data root>/logs/` for bug reports (`app_config.py`), which is correct for a developer and wrong for a service that runs for months.

## 2. Acceptance criteria
- [ ] The `run` host logs to stdout only unless `log.file` is configured; the unit file in the runbook sets no `log.file` (stdout goes to the journal on systemd, to the wrapper's rotated capture on Windows). A test asserts the shipped unit and the NSSM settings in the runbook source set none.
- [ ] If `log.file` is set, the log guide states in one place that the file **grows without bound** until the Engine gains rotation, and gives the `logrotate` stanza (POSIX) to use meanwhile; a test pins that sentence to the config key so the two cannot drift.
- [ ] The health line format is documented and stable: `[health] key=value …` with the keys of DESIGN §6; a parser test reads real output from the host.
- [ ] The CI run-log scan still reads `WARNING|ERROR|CRITICAL` records from a headless run (a sanity test runs `run` for a few seconds and the scan finds no unexpected record); a stale-feed health line is INFO, an escalation to WARNING is made by the alert source, not by the health line.
- [ ] A secret never reaches the log: the test of 038E is re-run against the host's whole stdout.
- [ ] If the owner chooses an Engine rotating file handler (O7(ii)), this task stops and records a separate Engine proposal; it does not edit the Engine.

## 3. Design
Prefer the supervisor's facilities (journald/NSSM) over an in-app file: they already rotate, cap and forward (R9, R10), so there is nothing to build, test or maintain in the app, and the open/closed answer to "a different sink" is a different unit file. JSON logging is a formatter choice the Engine would own; recorded, not built.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `Docs/OPERATIONS/` (the runbook, written by 038H) | the log guide and the `logrotate` stanza |
| `src/modules/operations/application/health_line.py` (new) | the single format function used by the host |
| `tests/unit/.../test_health_line_format.py`, `tests/sanity/...` | the parser and the log-scan tests |

## 5. Testing
Tier: unit and sanity.
- `test_the_health_line_round_trips_through_its_parser` · `test_a_headless_run_leaves_no_unexpected_warning_or_error_in_the_log`
- `test_the_shipped_unit_and_wrapper_set_no_log_file`
- `test_the_log_file_growth_sentence_is_pinned_to_the_config_key`
Not run yet.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: ask the owner whether an Engine rotating handler is wanted (O7).
