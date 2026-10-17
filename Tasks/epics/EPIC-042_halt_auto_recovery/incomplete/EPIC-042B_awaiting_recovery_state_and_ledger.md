# EPIC-042B — The lifecycle table has a state for a halt that waits, and the bot record keeps the attempts

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-17, through the coordinating session (decision record [D3, D7, D8, D9](../DECISION_2026-10-17_halt_auto_recovery.md))
**Risk:** 🟡 — a new state in the store's enum; every exhaustive use of the state must answer for it
**Complexity:** M — one table, one aggregate field, one codec key, the generated tables, every place that lists the states
**Epic (optional):** [EPIC-042](../README.md)
**Depends on:** [EPIC-042A](../completed/EPIC-042A_design_and_decision.md)

---

## 1. Context and problem
`bot_lifecycle_fsm_matrix.py` has nine states; the transient-halt wait has none. The attempt history must live in the bot record so a restart keeps the 24 h budget ([D4](../DECISION_2026-10-17_halt_auto_recovery.md)).

## 2. Acceptance criteria
- [ ] `AWAITING_RECOVERY` and the events `halt_transient`, `condition_cleared`, `budget_exhausted`, `wait_expired` are declared with exactly the eleven rows of the decision's §2.1, and no `PAUSED` or `RECOVERING` + `halt_transient` cell.
- [ ] `PRICE_STREAM_STATES` includes the state (by its definition) and `PRICE_STALENESS_HALTS` does not; the module docstring states why.
- [ ] `BotLifecycle.recovery_attempts` (default empty) round-trips through `bot_record_codec.py`; a file with no key loads as empty; the list is pruned to the longest window and capped.
- [ ] `HaltRecoveryRule`, `RuleChange`, `RecoveryLayer`, `COMMON_LAYER` (price_feed_stale, user_stream_down; 120 s, 3, 24 h, 15 min), `effective_policy` and `EffectivePolicy` rows (code, rule, `decided_by`) are domain types with tests per layer and for the merge: clears-lower, withdrawn, partial override of one field, a new code taking the default rule, precedence venue over kind over common, and a layer that builds an invalid rule failing at build.
- [ ] `RecoveryAttempt` and the ledger arithmetic (`used_within(window, now)`, all codes counted) are domain types with tests, including the boundary at exactly the window.
- [ ] `IBotKind.recovery_layer()` is a concrete method returning an empty layer and `VenueProfile.recovery_layer` a field with a default, so no implementer or construction site changes; the Futures profile sets `clears_lower_layers`; Spot's is empty.
- [ ] Every hand-written state set in the decision's §2.4 answers for the new state (`landing_level` WARNING, `bots_health_contributor` counts, `_ATTENTION_STATES`, `_RUNNING_CLOCK`, `bot_action_rules`, `queued_action_words`, `bot_detail`), and a guard fails when a set in `bots/` classifies fewer than every `BotLifecycleState`.
- [ ] The rollback of the unknown state value is recorded (a refused file, reported, pre-flight fails) in `07-deployment.md`, with the rule that a downgrade first resumes or stops the waiting bots.
- [ ] `scripts/render_bots_design_tables.py --write` regenerates `state-machines.md` and a new `halt-recovery` table (the effective policy of every kind × market) in `10-quality.md`; the Planned blocks move into the generated tables.
- [ ] How an older build reads the new key is recorded before it ships (rollback).

## 3. Design
Decision §2.1 and §2.2. Persistence: additive key, `schema_version` stays 1.

## 3a. Reuse
Used `BotLifecycleState`/`BOT_LIFECYCLE_TRANSITIONS` (the one table), `next_target`/`is_declared`, `render_bots_design_tables.py`. No capability-catalog row fits (domain types).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/bot_lifecycle_fsm_matrix.py` | state, events, rows, docstring |
| `src/modules/bots/domain/halt_recovery.py` (new) | rule, policy, attempt, ledger |
| `src/modules/bots/domain/bot.py` | `BotLifecycle.recovery_attempts`, `Bot.with_recovery_attempt` |
| `src/modules/bots/adapters/persistence/bot_record_codec.py` | the key |
| `src/modules/bots/contracts/i_bot_kind.py`, `venue_profile.py` | `recovery_layer`; the venue field and Futures' `clears_lower_layers` |
| `Docs/MODULES/bots/state-machines.md` and the other module docs | Planned → Built for this part |

## 5. Testing
Unit: the table rows (a table-driven test over the eleven), the ledger arithmetic, the codec round trip and the old-file load. Architecture: `tests/unit/architecture`. Fast tier of `ci-rule.md` §1.

## 6. Docs touched
`Docs/MODULES/bots/state-machines.md`, `08-concepts.md`, `05-building-blocks.md` (Planned → Built).
