# BOT-197 — A manual order or a strategy arm that opens a closed order session still puts the venue's RECOVERING bots back to work

**Status:** 🔵 Backlog
**Priority:** P2
**Board:** `BOT-183` made a bot's Resume, `--resume-halted` and the operator's `bot stop` wake only their own bot; a manual order on the desk or a strategy arm that opens a closed session names no bot and still reconciles every `RECOVERING` bot of the venue, which the owner did not resume.
**Source:** the review of #583 (BOT-183), 2026-10-19, ADR open question O1: "A manual order or a strategy arm that opens a closed session still wakes every RECOVERING bot."
**Risk:** 🔴 — a real-money bot the owner did not resume starts laying orders because a different, manual action opened the session.
**Complexity:** S — two callers pass an opener; the owner decides the rule first.
**Epic (optional):** [EPIC-029](../epics/EPIC-029_bots_tab_grid_fast_track/README.md)
**Depends on:** `BOT-183` (the `opened_for` field on `TradingSwitchChangedEvent`).

---

## 1. Context and problem
`SessionReadiness.ensure_ready` publishes `TradingSwitchChangedEvent(..., opened_for=...)`. `ExecuteOrderCommandHandler` (a manual order, `ensure_ready(command.venue)`) and the strategy arm (`arm_strategy/handler.py`, `trading_session.ensure_ready()`) pass no bot, so `GridFacts._apply_switch` treats the opening as "for no bot" and reconciles every `RECOVERING` bot of the venue, as before `BOT-183`.

## 2. Acceptance criteria
- [ ] The owner decides, with options: may a manual order or a strategy arm that opens a closed session wake `RECOVERING` bots? Recommended: no, the same rule as `BOT-183` (ADR 038 O2: a host never resumes a bot by itself).
- [ ] If no: the two openers name an opener that is not a bot, and a `RECOVERING` bot acts only on its own opening; a test on the composed app (a manual order opens the session, the `RECOVERING` bot stays `RECOVERING`, then resumes on its own command).

## 3. Design
Not written. Candidate: a named "opened by a person, for no bot" value that `GridFacts._apply_switch` does not treat as a wake, replacing `None` for these two openers (`None` stays "no opener known").

## 3a. Reuse
`TradingSwitchChangedEvent.opened_for`, `order_session_opening`.

## 4. Changes, per file
Written when the task starts.

## 5. Testing
Written when the task starts.

## 6. Docs touched
`Docs/MODULES/bots/06-runtime.md` (the paragraph on who passes `None`), the ADR `DECISION_2026-10-19_a_session_opened_for_one_bot_resumes_no_other.md` (O1).

## Implementation notes (written when done)
