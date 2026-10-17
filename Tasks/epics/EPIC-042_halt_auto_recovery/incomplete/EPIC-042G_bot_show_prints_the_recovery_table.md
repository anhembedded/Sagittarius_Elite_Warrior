# EPIC-042G — `bot show` prints the bot's effective recovery table

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-17, relayed by the coordinating session: the effective table "can be printed (for example in `bot show`)" ([decision D15](../DECISION_2026-10-17_halt_auto_recovery.md))
**Risk:** 🟢 — a read-only report line set
**Complexity:** S — one field on the status report, one renderer arm
**Epic (optional):** [EPIC-042](../README.md)
**Depends on:** [EPIC-042B](EPIC-042B_awaiting_recovery_state_and_ledger.md)

---

## 1. Context and problem
Which halts a bot will recover from, with what dwell and budget, is merged from three layers; an operator cannot read that from three files. `bot show` is the headless host's read of one bot.

## 2. Acceptance criteria
- [ ] `bot show <bot>` prints the bot's effective recovery table: code, dwell, attempts per window, stalled-wait threshold, and the layer that decided it; and the attempts used inside the window, from the bot record.
- [ ] A Futures bot prints "no automatic recovery" with the layer that says so.
- [ ] The text, JSON and CSV formats carry the same rows (`emit_report`).
- [ ] The rows come from `effective_policy`, the function the director uses; a test fails if the report builds its own merge.

## 3. Design
`GetBotStatusReportQuery` gains the rows as data in `BotStatusEntry`; the CLI renders them.

## 3a. Reuse
Used `emit_report`, `BotStatusReport`, `effective_policy`.

## 4. Changes, per file
`bots/contracts/bot_status_report.py`, `bots/application/queries/get_bot_status_report/`, `bots/cli/` (the `show` renderer), `Docs/OPERATIONS/`.

## 5. Testing
Unit: the report for a Spot Grid, a Futures Grid and a bot with attempts used. Integration: `bot show` on the fake host.

## 6. Docs touched
`Docs/OPERATIONS/`, `Docs/MODULES/bots/03-context.md`.
