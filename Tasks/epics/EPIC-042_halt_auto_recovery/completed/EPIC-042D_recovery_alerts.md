# EPIC-042D — The owner is told of each automatic recovery, of the exhaustion and of a wait that has stalled

**Status:** ✅ Done (2026-10-17; pull request open)
**Source:** the owner, 2026-10-17, through the coordinating session (decision record [D1 (alerts)](../DECISION_2026-10-17_halt_auto_recovery.md))
**Risk:** 🟢 — two new alert kinds and two source arms; no bot behaviour
**Complexity:** S — one event, one kind, one handler, one reason text
**Epic (optional):** [EPIC-042](../README.md)
**Depends on:** [EPIC-042B](../completed/EPIC-042B_awaiting_recovery_state_and_ledger.md)

---

## 1. Context and problem
A recovery is not a state entry, so `BotAlertSource.ALERT_ON_ENTRY` cannot carry it; the exhaustion enters `HALTED`, which already alerts, but the text must say the three recoveries are used up.

## 2. Acceptance criteria
- [x] `BotAutoRecoveredEvent(bot_id, reason, attempt, max_attempts)` exists and is published by the recovery run (done in `042C`); `AlertKind.BOT_AUTO_RECOVERED` (WARNING, group bot events) and its catalog row; the completeness test passes.
- [x] The source turns the event into one alert naming the bot, the reason, the attempt and the budget left.
- [x] The `BOT_HALTED` alert for a bot whose recoveries are used up carries that sentence in its `Reason:` line, from the reason detail the director wrote.
- [x] `BotRecoveryStalledEvent(bot_id, reason, waited_s)` is published once per wait and `AlertKind.BOT_RECOVERY_STALLED` (WARNING, bot events) is its alert, one when a bot has waited `stalled_after`, ended when the bot leaves the state - **done in `042C`** (review of PR #552: without it a feed that never returns leaves a real-money bot silent). Left here: only the criterion's tests, if any are missing, and the docs.
- [x] An alert-kind default for a headless owner is on (the hub's default channels), as the other bot kinds are.

## 3. Design
Applies `BotStopGaveUpEvent` and its handler; the source reads `bots/contracts` only (`EPIC-036G`).

## 3a. Reuse
Used `BotAlertSource`, `AlertKind`/`KIND_PROFILES`, `IAlertPublisher`.

## 4. Changes, per file
`bots/contracts/events/bot_auto_recovered_event.py` (new), `bots/contracts/events/bot_recovery_stalled_event.py` (new), `alerting/domain/alert_kind.py`, `alert_catalog.py`, `alerting/application/sources/bot_alert_source.py`, `bots/module.py` or its composition (publish), `Docs/MODULES/alerting/`, `Docs/MODULES/bots/03-context.md`.

## 5. Testing
Unit: the source with a fake publisher; catalog completeness. Integration: the recovery on the fake exchange publishes the event once.

## 6. Docs touched
`Docs/MODULES/alerting/` (the kind), `Docs/MODULES/bots/03-context.md` (the event).

## Implementation notes (written when done)
- **Recovered alert.** `AlertKind.BOT_AUTO_RECOVERED` (WARNING, bot events, so a headless owner gets it with the other bot kinds) and `BotAlertSource.on_auto_recovered`, subscribed in `AlertingModule.boot`. Its dedup key carries `attempt-N`: the hub's window for a WARNING is 15 minutes and two recoveries can fall inside it, which would otherwise have been counted on the first alert.
- **Exhaustion text.** The `Reason:` line of a `BOT_HALTED` alert read `BotStatusEntry.reason`, the code only; the sentence "the N automatic recoveries allowed in 24 h are used up; resume by hand" lives in `reason_detail`. `BotStatusEntry` gained `reason_detail` (also in the `--json` payload, key pinned in `test_the_bot_report_payload_keys_are_pinned`), and the line is now `Reason: <code> (<detail>)`. This adds the bot's detail to every `BOT_HALTED`/`BOT_ERROR` alert, not only the exhausted one.
- **Evidence.** Unit: `test_bot_alert_source.py` (two recoveries are two alerts; the exhausted halt names it). Integration: `test_a_halted_bot_reaches_discord.py` (a published event reaches the fake webhook through the real module wiring). The event's own publication is `test_grid_halt_recovery.py` (042C).
