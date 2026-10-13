# EPIC-038G — Logs for an unattended run cannot fill the disk and can be read by a machine

**Status:** ✅ Done (2026-10-12)
**Source:** the owner, 2026-10-09; the brief: *log rotation; the host sends a periodic health line to the log.*
**Risk:** 🟡 — the run-log scan in CI reads `- (WARNING|ERROR|CRITICAL) -` records (`ci-rule.md` §3); a format change can blind it
**Complexity:** S — mostly configuration and a documented line format; no Engine change (O7 settled 2026-10-12: none)
**Epic:** [EPIC-038](../README.md)
**SPEC:** none.
**Design:** [DESIGN §6, §12](../DESIGN_2026-10-09_headless_operation.md) · **Research:** [§9](../RESEARCH_2026-10-09_headless_operation.md) · **Decision:** [O7](../DECISION_2026-10-09_headless_operation.md)
**Depends on:** [038A](EPIC-038A_qt_free_boot_and_guard.md). The log line itself is produced by the host in [038D](EPIC-038D_run_host.md).

---

## 1. Context and problem
The Engine's file log is a plain `logging.FileHandler` (`std_logger.py:56`): no rotation, no size cap. Console logging is on by default (`app_config.json`, `log.console.enabled`). A full disk "stops the database write, not the network call, so the symptoms are strange" (R9). The dev/debug mode already writes a full session log to `<data root>/logs/` for bug reports (`app_config.py`), which is correct for a developer and wrong for a service that runs for months.

