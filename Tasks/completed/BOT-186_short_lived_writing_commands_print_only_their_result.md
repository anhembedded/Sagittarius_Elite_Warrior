# BOT-186 — A short-lived command that writes (`bot apply`, `trade-once`) shows only its result; the registry says which commands keep the console log

**Status:** ✅ Done (2026-10-17)
**Board:** After BOT-185 `main.py bot apply plan.json --prune` still printed the full INFO log, because the quiet routing covered only `"read_only": true` commands. Fix: two explicit registry declarations, `short_lived` (quiet like a reader) and `keeps_console_log` (`run`, `sync`, `stream`), one rule `command_keeps_log_off_console`, and a guard that fails until every command declares a side (`src/support/cli_host/command_access.py`, `src/config/cli_commands.json`).
**Source:** The owner, 2026-10-17, via the coordinator session (decision "A"), confirmed in this session as *"làm đi bạn"* ("go ahead"): extend the quiet routing to the short-lived writing commands, not `run`, decided from the registry, with a guard.
**Risk:** 🟡 — `trade-once --live` can place a real order; its INFO records move to the file, while its printed result and every WARNING/ERROR stay on the console. No order logic changes.
**Complexity:** S — two registry keys, one function, six declarations, a guard, docs.
**Depends on:** BOT-185 (merged, `8fb1edf`).

---

## 1. Context and problem
At `9161a85` the routing of BOT-185 is selected by `command_is_read_only`. The VPS owner ran `bot apply plan.json --prune`, a writer that ends by itself, and still saw ~70 INFO lines around the report. The command list in `cli_commands.json` holds: readers (`status`, `bot list|show|export|stop|pause|resume|start`, `alert test`, `preflight`, `exchange-status`, `order-preview`, `order-dry-run`), one-shot writers (`bot apply`, `trade-once`), and commands that run until told to stop or whose log is their output (`run`, `sync`, `stream start|stop`). `bot create/edit/delete` are not commands here: `bot apply` creates, edits and deletes (`--prune`) through the plan.

## 2. Acceptance criteria
- [x] `bot apply plan.json --prune` prints its report and nothing else on stdout, nothing on stderr, and its records are in a `cli-*.log`. Evidence: `test_a_short_lived_writing_command_is_quiet_too` (real process on a real data root; the log says `[instance] writable`, so it is the writing path, not the read-only one).
- [x] `--verbose` puts a short-lived writer's log back on the console. Evidence: `test_verbose_puts_a_short_lived_writers_log_back_on_the_console`; `test_only_a_read_only_command_without_verbose_gets_its_log_routed_to_a_file` rows for `bot apply`.
- [x] `run`, `sync`, `stream start` and `stream stop` keep the console log. Evidence: `test_the_commands_the_owner_named_are_on_the_side_the_owner_chose`, `test_a_command_keeps_its_log_off_the_console_when_it_reads_or_is_short_lived`.
- [x] The selector comes from the registry, not a name list, and a new command must declare a side. Evidence: `test_a_command_says_which_side_of_the_console_it_is_on` (one case per command, built from the real `cli_commands.json`); mutation run: removing `short_lived` from `trade-once` turns that case and the named-commands case red.
- [x] The `bot apply` table and the mainnet confirmation prompts stay visible. The report is `print_report` to stdout and the mainnet gate is the `--confirm-venue` flag whose refusals are `CliOutcome` messages on stderr; neither goes through the log, and no file of those commands changed.

## 3. Design
**Seam, as BOT-185 left it.** `main._quiet_log_for(quiet, args)` takes the decision; this task changes only where it comes from: `command_keeps_log_off_console(commands, args)` = not `keeps_console_log` and (`read_only` or `read_only_when` or `short_lived`). `keeps_console_log` wins over both, so a reader that must stream (none today) opts out explicitly.

**Why two declarations and a guard, not a derived rule.** "Writes and ends by itself" cannot be derived from the existing keys (`requires_writable`, `owns_lifecycle` describe `run` only), and a default of "quiet unless declared" would silence a future long-running command by accident, which is how an operator loses the only progress display it has. Explicit beats derived here (P7: the seam is the registry; the variants are one line each). The guard reads the real file, one test case per command.

**Classification and the one judgement call.** `sync` keeps its console log: it prints nothing on success, so its INFO lines are its progress for a job that can take minutes; silencing it would leave a blank terminal. `stream start` blocks until Ctrl-C; `stream stop` is the same command function. `trade-once` is quiet: it is one round and exits, and prints its decision, order result and refusals itself. It can trade real money with `--live`, so the owner may veto this one row by moving `trade-once` to `keeps_console_log` (one line, one test row).

## 3a. Reuse
`command_access.py` (`_declared`, `command_is_read_only`) extended in place; `prepare_cli_log`/`CliLogRouting` (BOT-185) unchanged; no UI need.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/support/cli_host/command_access.py` | `SHORT_LIVED_KEY`, `KEEPS_CONSOLE_LOG_KEY`, `command_keeps_log_off_console`; module docstring |
| `src/config/cli_commands.json` | `short_lived` on `bot apply`, `trade-once`; `keeps_console_log` on `run`, `sync`, `stream start`, `stream stop` |
| `src/main.py` | `_quiet_log_for` takes the quiet decision from the new function |
| `Docs/OPERATIONS/LOGGING.md` §1b, `headless_runbook.md` §10 | the four sides, the guard, which commands keep the log |
| tests | the guard, `test_command_access.py`, `test_main_entry.py` rows, two process tests |

## 5. Testing
As §2. Commit tier and the touched suites: see the implementation notes.

## 6. Docs touched
`Docs/OPERATIONS/LOGGING.md` §1b, `Docs/OPERATIONS/headless_runbook.md` §10. No `Docs/MODULES/` file: no `src/modules/<m>/` code changed.

## Implementation notes (written when done)
- The two command keys are not argparse flags, so `--help` is unchanged; `--verbose` (BOT-185) is the only operator-facing switch.
- Not verified: `trade-once` was not run live (no exchange here); its quiet path is proved by the registry and `main` tests, not by a process run against the fake exchange.
- `composition_root.py` is untouched, so its 400-line note from BOT-185 still stands.
