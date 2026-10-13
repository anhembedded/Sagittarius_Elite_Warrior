# EPIC-038I — Bots are described in a plan file a person can review, and `bot apply` makes the app match it

**Status:** ✅ Done (2026-10-13)
**Source:** the owner, 2026-10-09; the brief asked to research "config and bot-plan files in version control"; with no GUI, creating a bot by hand-typed arguments is the gap between a booted host and a running bot.
**Risk:** 🟡 — a file that changes money-handling state; a plan that deletes or edits a running bot by mistake
**Complexity:** M — a schema, a diff, an idempotent apply through existing commands
**Epic:** [EPIC-038](../README.md)
**Branch:** `claude/epic-038i-bot-plan`
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) §3.1 (the plan-driven journey) and [SPEC-015](../../../../Docs/SPEC/SPEC-015_run_the_bots_headless.md) (`--start-planned`) are updated.
**Design:** [DESIGN §5.3, §6](../DESIGN_2026-10-09_headless_operation.md) · **Research:** [§14](../RESEARCH_2026-10-09_headless_operation.md) · **Decision:** [D2, D9, O3, O8](../DECISION_2026-10-09_headless_operation.md)
**Depends on:** [038B](EPIC-038B_exit_codes_and_output_formats.md), [038C](EPIC-038C_bot_status_read_model.md); `--start-planned` is consumed by [038D](EPIC-038D_run_host.md).

---

## 1. Context and problem
On the desktop a bot is built through the Bots screen's steps; on a server there is no such screen, and a long argument list is not reviewable or repeatable. Freqtrade layers several config files and says to keep secrets in a separate one; it does not discuss version control (R14). The risk for this app is a plan file holding a key, or an apply that edits a RUNNING bot behind the lifecycle table's back.

## 2. Acceptance criteria
- [x] A plan file (JSON, versioned `schema`) lists bots: `name`, `kind`, `venue`, `symbol`, the kind's parameters in the same shape `CreateBotCommand` takes, and `desired_state` (`running` | `stopped`). It has **no field for a key, a secret or an account identifier**; a loader rejects an unknown field (a test with a `api_key` field fails).
  - **Evidence:** `BotPlanDocument`/`PlannedBot` and `parse_plan` (`application/plan/`): schema `sew.bot-plan/1`, fields `name`, `kind`, `venue`, `symbol`, `params`, `desired_state`; every unknown field, at the top and in a bot, is refused naming **the path and what was expected, never a value and never a field or parameter name** (a key pasted as a field name leaks as readily as one pasted as a value); a parameter named like a secret is refused too, by position (`test_bot_plan_parser.py`: `api_key`, `client_secret`, `api_secret`, `account_id`, `private_key` each rejected, a canary planted in the schema, kind, venue, desired state, field and parameter names and values never in any message; mutation: ignoring unknown bot fields turns four tests red). The kinds come from `IBotKindCatalog`, so a new kind needs no change (`test_a_new_kind_in_the_catalog_needs_no_change_in_the_plan_code`).
- [x] `bot apply <plan> --dry-run` prints a diff: create / edit / delete / leave, and what `desired_state` means for each; `--json` supported. Nothing is changed.
  - **Evidence:** `PlanApplier.diff` and `apply_report`: `create`/`edit`/`delete`/`leave`/`blocked` per entry with the meaning of `desired_state` for the bot as it is; `--json` is `sew.bot-apply/1` (keys pinned). A dry run dispatches nothing and writes nothing (`test_a_dry_run_dispatches_nothing_and_writes_nothing`, `test_a_dry_run_prints_the_diff_and_changes_nothing`; mutation: a dry run that applies turns three tests red). It is read-only for the entry point (`"read_only_when": "dry_run"`, below), so it runs beside a host (`test_beside_a_running_host_apply_exits_three_but_a_dry_run_and_an_export_work`).
