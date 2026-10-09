# EPIC-038B — A command's result is an exit code and a report a script can read

**Status:** 🔵 Planned — not started
**Source:** the owner, 2026-10-09: *"--json on status commands, and exit codes documented"* (the brief's words; so scripts and monitoring can use the CLI).
**Risk:** 🟢 — additive port changes; the one behaviour change is that a failing command stops exiting 0
**Complexity:** M — a shared-kernel contract, two renderers, a pass over six existing handlers
**Epic:** [EPIC-038](../README.md)
**SPEC:** [SPEC-003](../../../../Docs/SPEC/SPEC-003_check_the_exchange_connection.md) (`exchange-status`) is updated for the `--json` form and the exit code.
**Design:** [DESIGN §4.1, §7, §8, §9](../DESIGN_2026-10-09_headless_operation.md) · **Research:** [§12](../RESEARCH_2026-10-09_headless_operation.md)
**Depends on:** None

---

## 1. Context and problem
`ICliCommandHandler.handle` returns `None` and "catches the domain's own errors and prints" (`src/core/contracts/i_cli_command_handler.py`); `main()` never calls `sys.exit` (`src/main.py`). A failed `sync` and a good one both exit 0. `--json` exists once, on `order-preview` (`cli_commands.json:95`), implemented inside that command's formatter, so a second format would be a second copy of every report.

## 2. Acceptance criteria
- [ ] `ExitCode` (`IntEnum`) and `CliOutcome` live in `core/contracts` with the table in DESIGN §7 (0, 1, 2, 3, 4, 5, 6, 10, 11); the table is also a documented section of the runbook source (038H) generated from the enum, so the two cannot differ.
- [ ] `ICliCommandHandler.handle` may return `CliOutcome | None`; `None` means success. **No existing handler is edited to keep working.** `main()` maps the outcome to `sys.exit`; an unexpected exception exits 1 after logging the traceback.
- [ ] The six existing commands report failure through an outcome: `sync` with no data, `exchange-status` with a failed connection (code 6 for exchange, 5 for missing credentials), `order-dry-run` rejected, and so on; each keeps its printed text.
- [ ] `Report` (a versioned JSON-ready `payload` plus a neutral `layout`) and `IReportRenderer` exist in `core/contracts`; `TextReportRenderer` and `JsonReportRenderer` are registered by name; `--json` selects the JSON one for every report command. `exchange-status` and `order-preview` use it; their text output is byte-identical to today's (a golden test).
- [ ] The JSON envelope is `{"schema": "sew.<command>/<n>", "generated_at": ISO-8601 UTC, "data": {...}}`; a test pins each command's field names so a rename is a visible failure.
- [ ] Adding a third renderer (the test uses a one-line `key=value` renderer) needs no edit to any command or to the CLI parser.
- [ ] A secret never appears in a payload: a test runs `exchange-status --json` with a recognisable fake secret in the environment and greps the output.

## 3. Design
Command → `Report` → renderer: the view-model and strategy pattern; a command knows the *what*, a renderer the *how* (single responsibility), and a new format is a new class (open/closed). The exit code is a value the handler returns, not an exception, so a handler stays testable without catching `SystemExit`; the optional return keeps Liskov substitution for every existing handler (they return `None` and mean success). Reuse: `--json` stays the flag (EPIC-021E's precedent); the parser, the table and `declare_cli` do not change. Alternatives: `click`/`typer` (a rewrite of the CLI and a new dependency; rejected — the table already exists), raising `CliExit(code)` (control flow by exception, harder to test).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/core/contracts/cli_outcome.py` (new) | `ExitCode`, `CliOutcome` |
| `src/core/contracts/report.py` (new) | `Report`, `IReportRenderer`, `IReportFormats` |
| `src/core/contracts/i_cli_command_handler.py` | return type widened |
| `src/main.py` | map outcome to exit; a failure of `app.boot()` exits 1 |
| `src/presentation/cli/*_cmd.py`, `exchange_status_formatter.py`, `order_*_formatter.py` | produce a `Report`; failures return an outcome |
| `src/config/cli_commands.json` | `--json` added where missing |
| `src/presentation/cli/report_renderers.py` (new) | the two renderers and the registry |

## 5. Testing
Tier: unit; one integration test that runs `main.py` as a subprocess against the fake exchange and checks `$?`.
- `test_a_handler_returning_none_exits_zero` · `test_a_failed_sync_exits_with_the_documented_code` · `test_an_unknown_exception_exits_one_and_logs_the_traceback`
- `test_exchange_status_text_is_unchanged` (golden) · `test_exchange_status_json_has_the_pinned_fields`
- `test_a_new_renderer_registers_without_editing_a_command`
- `test_the_exit_code_table_in_the_runbook_source_matches_the_enum`
- `test_no_secret_reaches_a_json_report`
Not run yet.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: `test_a_failed_sync_exits_with_the_documented_code`, red.
