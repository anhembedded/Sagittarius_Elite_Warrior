# BOT-211 — A running position bot's current liquidation-risk level is readable, and the Plan dock shows it

**Status:** 🔵 Backlog
**Priority:** P2
**Board:** The risk watch's SAFE / WARN / CRITICAL reaches no screen: it is published once per change (`BotRiskChangedEvent`) and kept nowhere, so a UI cannot say the current level when it opens, and a bot that stays SAFE never announces it. Make the current level readable, then show it in the Plan dock as a word, an icon and a tone (`PRO-009` B5, left out of `EPIC-043E` for this reason).
**Source:** `EPIC-043E`, 2026-10-21. `PRO-009` §2 B5 says the risk watch's levels "already have a word beside them"; they have none on any screen. The delivery coordinator was told the default (not building the row in 043E) on 2026-10-21.
**Risk:** 🟡 — reads the running bot's watch, a real-money path; the read must never change what the watch does
**Complexity:** M — a read model in the running-bot domain, a query, and one Plan dock row
**Epic (optional):** [EPIC-043](../epics/EPIC-043_financial_visual_language/README.md)
**Depends on:** None (`EPIC-043D` merged).

---

## 1. Context and problem
`GridRiskWatch._announce` (`src/modules/bots/application/kinds/grid/watch/grid_risk_watch.py`, at `137fe0a6`) publishes `BotRiskChangedEvent` once per level change, and `RiskLevel` (`bots/contracts/risk_state.py`) has four members: `SAFE`, `WARN`, `CRITICAL`, `UNKNOWN`. The only consumer is the alert source (`alerting/application/sources/liquidation_alert_source.py`). Neither `BotProgress`, the runtime record nor any query carries the latest level. A screen that listens to the event would show nothing until the first change, and would show nothing for a bot that never leaves `SAFE`; showing "SAFE" there would be a claim the application cannot back, and an absent row is ambiguous (`domain-truth-rule.md`).

## 2. Acceptance criteria
- [ ] The running bot's latest `RiskState` (level, reason, distance, when it was read) is readable by a query, not by listening, for a bot on a position venue; a bot with no reading yet says `UNKNOWN`, never `SAFE`.
- [ ] The Plan dock of a running position bot has a "Liquidation risk" row: the level's word (`Safe`, `Warning`, `Critical`, `Unknown`), a `StateLook` icon and the meaning table's tone (`SAFE` plain, `WARN` caution, `CRITICAL` loss), and the distance in the existing formatter.
- [ ] The read does not touch the watch's decisions: no new lock, no new thread, a test that the watch's events are unchanged.
- [ ] A Spot bot or a stopped bot has no row.

## 3. Design (the choice and its options)
1. **Latest `RiskState` in the bot's runtime record** (the watch writes it on each reading, the existing snapshot reads it): one source, survives a restart's first read, adds a field to a stored record (a migration, a default).
2. **A query that asks the running watch** (`IRiskGuard`-side, in memory): no stored field; empty after a restart until the first reading, which is `UNKNOWN`, honestly.
3. **The UI keeps the last event and reads the watch once on selection**: two sources, the second racing the first.
Recommendation: option 2 with a `UNKNOWN` default, and the Plan dock row reading it on selection and on `BotRiskChangedEvent` (the event as a trigger, the query as the truth). It adds no stored field.

## 3a. Reuse
`StateBadge`/`StateLook`/`tone_icon` (the existing `triangle-alert`, `shield`, `circle-check-big` icons), `meaning_colours`, `verdict_tone`'s pattern, `BotChangesFeed` for marshalling a worker-thread event, the Plan dock's property grid (`PlanPropertyGrid`, `set_values(values, tones)`).

## 4. Changes, per file
To be filled when the task starts.

## 5. Testing
To be filled when the task starts: the query against the real watch with a fake exchange, the row's words, icon and tone per level, and a wiring test that the Plan dock refreshes on the event.

## 6. Docs touched
`Docs/MODULES/bots/` (the file that draws the risk watch and its read), `.claude/rules/ui-presentation-rule.md` if the Plan dock's clause changes.