- [x] `bot apply <plan>` is idempotent: a second run reports "no changes" and exits 0. It creates and edits through `CreateBotCommand`/`EditBotCommand`, and deletes only with `--prune` and only a bot at rest; every change goes through `ICommandDispatcher` so the lifecycle table and the read-only rule apply (exit 3 when another copy holds the data root).
  - **Evidence:** a second apply reports "No changes." and exits 0, dispatching no command and not rewriting the record (`test_applying_twice_changes_nothing_the_second_time`; mutation: always rewriting the record turns it red; process: `test_apply_creates_the_bot_then_says_no_changes_and_leaks_no_secret`). Creates, edits and deletes are `CreateBotCommand`/`EditBotCommand`/`DeleteBotCommand` through `ICommandDispatcher` against the real handlers; `--prune` deletes only what `permits_delete` (the lifecycle table) allows, for every lifecycle state. A second copy exits **3** for a real apply and changes nothing (`test_a_second_copy_exits_three_on_apply_and_changes_nothing`; process: `test_beside_a_running_host_...`).
- [x] An edit that the lifecycle table refuses for the bot's current state (a RUNNING bot's range) is reported as "needs stop first" exit 2; nothing is half-applied (each bot is applied independently and the result lists all).
  - **Evidence:** the differ asks `permits_edit(state)` (the table, for every state: `test_a_changed_parameter_is_an_edit_only_where_the_lifecycle_table_permits_it`) and reports "needs stop first, the bot is RUNNING"; the verb exits 2 and the other entries are still applied and listed (`test_a_blocked_entry_exits_two_names_stop_first_and_still_applies_the_rest`); on the composed app the table's own refusal leaves the RUNNING Grid's range untouched (`test_a_running_bots_range_edit_is_refused_by_the_lifecycle_table_on_the_real_app`). A blocked entry is **not recorded** as wanted, so `--start-planned` cannot start parameters the operator did not get.
- [x] The identity of a plan entry is its `name` + `venue`; renaming is a delete and a create, and the diff says so.
  - **Evidence:** the differ groups stored bots by `(name, venue)`; the same name on another venue is another bot; two stored bots with one identity block the entry and name both; a rename shows as a create plus (with `--prune`) a delete whose detail says "a rename is a delete and a create" (`test_a_rename_is_a_delete_and_a_create_and_the_diff_says_so`). A change of **kind or symbol** on a matching entry is blocked as "a new bot" (`EditBotCommand` keeps both).
- [x] `bot export <id|--all>` writes a plan from the stored bots (round trip: `export` then `apply --dry-run` is "no changes").
  - **Evidence:** `bot export (--all | --bot-id ID) --output FILE` (`export_plan`); the file is created exclusively and never overwritten; `export` then `apply --dry-run --prune` is "no changes" in unit and in two processes (`test_export_then_a_dry_run_is_no_changes`, `test_export_then_a_dry_run_is_no_changes_as_processes`). The id is a flag and the output a required file because the positional-list form needs `nargs`, which the CLI declaration does not have, and standard output carries the Engine's console log.
- [x] A test greps a plan produced by `export` and the dry-run output for the fake secrets in the environment: none.
  - **Evidence:** `test_an_exported_plan_and_its_diff_hold_no_secret_from_the_environment` (a canary key and secret in the environment); the process tests grep the apply/list/export outputs, the plan file, the record and the host's log for the fake secret; the record file holds ids, names, venues and states only (`test_the_record_file_holds_ids_names_venues_and_states_only`).
- [x] `run --start-planned` (038D) reads the same file's `desired_state`. **Handed over by [038D](../completed/EPIC-038D_run_host.md) (2026-10-13):** 038D built the host side and left the plan unwritten: `IBotPlan` (`bots/contracts/i_bot_plan.py`: `exists()` and `wants_running()`) is bound to `NoBotPlan` in `bots/composition/state_bindings.py`. This task binds an adapter that reads the `desired_state` `bot apply` recorded, in place of `NoBotPlan`; the start step and the mainnet confirmation (`--confirm-venue`, decision O8) need no change. A test starts a real `run` with a plan and a stopped planned bot and finds it RUNNING on the fake exchange.
  - **Evidence:** `AppliedBotPlan` (an `IBotPlan` over `IAppliedPlanStore`, the record `bot apply` writes to `state/bot_plan.json` beside the bots folder) replaces `NoBotPlan` in `state_bindings.py`; the start step and the mainnet confirmation are unchanged. In-process on the composed app and the fake Binance server: apply, then `StartPlannedBots` → the planned Grid is RUNNING with its ladder resting, the one wanted stopped stays DRAFT (`test_apply_creates_the_bots_and_start_planned_starts_only_the_ones_that_want_to_run`). As processes: `bot apply` then `run --start-planned` asks for a start of exactly the planned bot (`test_a_real_run_with_start_planned_starts_exactly_the_bot_the_plan_wants_running`); that the process's bot then *halts* is the process fake's limit (no user-data stream), so RUNNING is proven in-process. **No plan, or a record it cannot read, is exit 5 before anything boots** (`test_start_planned_needs_a_readable_plan.py`, `test_run_start_planned_with_no_applied_plan_exits_five_and_boots_nothing`, `..._a_damaged_record_...`); the damaged record's content is never echoed.

