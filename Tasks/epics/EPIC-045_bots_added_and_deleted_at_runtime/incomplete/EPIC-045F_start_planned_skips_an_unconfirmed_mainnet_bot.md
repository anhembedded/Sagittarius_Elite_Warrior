# EPIC-045F — `run --start-planned` skips a mainnet bot that lacks its confirmation and runs the rest

**Status:** 🟡 In progress (built; pull request open)
**Source:** the owner, 2026-10-21, from the VPS: with `--start-planned` in the unit, an applied plan that wants one mainnet bot running and has no `--confirm-venue` made `run` exit 2 before boot; systemd does not restart it, so every other bot (testnet) was left unattended until the owner intervened. "`--start-planned` gặp bot mainnet chưa xác nhận thì bỏ qua bot đó, cảnh báo, và vẫn chạy các bot còn lại" (when `--start-planned` meets a mainnet bot that is not confirmed, skip that bot, warn, and still run the remaining bots).
**Risk:** 🟡 — it changes what a host does at boot when a plan wants a mainnet bot; it must start no mainnet bot unconfirmed.
**Complexity:** M
**Epic:** [EPIC-045](../README.md)
**Depends on:** [EPIC-045A](EPIC-045A_bot_add_on_the_running_host.md) and [EPIC-045B](EPIC-045B_bot_delete_on_the_running_host.md) merged (delivery order only)

---

## 1. Context and problem
`run --start-planned` refuses before boot when the applied plan wants a mainnet bot running and the unit carries no `--confirm-venue` (runbook §8: "exit 2 before anything boots"). The exit is not restarted by systemd, so the other bots are left unattended.

## 2. Acceptance criteria
- [ ] A planned bot that needs a confirmation it was not given is skipped with a WARNING log and an alert naming `bot start <id> --confirm-venue <venue>`; the host boots and starts the rest of the plan.
- [ ] No mainnet bot starts without its confirmation; nothing else about the real-money guard changes.
- [ ] The case where no bot at all could start is decided and recorded (D7 recommends: not fatal for this reason); an unreadable applied plan still exits 5.
- [ ] Runbook §8's "exit 2 before anything boots" is rewritten to match.

## 3. Design
See [the decision record](../DECISION_2026-10-21_add_and_delete_on_the_running_host.md) D7. Reads `run --start-planned`'s start path first; reuses the host's existing alert channel.

## 3a. Reuse
Used `StartPlannedBots` (the step stays; only its refusal changes), `IEventPublisher` and the alerting module's bot-event source (`BotAlertSource`) for the alert, `TradingVenue.is_mainnet` for the question O8 already asks. Not used: a new alert channel.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `modules/operations/application/host_steps.py` | `StartPlannedBots` skips an unconfirmed mainnet bot (WARNING + event); `mainnet_start_refusal` is gone |
| `modules/operations/cli/run_command.py` | no pre-boot refusal for `--start-planned`; the step gets the event publisher |
| `modules/bots/contracts/events/planned_bot_not_started_event.py` | the typed fact |
| `modules/alerting/**` | `PLANNED_BOT_NOT_STARTED` kind (WARNING, bot events), `on_planned_bot_not_started`, bus wiring |

## 5. Testing
A unit test of the plan-start path with one unconfirmed mainnet bot and one testnet bot; an integration journey on the fake exchange.

## 6. Docs touched
`Docs/OPERATIONS/headless_runbook.md` §8; the headless host's module doc.

## Implementation notes (written when done)
The refusal was a decision of its own (O8 + "a half-started plan is the worse surprise", in the old docstring of `mainnet_start_refusal`); the owner reversed it for `--start-planned` on 2026-10-21 because systemd does not restart exit 2. `--resume-recovering` keeps its pre-boot exit 2 (not asked). The skip is judged inside the step, after boot, with the bot's own venue against the typed one; no start is dispatched for a skipped bot, so no order session is opened for it. The unconfirmed bot stays at rest and is reported by one WARNING and one alert per run. The `-Full` result on the pull request head is Not yet read.

## Resume
Built and under review; flip to Done and move to `completed/` once merged.
