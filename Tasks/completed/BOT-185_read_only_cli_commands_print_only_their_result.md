# BOT-185 — A command that only reads shows its result and nothing else; its log goes to a bounded file

**Status:** ✅ Done (2026-10-17)
**Board:** `main.py bot list` printed 74 log lines around the one table, because the Engine's console handler writes every INFO record of the read-only boot to stdout. Fix: a read-only command's records go to `<data root>/logs/cli-<ts>-<pid>.log` (one file per process, newest 40 kept, 512 KiB each), WARNING+ still reaches stderr, `--verbose` restores today's console log; `run` and writing commands are unchanged (`src/shell/cli_log_routing.py`).
**Source:** The owner, 2026-10-17, relayed by the coordinator session: *"for the read-only CLI commands (bot list/show, plan, alert test and the other short-lived commands that open a read-only copy), the console shows only the command's result; the log records go to a file; `--verbose` puts them back on the console as today"* and *"the new file needs a size-management mechanism"*.
**Risk:** 🟢 — no real money; the log of a read-only run moves from stdout to a file and stderr, and nothing that reads those commands' stdout (`--json`) sees a change except fewer lines on stderr.
**Complexity:** M — a handler set re-applied after each of the Engine's two `StdLogger` builds, a pruning rule, one flag on every parser, docs.
**Depends on:** None.

---

## 1. Context and problem
At `0889c02`, `main.py bot list` on an empty data root printed 74 lines to stdout: extension start/stop, `[data-root] … (overridden by SEW_DATA_ROOT)` ×7 (`src/core/repo_root.py` `data_root()` logs INFO on every call), `[instance] read-only`, scheduler lines, and `No bots.` in the middle. Cause: the Engine's `StdLogger` always builds a `StreamHandler(sys.stdout)` from `log.console.enabled`, and `create_app` builds it twice (before the bus, then in `LoggerExtension.register`), each build clearing the handlers of the `App` logger. `console_log_to(sys.stderr)` already moves it to stderr for `--json`, but moves the noise rather than removing it.

## 2. Acceptance criteria
- [x] A command declared `read_only` (`bot list`, `status`, …) prints only its result on stdout and nothing on stderr, and its records, including those of building the object graph, are in one `cli-*.log` under `<data root>/logs/`. Evidence: `test_a_read_only_command_prints_its_result_and_writes_its_log_to_a_file` (process), `test_create_app_keeps_the_routing_after_the_extension_rebuilds_the_logger` (real `create_app`).
- [x] `--verbose`, at any position on the line, puts the records on the console as today and writes no file. Evidence: `test_verbose_puts_the_log_back_on_the_console_and_writes_no_file`, `test_verbose_is_accepted_at_any_position`, `test_only_a_read_only_command_without_verbose_gets_its_log_routed_to_a_file`.
- [x] A WARNING, ERROR or CRITICAL stays visible on stderr in the log's own format, and a failed command still prints its message and exits non-zero. Evidence: `test_a_warning_reaches_the_console_and_the_file`, `test_a_failed_command_still_says_so_on_the_console`.
- [x] `--json` stays one document on stdout with an empty stderr. Evidence: `test_a_json_report_stays_one_document_with_a_quiet_error_stream`.
- [x] The log directory is bounded: at most `FILES_KEPT` (40) files, each capped at `MAX_FILE_BYTES` (512 KiB) with one backup, only `cli-*` files pruned. Evidence: `test_the_directory_keeps_at_most_files_kept_and_drops_the_oldest`, `test_a_file_is_capped_by_rotation_and_keeps_one_backup`.
- [x] A log directory that cannot be used costs the file, not the command. Evidence: `test_a_log_directory_that_cannot_be_used_costs_the_file_not_the_command`.
- [x] `run`, `sync` and every command that is not read-only are unchanged. Evidence: `test_only_a_read_only_command_without_verbose_gets_its_log_routed_to_a_file` (`sync` row), `test_without_routing_the_engine_still_writes_its_log_to_stdout`.

## 3. Design
**Seam.** `CliLogRouting` (`src/shell/cli_log_routing.py`) is a value naming the file; `apply()` removes the Engine's console handler (exactly `type(h) is StreamHandler`, so a `log.file`/`--dev` file handler is kept) and adds a size-capped file handler and a stderr handler at WARNING. `create_app(..., cli_log=None)` applies it after each of its two `StdLogger` constructions; `None` is today's behaviour, which is why the GUI, `run` and tests do not change. The Engine is not changed (`ONBOARDING.md` §2).

**Which commands.** The existing declaration: `command_is_read_only(commands, args)`, the same one that decides the read-only instance. No second list; a new read-only command is quiet by declaring `"read_only": true`.

**Size management — options considered** (decision recorded here, `CONSTITUTION.md` P5):

