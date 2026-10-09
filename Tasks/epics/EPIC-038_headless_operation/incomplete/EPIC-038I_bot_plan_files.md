# EPIC-038I — Bots are described in a plan file a person can review, and `bot apply` makes the app match it

**Status:** 🔵 Planned — not started
**Source:** the owner, 2026-10-09; the brief asked to research "config and bot-plan files in version control"; with no GUI, creating a bot by hand-typed arguments is the gap between a booted host and a running bot.
**Risk:** 🟡 — a file that changes money-handling state; a plan that deletes or edits a running bot by mistake
**Complexity:** M — a schema, a diff, an idempotent apply through existing commands
**Epic:** [EPIC-038](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) is updated for the plan-driven journey.
**Design:** [DESIGN §5.3, §6](../DESIGN_2026-10-09_headless_operation.md) · **Research:** [§14](../RESEARCH_2026-10-09_headless_operation.md)
**Depends on:** [038B](EPIC-038B_exit_codes_and_output_formats.md), [038C](EPIC-038C_bot_status_read_model.md); `--start-planned` is consumed by [038D](EPIC-038D_run_host.md).

---

## 1. Context and problem
On the desktop a bot is built through the Bots screen's steps; on a server there is no such screen, and a long argument list is not reviewable or repeatable. Freqtrade layers several config files and says to keep secrets in a separate one; it does not discuss version control (R14). The risk for this app is a plan file holding a key, or an apply that edits a RUNNING bot behind the lifecycle table's back.

## 2. Acceptance criteria
- [ ] A plan file (JSON, versioned `schema`) lists bots: `name`, `kind`, `venue`, `symbol`, the kind's parameters in the same shape `CreateBotCommand` takes, and `desired_state` (`running` | `stopped`). It has **no field for a key, a secret or an account identifier**; a loader rejects an unknown field (a test with a `api_key` field fails).
- [ ] `bot apply <plan> --dry-run` prints a diff: create / edit / delete / leave, and what `desired_state` means for each; `--json` supported. Nothing is changed.
- [ ] `bot apply <plan>` is idempotent: a second run reports "no changes" and exits 0. It creates and edits through `CreateBotCommand`/`EditBotCommand`, and deletes only with `--prune` and only a bot at rest; every change goes through `ICommandDispatcher` so the lifecycle table and the read-only rule apply (exit 3 when another copy holds the data root).
- [ ] An edit that the lifecycle table refuses for the bot's current state (a RUNNING bot's range) is reported as "needs stop first" exit 2; nothing is half-applied (each bot is applied independently and the result lists all).
- [ ] The identity of a plan entry is its `name` + `venue`; renaming is a delete and a create, and the diff says so.
- [ ] `bot export <id|--all>` writes a plan from the stored bots (round trip: `export` then `apply --dry-run` is "no changes").
- [ ] A test greps a plan produced by `export` and the dry-run output for the fake secrets in the environment: none.
- [ ] `run --start-planned` (038D) reads the same file's `desired_state`.

## 3. Design
Declarative desired state with an idempotent apply (the Kubernetes/Terraform shape), expressed as a thin driver over the existing commands, so the plan path and the screen path are one path (D2). Bot kinds supply their own parameter schema through the existing kind catalog (`IBotKindCatalog`), so a new bot kind needs no change here (open/closed). Alternatives: editing the bots' store files directly (bypasses the lifecycle table — the sibling-path failure class), a plan in the user config (mixes secrets-adjacent settings with reviewable data).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/cli/bot_apply_action.py`, `bot_export_action.py` (new) | the two verbs |
| `src/modules/bots/application/plan/` (new) | `BotPlan`, loader, differ |
| `src/config/cli_commands.json` | `bot apply`, `bot export` |
| `Docs/OPERATIONS/headless_runbook.md` | plan files and version control |

## 5. Testing
Tier: unit and integration (real handlers, in-memory store, the fake exchange).
- `test_apply_twice_changes_nothing_the_second_time` · `test_dry_run_changes_nothing` · `test_export_then_dry_run_is_no_changes`
- `test_a_plan_with_a_key_field_is_rejected` · `test_no_secret_reaches_a_plan_or_a_diff`
- `test_a_running_bots_range_edit_is_refused_by_the_lifecycle_table_through_apply`
- `test_prune_deletes_only_bots_at_rest`
- `test_a_second_copy_exits_three_on_apply`
- `test_a_new_bot_kind_needs_no_change_in_the_plan_code`
Not run yet.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: read the Create/Edit command shapes and the kind catalog and record the plan schema.
