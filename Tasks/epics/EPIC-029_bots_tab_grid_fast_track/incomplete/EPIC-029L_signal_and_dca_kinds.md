# EPIC-029L — The existing strategies run as signal bots, and DCA runs on the ladder executor

**Status:** 🔵 Backlog — after the fast track; sliced in detail when it starts
**Source:** [`PRO-006`](../../../proposal/PRO-006.md) §4.3 "After the fast track", accepted by the user on 2026-10-03 (*"Oki, duyệt"*).
**Risk:** 🟡 — moves strategy arming behind the bot shell; DCA reuses but extends the ladder.
**Complexity:** L — two new `IBotKind` implementations, migration of saved strategy configs, retirement of desk arming.
**Epic:** [EPIC-029](../README.md)
**Depends on:** `EPIC-029I`, `EPIC-029J`.

---

## 1. Context and problem
The user judged the six strategies low value on 2026-10-03, so they come last. They still deserve the shell: today a strategy's symbol is the chart's (`desk_strategy.py:65`) and it has no lifecycle. DCA (initial order, safety orders, take profit) reuses the ladder executor's level machinery.

## 2. Acceptance criteria
- [ ] A `SignalKind` wraps today's strategy engine behind `IBotKind`; a signal bot has an explicit symbol and the shell's lifecycle.
- [ ] The saved per-venue strategy configs (`trading.<venue>.live_*`) are migrated once into signal bots; the migration is idempotent and logged.
- [ ] A `DcaKind` places an initial order and stepped safety orders and closes at its take profit, on the ladder executor, with its own planner verdicts.
- [ ] Desk arming code paths no longer exist outside the Dev Board.

## 3. Design
Signal kind reaches `strategy` through published ports only (`DECISION_2026-09-17_strategy_ui_contributes_rather_than_being_imported.md`). The full per-file design is written when this task starts, against the tree as it is then.

## 4. Changes, per file
Written when the task starts (the fast track will have changed the files it touches).

## 5. Testing
Written when the task starts; each criterion above maps to a unit or integration test, plus the Testnet tier where an exchange behaviour is involved.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
