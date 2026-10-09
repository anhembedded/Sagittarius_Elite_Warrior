# EPIC-038C — One bot status read model: `status`, `bot list`, `bot show` and the health snapshot file

**Status:** 🔵 Planned — not started
**Source:** the owner, 2026-10-09; the brief asked for "a presentation-agnostic port for anything the CLI needs, e.g. a bot status read model" and `--json` on status commands.
**Risk:** 🟡 — a new read model beside two that are planned (`EPIC-035W` health strip, `EPIC-036E` heartbeat); three consumers that disagree is the failure to avoid
**Complexity:** M — a read model, a contributor hook, a snapshot sink and file, three commands
**Epic:** [EPIC-038](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) is read for the bot states; SPEC-015 (new, written by 038D) lists `status`.
**Design:** [DESIGN §4, §5.2, §8](../DESIGN_2026-10-09_headless_operation.md) · **Research:** [§1, §7, §12, §13](../RESEARCH_2026-10-09_headless_operation.md)
**Depends on:** [EPIC-038B](EPIC-038B_exit_codes_and_output_formats.md) (`Report`, exit codes). Embeds [`EPIC-035W`](../../EPIC-035_spot_grid_unattended_safety/incomplete/EPIC-035W_the_bots_health_is_visible_on_screen.md)'s per-bot health when that exists.

---

## 1. Context and problem
A person can see a bot's state only on the Bots screen. A script, a monitor or the owner over SSH has nothing: no command lists bots, no file says whether a host is alive, and "alive" means different things (R1): the process exists, the bots are in the right state, the feeds are fresh. A second process cannot ask the first (the second copy is read-only; no port is opened, D5), so the first must leave its view on disk. `EPIC-035W` and `EPIC-036E` each plan a health snapshot; this task must be the one place that builds it or a consumer of theirs, never a third.

## 2. Acceptance criteria
- [ ] `BotStatusReport` (frozen) is built by one application query from `ListBotsQuery`/`GetBotQuery` results: per bot id, name, kind, venue, symbol, state, reason, `run_started_at`, plus a free `health` mapping that stays empty until `EPIC-035W` exists, and then carries its snapshot **unchanged**. A test shows the GUI's list and `bot list` agree on every bot of a seeded store.
- [ ] `IOperationsRegistry.declare_health` and the `declare_operations` hook exist (default no-op, like `declare_cli`); bots, trading (user-stream state and age, clock skew) and market_data (last tick age per symbol) each contribute a section; a contributor that raises or blocks is reported as `unavailable` and never fails the snapshot (a deadline per contributor, injected clock).
- [ ] `FileHealthSnapshotSink` writes `state/health.json` atomically (temp file + rename) with `schema`, `app_version`, `pid`, `started_at`, `written_at`, `host_state` and one object per contributor; no secret and no balance (a test greps it).
- [ ] `status [--json]` decides the host state from the lock (`IInstanceProbe.is_held`) **and** `written_at` within three health intervals: `running`, `stale`, `not running`; exits 0, 11 or 10. It reads bot files the way a read-only copy does and works while the host runs.
- [ ] `status --watch [--interval n]` repeats the same `Report` through the same renderer (D1's replacement for a TUI); it exits on Ctrl-C with 0.
- [ ] `bot list` and `bot show <id>` print the read model; `--json` works; an unknown id exits 2 with a plain message.
- [ ] A bot file this build cannot read is shown as `unreadable` with its path, not hidden (the restore service already refuses and leaves such a file untouched).
- [ ] A fourth section, added by a test-only contributor, appears in the snapshot, in `status` and in `--json` with **no edit** to the publisher, the sink or the handler.

## 3. Design
Read model (CQRS query side) behind a port the CLI, the health line, the future heartbeat and the health strip share; the `Report` of 038B is its output. Contributors follow the proven contribution pattern (`declare_cli`/`ICliRegistry`) instead of `operations` importing every module (open/closed). The snapshot file is a handoff between processes in the *Blackboard* style, chosen over an RPC because it opens nothing (R11); the lock is the liveness proof the file cannot give after a crash (R1). Decision D5 is the proposal this task implements.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/core/contracts/i_operations_registry.py` (new), `bounded_context_module.py` | registry port and the default-no-op hook |
| `src/modules/operations/` (new, per D4) | `HealthSnapshot`, `IHealthContributor`, `HealthPublisher`, `IHealthSnapshotSink`, `FileHealthSnapshotSink`, `StatusQuery`, `IInstanceProbe` adapter |
| `src/modules/bots/`, `trading/`, `market_data/` `module.py` | `declare_operations` with one contributor each |
| `src/modules/bots/cli/` (new) | `bot list`, `bot show` |
| `src/config/cli_commands.json` | `status`, `bot` (subparsers) |
| `src/infrastructure/single_instance/` | `is_held` probe |

## 5. Testing
Tier: unit with fakes; one integration test starting a real app in-process (no exchange) and reading its file.
- `test_status_agrees_with_the_bots_screen_list_for_a_seeded_store`
- `test_a_stale_snapshot_with_the_lock_free_reports_not_running` · `test_a_fresh_snapshot_with_the_lock_held_reports_running` · `test_an_old_snapshot_with_the_lock_held_reports_stale`
- `test_the_snapshot_is_written_atomically` (kill between write and rename leaves the old file intact)
- `test_a_contributor_that_raises_is_unavailable_not_fatal` · `test_a_slow_contributor_is_cut_off_at_its_deadline`
- `test_a_new_contributor_needs_no_edit_to_the_publisher`
- `test_the_snapshot_contains_no_secret` · `test_an_unreadable_bot_file_is_listed_with_its_path`
- `test_status_exit_codes_are_0_10_11`
Not run yet.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: check the state of `EPIC-035W` and `EPIC-036E` and record whether either has defined a snapshot yet; if so, consume it.
