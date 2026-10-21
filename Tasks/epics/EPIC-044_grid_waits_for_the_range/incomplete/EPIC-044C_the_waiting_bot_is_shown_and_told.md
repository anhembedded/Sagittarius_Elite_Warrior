# EPIC-044C — Every surface that shows a bot says it is waiting for the range, and the owner is told when it enters

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-21, through the coordinating session (quoted once in the epic README: *"trường hợp giá out range, thì bot vẫn start, nhưng chờ giá vào trong range thì bot mới bắt đầu init lệnh"* — if the price is out of the range the bot still starts but only begins laying orders once the price is inside).
**Risk:** 🟡 — display and alert only; a false label would mislead (`domain-truth-rule.md`).
**Complexity:** M — six surfaces, one alert, frames.
**Epic (optional):** [EPIC-044](../README.md)
**SPEC (optional):** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** [EPIC-044B](EPIC-044B_the_state_and_the_entry.md); the UI and alerting PRs in flight (#677, #678, #674) merged

---

## 1. Context and problem
ADR D10. Without it the waiting bot would render as an unknown state in the table, the badge and the CLI.

## 2. Acceptance criteria
- [ ] A state badge for `AWAITING_RANGE` (`StateBadge`, an icon and the word "Waiting for the range").
- [ ] The Plan banner says "Waiting for the price to enter X–Y (now Z)" in `PlanColumn`.
- [ ] The Bots table shows the state; `bot list` and `bot show` show the state, the range and the last price.
- [ ] The heartbeat and the daily summary count waiting bots apart from running ones.
- [ ] One alert when the bot enters the range: price and number of orders laid.
- [ ] Frames of the Bots screen with a waiting bot, light and dark, in the CI `ui-screenshots` artifact (ids and file names given to the coordinator).

## 3. Design
ADR D10; `StateBadge`/`StateLook`, `NoticeBar`, the existing `BotAlertSource` entry rule extended with the transition `AWAITING_RANGE → RUNNING`.

## 3a. Reuse
`StateBadge`, `NoticeBar`, `PlanColumn`, `value_formatter`, `price_text`; not used: a new bus event.

## 4. Changes, per file
Decided at implementation time against the merged heads of #677, #678, #674.

## 5. Testing
Unit tests per surface (presence, order, the words), the screenshot cases, an alerting test that one alert is raised.

## 6. Docs touched
`Docs/MODULES/bots/05-building-blocks.md`, `Docs/HLD/11_desktop_workbench.md`, `Docs/SPEC/SPEC-014_run_a_grid_bot.md`.
