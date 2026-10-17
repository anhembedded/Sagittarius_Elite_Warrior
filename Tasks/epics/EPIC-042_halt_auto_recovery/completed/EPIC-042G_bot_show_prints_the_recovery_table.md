# EPIC-042G — `bot show` prints the bot's effective recovery table

**Status:** ✅ Done (2026-10-17; pull request open)
**Source:** the owner, 2026-10-17, relayed by the coordinating session: the effective table "can be printed (for example in `bot show`)" ([decision D15](../DECISION_2026-10-17_halt_auto_recovery.md))
**Risk:** 🟢 — a read-only report line set
**Complexity:** S — one field on the status report, one renderer arm
**Epic (optional):** [EPIC-042](../README.md)
**Depends on:** [EPIC-042B](../completed/EPIC-042B_awaiting_recovery_state_and_ledger.md)

---

## 1. Context and problem
Which halts a bot will recover from, with what dwell and budget, is merged from three layers; an operator cannot read that from three files. `bot show` is the headless host's read of one bot.

## 2. Acceptance criteria
- [x] `bot show <bot>` prints the bot's effective recovery table: code, dwell, attempts per window, stalled-wait threshold, and the layer that decided it; and the attempts used inside the window, from the bot record.
- [x] A Futures bot prints "no automatic recovery" with the layer that says so.
- [x] The text and JSON formats carry the same rows (`emit_report`). No CSV report format is registered in this build (`ReportFormats.default()` has text and JSON), so none was tested; a format registered later gets the rows from the same `Report`.
- [x] The rows come from `effective_policy`, the function the director uses; a test fails if the report builds its own merge.

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

## Implementation notes (written when done)
- **Where the rows come from.** `GetBotStatusReportQueryHandler` resolves the bot's kind in `IBotKindCatalog` and calls `recovery_policy_of(kind.recovery_layer(), venue)`, the function the executor factory builds the director's policy with (`recovery_table.py` -> `recovery_table_of`). Nothing in the report merges layers. `test_the_kinds_own_layer_reaches_the_report` fails if it did: a kind whose layer retunes the dwell must show that dwell and name that layer.
- **Data, then text.** `BotStatusEntry.recovery` is a `BotRecoveryTable` of `RecoveryRuleLine`s (code, dwell, attempts per window, stalled-after, deciding layer, attempts used inside that rule's window). It is filled for the one-bot read only; a listing carries `null`, so `bot list` stays small. `bot show` prints one `Recovery` row per reason; text, JSON and CSV come from the same `Report`.
- **Futures.** `EffectivePolicy.emptied_by` names the layer that cleared the lower ones, so the row reads `no automatic recovery (futures layer)` and `none_decided_by` is `futures`.
- **Attempts.** `BotSnapshot.recovery_attempts` carries the bot's ledger; the handler counts it against each rule's window with `attempts_within` at `IBotClock.now()`.
- **Contract with scripts.** The `bot` payload gained `reason_detail` and `recovery` (a field added within the version, `bot_status_reports.py`).
