# EPIC-042D — The owner is told of each automatic recovery, of the exhaustion and of a wait that has stalled

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-17, through the coordinating session (decision record [D1 (alerts)](../DECISION_2026-10-17_halt_auto_recovery.md))
**Risk:** 🟢 — two new alert kinds and two source arms; no bot behaviour
**Complexity:** S — one event, one kind, one handler, one reason text
**Epic (optional):** [EPIC-042](../README.md)
**Depends on:** [EPIC-042B](EPIC-042B_awaiting_recovery_state_and_ledger.md)

---

## 1. Context and problem
A recovery is not a state entry, so `BotAlertSource.ALERT_ON_ENTRY` cannot carry it; the exhaustion enters `HALTED`, which already alerts, but the text must say the three recoveries are used up.

## 2. Acceptance criteria
- [ ] `BotAutoRecoveredEvent(bot_id, code, attempt, budget, window)` in `bots/contracts/events/`, published by the recovery run after `confirm`; `AlertKind.BOT_AUTO_RECOVERED` (WARNING, group bot events) and its catalog row; the completeness test passes.
- [ ] The source turns the event into one alert naming the bot, the reason, the attempt and the budget left.
- [ ] The `BOT_HALTED` alert for a bot whose recoveries are used up carries that sentence in its `Reason:` line, from the reason detail the director wrote.
- [ ] `BotRecoveryStalledEvent(bot_id, code, waited)` and `AlertKind.BOT_RECOVERY_STALLED` (WARNING, bot events): one alert when a bot has waited `stalled_after`, none again for the same wait; ended (condition cleared) when the bot leaves the state.
- [ ] An alert-kind default for a headless owner is on (the hub's default channels), as the other bot kinds are.

## 3. Design
Applies `BotStopGaveUpEvent` and its handler; the source reads `bots/contracts` only (`EPIC-036G`).

## 3a. Reuse
Used `BotAlertSource`, `AlertKind`/`KIND_PROFILES`, `IAlertPublisher`.

## 4. Changes, per file
`bots/contracts/events/bot_auto_recovered_event.py` (new), `alerting/domain/alert_kind.py`, `alert_catalog.py`, `alerting/application/sources/bot_alert_source.py`, `bots/module.py` or its composition (publish), `Docs/MODULES/alerting/`, `Docs/MODULES/bots/03-context.md`.

## 5. Testing
Unit: the source with a fake publisher; catalog completeness. Integration: the recovery on the fake exchange publishes the event once.

## 6. Docs touched
`Docs/MODULES/alerting/` (the kind), `Docs/MODULES/bots/03-context.md` (the event).
