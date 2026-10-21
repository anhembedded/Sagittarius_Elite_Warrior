# EPIC-044C — Every surface that shows a bot says it is waiting for the range, and the owner is told when it enters

**Status:** ✅ Done (2026-10-21)
**Source:** the owner, 2026-10-21, through the coordinating session (quoted once in the epic README: *"trường hợp giá out range, thì bot vẫn start, nhưng chờ giá vào trong range thì bot mới bắt đầu init lệnh"* — if the price is out of the range the bot still starts but only begins laying orders once the price is inside).
**Risk:** 🟡 — display and alert only; a false label would mislead (`domain-truth-rule.md`).
**Complexity:** M — six surfaces, one alert, frames.
**Epic (optional):** [EPIC-044](../README.md)
**SPEC (optional):** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** [EPIC-044B](EPIC-044B_the_state_and_the_entry.md) (merged, #682); #674 does not touch what this changes (the coordinator allowed the start, 2026-10-21)

---

## 1. Context and problem
ADR D10. Without it the waiting bot would render as an unknown state in the table, the badge and the CLI.

## 2. Acceptance criteria
- [x] A state badge for `AWAITING_RANGE` (`StateBadge`, an icon and the word "Waiting for the range"): `bot_state_looks.py` (clock, neutral; 044B) and the frames below; `test_a_waiting_bot_says_what_it_waits_for.py::test_the_state_line_is_the_state_word_alone`.
- [x] The Plan banner says "Waiting for the price to enter X–Y (last price Z, N s ago); nothing is placed until it does" in `PlanColumn`, as information and not a warning: `waiting_text`, `bot_facts._waiting_note`; `test_a_waiting_bot_says_what_it_waits_for.py` (the sentence, no price yet, not a warning, no other state says it).
- [x] The Bots table shows the state and does not flag the wait as needing attention (`test_the_bots_table_shows_the_state_word_and_does_not_flag_the_wait_for_attention`); `bot list` and `bot show` show the state, the range and the last price (`bot_waiting_reason.py`, `test_a_waiting_bot_is_listed_with_its_range_and_price.py`, JSON `reason` unchanged).
- [x] The heartbeat and the daily summary count waiting bots apart from running ones (`counts_line` groups by state) and the heartbeat line says the range and the price; the `[health]` line and `BotsHealthContributor` gain `awaiting_range` (`test_the_heartbeat_names_a_bot_waiting_for_its_range.py`, `test_host_health_line.py`, `test_bots_health_contributor.py`).
- [x] One alert when the bot enters the range, from one `BotRangeEnteredEvent` the entry path publishes once the ladder is laid (`GridRangeEntry._tell_the_ladder_is_laid`; `test_a_grid_that_enters_its_range_tells_it_once.py` for every direction × side, none for an inside start, a refused plan or a ladder that could not be laid; `test_a_bot_that_enters_its_range_is_told.py`).
- [x] Frames of the Bots screen with a waiting bot, light and dark, in the CI `ui-screenshots` artifact (ids and file names given to the coordinator): `test_a_waiting_bot_is_pictured.py` writes `bots~waiting_spot_waiting[~dark]@WxH.png` and `bots~waiting_futures_short_waiting[~dark]@WxH.png` at 1024x700, 1366x768 and 1920x1080. Evidence: CI run 39584376957, artifact `ui-screenshots` id 12339453377 (12 `bots~waiting_*` pictures; the reviewer opened four).

## 3. Design
ADR D10; `StateBadge`/`StateLook`, `NoticeBar`, `BotRangeEnteredEvent` (the entry crosses two states, so no state-entry rule can carry it; ADR D10), handled by `BotAlertSource.on_range_entered`.

## 3a. Reuse
`StateBadge`, `NoticeBar`, `PlanColumn`, `value_formatter`, `price_text`; a new contract event, `BotRangeEnteredEvent`, because the entry crosses two states (ADR D10).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `bots/application/kinds/grid/watch/grid_price_reaction.py` | a waiting bot keeps the price it hears as its last (`_enter_if_waiting`) |
| `bots/contracts/grid_ladder_texts.py` | `waiting_text`, the one sentence |
| `bots/ui/bots_screen/bot_facts.py` | the note of a waiting bot; its state line is the word alone |
| `bots/cli/bot_waiting_reason.py`, `bot_status_reports.py` | the sentence takes a waiting bot's reason cell in `bot list` and `bot show` |
| `alerting/application/heartbeat_text.py` | the heartbeat line of a waiting bot |
| `bots/application/services/lifecycle/bots_health_contributor.py`, `operations/application/host_health_line.py`, `health_line.py` | `awaiting_range` count, appended |
| `bots/contracts/events/bot_range_entered_event.py`, `grid_range_entry.py` | the event and its single publication |
| `alerting/domain/alert_kind.py`, `alert_catalog.py`, `module.py`, `sources/bot_alert_source.py`, `bot_reason_routes.py` | `BOT_RANGE_ENTERED` (INFO), its handler, the halt conditions the wait ends; `reason_line` moved to keep the source under 400 lines |
| `bots/ui/bots_screen/plan_table_frames.py` | two frames: `spot_waiting`, `futures_short_waiting` |

## 5. Testing
The unit tests named in §2, `tests/integration/presentation/ui/test_a_waiting_bot_is_pictured.py` (12 pictures; not blank, the banner and the state word), the `bot list`/`bot show` tests over the stored-bot world. Mutation-checked: no price saved while waiting, the reason cell not replaced, the publication unguarded by `RUNNING`: each turns a test red. Commit tier PASS; `tests/unit/architecture`, `tests/unit/modules`, the alerting and bots integration folders: 13,715 passed.

## 6. Docs touched
`Docs/MODULES/bots/05-building-blocks.md`, `06-runtime.md`; `Docs/MODULES/alerting/03-context.md`, `05-building-blocks.md`; `Docs/SPEC/SPEC-014_run_a_grid_bot.md`; `Docs/OPERATIONS/LOGGING.md` and `headless_runbook.md` (the `[health]` line). `Docs/HLD/11_desktop_workbench.md`: none, because it names no state and the new look is the existing `StateBadge` pattern.

## Implementation notes (written when done)
- **Decision (owner may veto):** the alert is INFO, so it is delivered and silent by default like a fill; it is the thing the owner asked for, not a warning. Routing it loud is the owner's setting.
- A waiting bot's "last price Z" needed the price recorded while it waits (review round 1: it is written with its age, because a waiting bot has no stale-feed halt and a bare "now" could be hours old); `_exits_watched` is false then, so the save moved into `_enter_if_waiting`.
- The heartbeat already counted bots by state, so waiting bots were apart from running ones without a change; what was added is the range and the price on the bot's line.
- `bot show` already printed the last price and both edges for a Grid (`BOT-193`); with the price recorded they are filled for a waiting bot, and the Reason row carries the sentence.
- Found while here, not changed: the GUI's Resume to Confirm for a flat bot meets a "no proposal" case when the price is outside the range (a flat Resume waits instead of proposing a ladder); and `readiness_assessment._exchange_outcome` still judges the exchange's facts at the raw price. Both are for a follow-up if the owner meets them.