| Option | Cross-process safe | Bounded | Cost / verdict |
| :--- | :-: | :-: | :--- |
| One `RotatingFileHandler` file shared by all runs | **No**: concurrent renames lose records; on Windows the rename raises `PermissionError` while another process holds the file and `logging` prints it to stderr (CPython documents it as not multi-process safe) | yes | rejected |
| One file per day, pruned by age | yes (append) | by days, not bytes: a day is runs × ~7 KB, uncapped | needs a second rule for a runaway day; rejected |
| `logrotate` / `copytruncate` | yes | yes | root-owned stanza for a file an operator's account writes; Windows has none; rejected |
| **One file per process + prune the oldest at start + a per-file `RotatingFileHandler` cap** | **yes**: one writer per file, so the cap's rename is race-free | yes: ≤ 40 files × 512 KiB = 20 MiB | **chosen**: stdlib only, no lock, no daemon |

Residual: two runs starting together may both prune the same file (the loser finds it gone: `suppress(OSError)`) or leave a few files over 40 until the next start; the bound is soft by the number of simultaneous starters. Typical size is ~7 KB a run, so 40 files are a few hundred KB.

**Console.** WARNING+ goes to stderr, never stdout, so the table and the `--json` document own stdout. `run_command` already writes a failed command's message and traceback to stderr.

**Flag.** `--verbose` is a parent parser (`cli_parser.py` `_VERBOSE_PARENT`, `default=SUPPRESS`), not a `cli_commands.json` entry: it applies to all ~20 entries and their sub-verbs at any position, and a sub-parser's default can then never overwrite a flag the parent read. It is listed in every command's `--help`. `gui`/`shell` (launcher verbs) do not take it; they keep their log.

## 3a. Reuse
`command_is_read_only` (`.claude/rules/capabilities.md`: the read-only declaration) used; `console_log_to` used unchanged for `--json`/`--format` runs with `--verbose`; `data_root()` used through the new `log_directory()` that `load_app_config` now shares; no UI need.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/shell/cli_log_routing.py` | new: `CliLogRouting`, `prepare_cli_log`, pruning, caps |
| `src/shell/composition_root.py` | `create_app(cli_log=None)`; `apply()` after each `StdLogger` build; the decision line |
| `src/shell/app_config.py` | `log_directory()` (one place for `<data root>/logs`) |
| `src/main.py` | `_quiet_log_for`: routing for a read-only command without `--verbose`; passed through `_build_app` |
| `src/presentation/cli/cli_parser.py` | `--verbose` parent parser on the main parser and every command and sub-command |
| `.claude/rules/capabilities.md` | regenerated catalog row |
| `Docs/OPERATIONS/LOGGING.md` §1b, `headless_runbook.md` §10 | where the log goes, how to read it, `--verbose`, the size bound |
| `tests/unit/shell/test_cli_log_routing.py`, `tests/unit/presentation/cli/test_main_entry.py`, `tests/integration/presentation/test_read_only_commands_keep_their_log_off_the_console_process.py` | proof, including the two doubles of `create_app` gaining the new argument |

## 5. Testing
Unit and integration tiers as listed under §2. Mutation checks run: deleting the second `apply()` in `create_app`, and deleting the first, each turn `test_create_app_keeps_the_routing_after_the_extension_rebuilds_the_logger` red. Commit tier and the architecture guards: see the implementation notes. The full gate is GitHub Actions' `ci-local.ps1 -Full` on the PR head.

## 6. Docs touched
`Docs/OPERATIONS/LOGGING.md` §1b (new), `Docs/OPERATIONS/headless_runbook.md` §10. No `Docs/MODULES/` file: the shell has no module folder and no `src/modules/<m>/` file changed ("Design in step": `No design change`).

## Implementation notes (written when done)
- **Reproduced first**: `main.py bot list` on `SEW_DATA_ROOT=/tmp/sewdata`: 74 stdout lines, 0 stderr. After: `No bots.` on stdout, 0 stderr, a 74-line `cli-20261017-140143-905.log`, whose first line is `[cli-log] console shows warnings and errors only; records go to <path>`; `--verbose` after or before the verb prints the 74 lines again; `status --json` is one document.
- **The 7× `[data-root]` lines are not removed**: `data_root()` still logs INFO per call (now into the file). Deduplicating it is a separate change in `src/core/repo_root.py`; recorded, not done here.
- **Review round 1** (`e93797c`): `os.access` ignores ACLs on Windows, so an unwritable file would have printed a traceback per record; `prepare_cli_log` now proves writability by opening the file it names, with a test. The 40-file bound counts rotated backups as files, so it is soft by rotated runs too (wording fixed). `composition_root.py` is now exactly 400 lines: the next edit to `create_app` must split it.
- **A `log.file` or `--dev` file** is left alone, so a developer who set one gets both files. `--dev`/`--debug` are not accepted by headless commands (the parser rejects them), so they never meet this routing.
- **Not verified**: the Windows rename failure that rules out a shared rotating file is documented behaviour of CPython's `RotatingFileHandler`, not reproduced here (Linux container); the chosen design never renames a file another process holds. The 40-file prune under real simultaneous starters is reasoned, not stress-tested.
- Delivery state: pushed to `claude/quiet-cli-console-log-BOT-185`, draft PR; reviewer and coordinator handoff recorded in the PR.
