# EPIC-042A — The design of automatic halt recovery: the state, its events, the seam and the persistence are decided and drawn

**Status:** ✅ Done (2026-10-17; pull request open)
**Source:** the owner, 2026-10-17, through the coordinating session: *"Propose the state, for example AWAITING_RECOVERY (name it per Docs/VOCABULARY), with explicit events and transitions"* and *"File a task first … First PR: the design."* (translated from the brief: a decision record with the state, events and transition table, and updates to `Docs/MODULES/bots/`).
**Risk:** 🟢 — documentation only; no code, no behaviour.
**Complexity:** S — one decision record, one diagram, edits to six existing documents.
**Epic (optional):** [EPIC-042](../README.md)
**Depends on:** None

---

## 1. Context and problem
A Spot Grid halted by a feed gap stays `HALTED` after the feed returns, and the headless host cannot resume it ([decision §1](../DECISION_2026-10-17_halt_auto_recovery.md)). The owner decided the behaviour; the state machine, the seam and the persistence had to be proposed before code, because a lifecycle state is the most expensive thing to rename once the store has written it.

## 2. Acceptance criteria
- [x] The decision record states the new state, the events and every transition row, and shows them as a diagram.
- [x] The seam is named with its extension cases and the test that locks it.
- [x] The rate-limit auto-resume's migration is answered and recorded as a follow-up.
- [x] `Docs/MODULES/bots/` marks each new part **Planned** with its task: the state machine, the building blocks, the runtime sequence, the stored field, the constants.
- [x] The vocabulary defines the new terms and separates the state from *Recovering bot*.
- [x] Document guards and the reference check are green.

## 3. Design
See the decision record. Applied pattern (P5): the Grid's own propose-and-confirm resume, `BotStopGaveUpEvent` for a bot fact that is not a state, `IBotKind.supported_profiles` for a per-market declaration, the lifecycle table as the one place a state is declared (`code/quality.md` §3).

## 3a. Reuse
`None: no UI or application need` — documentation only. The code tasks list their reuse (`GridResumeSequence`, `IBotRetryScheduler` is *not* used: the beat already runs, `order_session_refusal_words`, `BotStopGaveUpEvent`'s path).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `Tasks/epics/EPIC-042_halt_auto_recovery/` | The epic, the decision record, this task and the six planned ones |
| `Tasks/epics/README.md` | The epic's row |
| `Docs/MODULES/bots/state-machines.md` | Planned: the state, events and rows (hand-written, not between the generated markers) |
| `Docs/MODULES/bots/05-building-blocks.md` | Planned: the director, the policy, the probe, the ledger |
| `Docs/MODULES/bots/06-runtime.md`, `diagrams/06-halt-recovery.puml` | Planned: the sequence |
| `Docs/MODULES/bots/08-concepts.md`, `10-quality.md`, `09-decisions.md`, `README.md` | Planned: the stored field, the constants, the index row, the at-a-glance row |
| `Docs/VOCABULARY/README.md` | Three terms |

## 5. Testing
Documentation-only: `python3 scripts/check_skill_prompt_references.py` and the document guards (`tests/unit/architecture/test_module_docs_cite_code_by_symbol.py`, the task-board and epic-README guards, `test_render_bots_design_tables.py`). Run results are in the pull request.

## 6. Docs touched
The files in §4.

## Implementation notes (written when done)
- The names in the planned sections are plain code identifiers, not `path.py → symbol` citations, because none of the planned symbols exists yet; `EPIC-042B`–`E` turn each into a citation in the commit that creates it (`commit-rule.md` §1, "Design in step").
- Two choices the owner may veto are stated as such in the record: D9 (restart) and D11 (wait limit).