## 2. Acceptance criteria
- [x] The `run` host logs to stdout only unless `log.file` is configured. **Proved for the shipped configuration**: `test_the_shipped_configuration_sets_no_log_file` and `test_a_plain_run_logs_to_stdout_and_to_no_file` (the Engine's `StdLogger` built from the real config has one stdout handler and no file handler), and `test_a_plain_headless_run_writes_no_log_file` (a headless boot in a fresh interpreter writes nothing under `<data root>/logs/`). **Handed over to 038H**: the shipped unit and the NSSM recipe do not exist yet, so the test that they set no `log.file` is 038H's own `test_the_unit_sets_no_log_file`, extended (criterion added there).
- [x] The log guide, [`Docs/OPERATIONS/LOGGING.md`](../../../../Docs/OPERATIONS/LOGGING.md) §2, states in one sentence that `log.file` grows without bound until the Engine gains rotation and gives the `logrotate` stanza (with `copytruncate`, because the handler keeps its file open). `test_the_log_file_growth_sentence_is_pinned_to_the_config_key` pins the sentence to the key; `test_log_file_is_the_key_the_engine_reads_and_opens_a_plain_file_handler` makes the sentence fail loudly the day the Engine's handler stops being a plain `FileHandler`.
- [x] The health line format is documented ([`LOGGING.md`](../../../../Docs/OPERATIONS/LOGGING.md) §4, module docstring of `health_line.py`) and stable: `[health] state=… up=…s bots=… tick_age_s=… stream_age_s=… skew_ms=… rss_mb=…`. `test_the_health_line_text_is_pinned` fixes the literal text, `test_the_health_line_round_trips_through_its_parser` the pair, and `test_the_health_line_in_the_real_log_output_parses_back` parses a record **taken from the real logging configuration's stdout**. The host does not exist yet (038D), so "real output from the host" is real output from the shared composition's process; 038D points the same test at `run`.
- [x] The CI run-log scan still reads `WARNING|ERROR|CRITICAL` records from a headless run: `test_a_headless_boot_leaves_no_unexpected_warning_or_error_in_the_log` runs boot, one health line and stop with PySide6 blocked and applies the gate's own regex; `test_a_stale_feed_is_logged_at_info_never_warning` pins the INFO rule (`log_health_line` is the only emitter and fixes the level). **Partial:** the process is the boot/stop cycle, not `run` for a few seconds (no host, and a test sleep is forbidden); 038D re-points it (criterion added there).
- [x] A secret never reaches the log, **in the form that can be tested today**: `test_no_credential_reaches_the_log` plants a canary in all eight Binance credential variables, has the run **read each venue's canary through the real provider classes** (`EnvFirstCredentialsProvider`, `MainnetCredentialsProvider`) and asserts the read happened (`CREDENTIALS_READ=4`) and that the canary appears nowhere in stdout or stderr. The reviewer found the first version vacuous: `create_app/boot/stop` resolves no credential, so the explicit read is what gives the absence meaning. It still does not exercise the venue wiring (`venue_assembly`) or any 038E backend; both extend it (criteria added to 038D and 038E, each requiring a positive proof that the credential was read).
- [x] No Engine change (O7): none made; the rotating handler stays a separate Engine proposal if the owner wants it.

## 3. Design
Prefer the supervisor's facilities (journald/NSSM) over an in-app file: they already rotate, cap and forward (R9, R10), so there is nothing to build, test or maintain in the app, and the open/closed answer to "a different sink" is a different unit file. JSON logging is a formatter choice the Engine would own; recorded, not built.

## 3a. Reuse
Checked `.claude/rules/capabilities.md` and `src/support/`: this task builds no widget, flow or UI helper. **Used** `load_app_config` (the one configuration loader) for the shipped-config tests, the Engine's `StdLogger` and `LoggerConfig` (the real logging configuration, never `basicConfig`), `create_app` (the shared composition), `data_root`'s `SEW_DATA_ROOT` override and the subprocess shape of `tests/sanity/test_the_app_boots_without_pyside6.py`. **Not used:** `INotifier` (a log line is not a user notice), `ICliRegistry` (no command here; 038B and 038D own them). **Built, because no row covers it:** the health line's format and parser (`HealthLine`), the host-state vocabulary (`HostState`), and the module that holds them (`operations`, D4).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `Docs/OPERATIONS/LOGGING.md` (new) | the log guide: where logs go, the `log.file` growth sentence and `logrotate` stanza, the record format, the health line |
| `src/modules/operations/application/health_line.py` (new) | `HealthLine`, `BotCount`, `format_health_line`, `parse_health_line`, `health_lines_in`, `log_health_line` |
| `src/modules/operations/contracts/host_state.py` (new) | `HostState` |
| `src/modules/operations/module.py` (new), `src/shell/modules.py` | the `operations` module (D4), no hook yet; two lines in the module list |
| `tests/unit/modules/operations/application/test_health_line_format.py` (new) | format, round trip, malformed input, INFO level |
| `tests/unit/architecture/test_no_module_depends_on_operations.py` (new), `scanned_roots_registry.py` | the guard behind D4's "depended on by none", mutation-proved |
| `tests/unit/shell/test_unattended_log_defaults.py` (new) | shipped config, plain file handler, guide sentence and stanza |
| `tests/sanity/test_a_headless_boot_logs_cleanly.py` (new) | log scan, health line from real output, canary credentials, no log file |
| `Docs/VOCABULARY/README.md` | **Health line**, **Host state**; the module count is six |
| `Tasks/epics/EPIC-038_headless_operation/` | this task closed; hand-over criteria added to 038D, 038E, 038H; epic README, TRACKING and the epics index updated |

## 5. Testing
Tier: unit and sanity. Mutation-checked (each turned the named tests red, then reverted): a WARNING record carrying a credential written during the headless boot (log-scan and canary tests); `log.file` added to `app_config.json` (the two configuration tests); the guide sentence reworded (the pin).
- `test_the_health_line_round_trips_through_its_parser` · `test_the_health_line_text_is_pinned` · `test_the_health_line_in_the_real_log_output_parses_back` · `test_a_headless_boot_leaves_no_unexpected_warning_or_error_in_the_log`
- `test_the_log_file_growth_sentence_is_pinned_to_the_config_key` · `test_log_file_is_the_key_the_engine_reads_and_opens_a_plain_file_handler`
- `test_the_shipped_unit_and_wrapper_set_no_log_file`: **not written here**, handed to 038H (no unit file exists yet; a test over no files would pass vacuously).
Commit tier (`ci-local.ps1 -SkipTests`) PASS; the architecture, shell, sanity and `operations` suites green locally (970 passed). The full gate is GitHub Actions' `ci-local.ps1 -Full` on the PR head: not read yet.

## Implementation notes (written when done)
Written 2026-10-12 on branch `claude/epic-038g-unattended-logging` from `master-warrior` `d20065c`. Engine at the pinned `f4ef582`, untouched.

**Rotation is the supervisor's.** The Engine's console handler writes to `sys.stdout` (`std_logger.py`), so on systemd the journal captures and bounds it and under NSSM the wrapper does; the app's shipped config sets no `log.file`. What can still grow is an operator-set `log.file`, and `--dev`/`--debug` (which write `<data root>/logs/`); the guide says so, and gives the `copytruncate` stanza because `FileHandler` holds its file open.

**The `operations` module exists now, empty of hooks.** The task names `src/modules/operations/application/health_line.py`, and a package under `src/modules/` must be listed in `shell/modules.py` (`test_module_declarations`). That lands decision D4 (still *Proposed*) in a minimal form: a module with an id, no dependencies and a no-op `register()`. A `support/` package was rejected (the catalog guard demands a user outside the package, and the format is operations-specific); `shell/` was rejected by D4's own reasoning. If the owner overrules D4, the module is two files and one list entry to move. The shared file `src/shell/modules.py` was announced to the coordinator.

**The format.** The keys are DESIGN §6's, in its order, with its `up=…s` spelling. Unknown measurements are `na`, no bots is `none`. The parser ignores unknown keys, so a key appended later does not break an older monitor, and refuses a repeated or missing key. Construction is as strict as parsing (a negative age, a duplicate bot state, a bot state outside `[a-z_]+` cannot be built), so nothing written cannot be read back and no free text can carry a secret into the line.

**INFO by construction.** `log_health_line` is the only emitter and takes no level. A stale feed is a large `tick_age_s`; the escalation belongs to the alert source (`EPIC-036`).

**What the tests found.** Nothing wrong in the shipped logging: a headless boot with canary credentials produces no problem-level record, no credential, and no file. The canary tests were red under mutation, so they can fail.

## Resume
Done. Open follow-ups live in the receiving tasks: 038D (use `log_health_line`; re-point the sanity test at `run`), 038E (extend the canary test to the new backends), 038H (no `log.file` in the unit and the wrapper; link the guide). The `logrotate` stanza is untested against a real `logrotate` run; 038H's checklist is where it gets exercised.

**Review round 1 (PR #467, reviewer comment at `22ff154`).** Fixed: the canary test now proves the credential was read; the parser accepts ASCII digits only, at most 18, so an oversized or Arabic-Indic value raises `HealthLineError`; `health_lines_in` matches only a record whose message opens `[health] state=`, so a foreign record mentioning the tag is skipped while a malformed health record still raises; D4's "depended on by none" is now held by `test_no_module_depends_on_operations.py`; the DECISION's *Decided by* line and D6 row are current; the guide marks what 038D and 038H create; 038H must run the logrotate stanza in its checklist.
