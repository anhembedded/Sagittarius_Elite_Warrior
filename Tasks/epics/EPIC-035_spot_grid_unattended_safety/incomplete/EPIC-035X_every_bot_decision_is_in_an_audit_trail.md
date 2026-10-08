# EPIC-035X — Every bot decision is in an audit trail

**Status:** 🔵 Planned — requested by the owner on 2026-10-08, who asked that it **not be started yet**
**Source:** the owner's request of 2026-10-08, relayed by the coordinator session; extends the Spot Grid audit (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz). Phase 3 of [EPIC-035](../README.md).
**Risk:** 🟡 — a new durable store on the path of every decision, and a secret-leak surface
**Complexity:** L
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** EPIC-035C (state transitions and halts carry a reason); [`EPIC-035K`](EPIC-035K_alerts_reach_a_user_who_is_away.md) quotes this journal, so 035X lands before it or with it

---

## 1. Context and problem
The owner had to read a raw dev log to learn why the bot cancelled all its orders (`RUNNING -> HALTED on halt (inventory_mismatch …)`); the UI did not explain it. Decisions live in log lines, which rotate, mix with everything else and carry no stable reason code. Verify the current record on the running app and in `src/modules/bots/application/services/bot_run_state.py` before coding.

This task is specified briefly: it is Phase 3 — Alerting and transparency. The full acceptance criteria are re-confirmed against the code when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] A durable, per-bot, append-only journal of decisions with their reasons and inputs:
  - state transitions with their reason;
  - orders sent, cancelled, filled or rejected, with the client order id;
  - reconcile results with the numbers compared;
  - SL/TP triggers, with the price seen and its age;
  - halts and parks.
- [ ] Each entry has a timestamp, a severity and a stable reason code (an enum, not free text).
- [ ] The journal is shown in the Bots screen's Log tab and is filterable (severity, kind, reason code, time).
- [ ] It survives a restart and is exportable as CSV.
- [ ] No secrets and no signed URLs are ever written (a signature, an API key, a webhook URL); entries are sanitised at the port, not at the call sites.
- [ ] It is the source the [`EPIC-035K`](EPIC-035K_alerts_reach_a_user_who_is_away.md) alerts quote: an alert carries the journal entry's reason code and text, never a second wording.
- [ ] Built behind a port, so the storage (JSON lines versus SQLite) is an adapter decision, recorded in this task's Design before the adapter is written.

## 3. Design
A journal port in the bots contracts package (`append`, `query` by filter, `export`), a typed entry with a closed reason-code enum, and one adapter. The adapter choice is open and is recorded here when decided: JSON lines (simple, append-only by construction, a `grep`-able file, per-bot rotation to design) versus SQLite (filtering and CSV export are queries, a schema to migrate). Per `CONSTITUTION.md` P5, survey the stores the project already uses (the bot store, the trading store) before inventing one. The Log tab is QtWidgets only per `ui-presentation-rule.md`, with a `preview.py` screenshot.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/contracts/ (the journal port and entry type)` | as the criteria require |
| `src/modules/bots/adapters/ (the journal adapter)` | as the criteria require |
| `src/modules/bots/application/ (the write points)` | as the criteria require |
| `src/modules/bots/ui/bots_screen/ (the Log tab)` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_a_halt_writes_one_entry_with_its_reason_code_and_inputs`
- `test_the_journal_survives_a_restart`
- `test_the_journal_is_append_only` (no update or delete on the port)
- `test_no_secret_or_signed_url_is_ever_written` (red-flag test: feeds a signed URL and a key through every write point and scans the stored bytes)
- `test_the_csv_export_round_trips`
- `test_the_log_tab_filters_by_severity_and_reason`
- `test_a_second_adapter_needs_no_application_change`

Not run yet.

## Resume
Not started. The owner asked on 2026-10-08 that this task not be started yet.