## 3. Design
Declarative desired state with an idempotent apply (the Kubernetes/Terraform shape), expressed as a thin driver over the existing commands, so the plan path and the screen path are one path (D2). Bot kinds supply their own parameter schema through the existing kind catalog (`IBotKindCatalog`), so a new bot kind needs no change here (open/closed). Alternatives: editing the bots' store files directly (bypasses the lifecycle table — the sibling-path failure class), a plan in the user config (mixes secrets-adjacent settings with reviewable data).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/cli/bot_apply_action.py`, `bot_export_action.py` (new) | the two verbs |
| `src/modules/bots/application/plan/` (new) | `BotPlan`, loader, differ |
| `src/config/cli_commands.json` | `bot apply`, `bot export` |
| `Docs/OPERATIONS/headless_runbook.md` | plan files and version control |

## 3a. Reuse
Checked `.claude/rules/capabilities.md` (generated catalogue) and the code before building; each row is `used <symbol>` or `not used because ...`.

| Need | Result |
| :--- | :--- |
| Create, edit and delete a bot | used `CreateBotCommand`, `EditBotCommand`, `DeleteBotCommand` through `ICommandDispatcher` (the Bots screen's own commands); the apply writes no bot file |
| Read the stored bots | used `ListBotsQuery` / `BotSnapshot` (the Bots tab's read) |
| What the lifecycle table allows | used `bot_lifecycle_fsm_matrix` (`is_declared`, `next_target`); gained `permits_edit`, `permits_delete` and `restarts_into_recovering` beside the transitions they read, so no second list of states exists |
| The kinds of bot | used `IBotKindCatalog`; the plan code names none |
| Declare a CLI verb | used the `bot` command's `subparsers` in `cli_commands.json` and `BOT_VERBS`/`IBotVerb` (two entries); `BotVerbWorld` carries the extra collaborators |
| Print a report, text or JSON | used `Report`, `IReportPrinter`, `emit_report` (`sew.bot-apply/1`, `sew.bot-export/1`) |
| The lock, exit 3 | used `IInstanceAccess` (`read_only`, `reason`) and `ExitCode.LOCK_HELD`; the entry point's lock decision uses the existing `command_access` with one new declaration, `read_only_when` |
| Exit codes | used `ExitCode`/`CliOutcome` (D9): 2 for a bad plan or request, 3 for a held lock, 5 for a `run` that has no readable applied plan |
| The host's plan seam | used `IBotPlan` and `StartPlannedBots` (038D); `IBotPlan` gained `problem()` |
| The host's start of a bot | used `StartBotForHostCommand` and the O8 `--confirm-venue` refusal unchanged |
| Write a file atomically | used the write-temp-then-rename shape of `FileHealthSnapshotSink`; not shared because the sink writes a snapshot, not a record (one small function in `FileAppliedPlanStore`) |
| Doubles | derived from the ABCs (`IBotKind`, `IAppliedPlanStore`); the command dispatcher routes to the real handlers over the verified `FakeBotStore` |

## 5. Testing
Tier: unit, integration (in process on the composed app) and integration (real processes, BUG-199's boundary).
- `test_apply_twice_changes_nothing_the_second_time` · `test_dry_run_changes_nothing` · `test_export_then_dry_run_is_no_changes`
- `test_a_plan_with_a_key_field_is_rejected` · `test_no_secret_reaches_a_plan_or_a_diff`
- `test_a_running_bots_range_edit_is_refused_by_the_lifecycle_table_through_apply`
- `test_prune_deletes_only_bots_at_rest`
- `test_a_second_copy_exits_three_on_apply`
- `test_a_new_bot_kind_needs_no_change_in_the_plan_code`
All of the above exist under the names below (the task's list is a floor):
- unit `tests/unit/modules/bots/application/plan/`: `test_bot_plan_parser.py`, `test_plan_differ.py`, `test_plan_applier.py`, `test_plan_export_and_record.py`; `tests/unit/modules/bots/cli/test_bot_plan_verbs.py`; `tests/unit/support/cli_host/test_command_access.py` (`read_only_when`); `test_host_steps.py` (the plan that wants nothing);
- integration `tests/integration/modules/bots/test_bot_apply_then_start_planned_on_the_fake_exchange.py`, `tests/integration/modules/operations/test_start_planned_needs_a_readable_plan.py`;
- processes `tests/integration/presentation/test_bot_plan_process.py` (7 tests; exit 3 beside a host, a dry run and an export beside it, exit 5 for `run --start-planned`, no secret anywhere).
Mutation checks (each turned a test red, then reverted): the edit permission, recording a blocked entry, always rewriting the record, ignoring unknown bot fields, removing the `run` refusal, a dry run that dispatches.

## Implementation notes (written when done)
**Decisions the epic's records did not settle** (made on the evidence, grounded in D2/D9/O8; the owner may veto):
1. **The host reads what was applied, not the file.** `run --start-planned` reads `state/bot_plan.json` (beside the bots folder, never inside it, where it would be read as a bot), the record `bot apply` writes, keyed by bot id. The plan file names bots by name+venue; only apply knows the ids. An edit to the plan file counts once it is applied; the host never starts a bot from a file nobody reviewed with `--dry-run`.
2. **A missing or unreadable applied plan refuses `run --start-planned` with exit 5, before anything boots.** D9: only the operator can fix it, and a restart cannot, so the unit must not restart it (`RestartPreventExitStatus` covers 5). It is not exit 2 (a usage error is an argument; this is state under the data root). An unreadable record is a *problem*, never an empty plan: `IBotPlan.problem()`, and `wants_running()` raises on it. `bot apply` with a bad plan *file* is exit 2 (an argument).
3. **Applying never starts or stops a bot.** `desired_state` is recorded; the diff says what it will mean. A RUNNING bot whose plan says `stopped` is left (the dry run says "apply does not stop a bot").
4. **A blocked or refused entry is not recorded** as wanted, so `--start-planned` cannot start parameters the operator did not get; the others are applied (each bot independently) and the verb exits 2.
5. **`bot apply --dry-run` is read-only for the entry point** (`"read_only_when": "dry_run"`, a small extension of `command_access.py`): it neither takes the lock nor boots as the writable copy (whose boot applies the restart rule to the bots), and it works beside a running host. A real apply on a read-only copy exits 3 from the verb, and nothing is dispatched.
6. **Kind or symbol cannot be edited in place** (`EditBotCommand` keeps both): the entry is blocked with "a new bot - name it differently and use --prune".
7. **Stored bots the plan does not name are left alone** unless `--prune`; bot files this build cannot read are listed as a note and are not part of the comparison.
8. **`bot export` needs `--output`** and never overwrites: standard output carries the Engine's console log, and the CLI declaration has no `nargs` for a list of ids (`--bot-id` takes one).
9. **A real `bot apply` is a writable boot.** The application boots as the writable copy, so the restart rule runs first: a RUNNING or PAUSED bot on disk becomes RECOVERING before the diff is read. `--dry-run` boots read-only and shows the states as the files record them. The diff's "will start it" is promised only for a bot at rest (`AT_REST_STATES`, the rule the host asks); a HALTED, ERROR, STARTING or STOPPING bot gets "will not start it".
10. **The runbook** (`Docs/OPERATIONS/headless_runbook.md`) does not exist yet (`EPIC-038H` writes it); the operator-facing text is SPEC-014 §3.1, SPEC-015 and `--help`, and 038H is told to carry the "plan files and version control" section.

**Findings the task text lacked:** `NoBotPlan` is deleted (nothing used it); `IBotVerb.run` takes a `BotVerbWorld` now (it was `(args, dispatcher, printer)`); the status report gained no field here (`recovers_on_restart` was 038D's). The process-level fake exchange has no user-data stream, so a Grid started in a process halts a moment later; the in-process composed-app journey is the proof of RUNNING. `bot list` shows an applied-then-unstarted bot as DRAFT, and an edited STOPPED bot lands on DRAFT (the table), so a re-applied edit of a stopped bot needs `run --start-planned` (or the Start button) again.

## Resume
Done. Open items elsewhere: `EPIC-038H` carries the runbook section on plan files and version control and the `TimeoutStopSec` formula; a `bot resume`/control of a running host stays `EPIC-038J` (O4).
