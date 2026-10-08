# EPIC-035W — The bot's health is visible on screen

**Status:** 🔵 Planned — requested by the owner on 2026-10-08, who asked that it **not be started yet**
**Source:** the owner's request of 2026-10-08, relayed by the coordinator session; extends the Spot Grid audit (https://claude.ai/artifact/QaMbN6KkH47h4eTrUpNGDz). Phase 3 of [EPIC-035](../README.md).
**Risk:** 🟡 — a new read model over several event sources and a status-bar change in the shell
**Complexity:** L
**Epic:** [EPIC-035](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), updated by this task if a journey changes
**Depends on:** EPIC-035A (the bot's price feed and its age), EPIC-035B (the user-data stream health and the reconcile after a gap)

---

## 1. Context and problem
The bot checks itself internally, but the owner cannot see on screen whether a running bot is alive:
- `UserStreamHealthEvent` (`src/modules/trading/contracts/events/user_stream_health_event.py`) is consumed by `UserStreamWatch` (`src/modules/bots/application/services/user_stream_watch.py`) and has no UI consumer.
- The age of the 035A price feed is not shown anywhere.
- The status bar reads "Exchange: not checked · Market data: not live" even while a bot is running and connected (`src/modules/trading/ui/market/connection_words.py:17`, `src/modules/trading/ui/market/market_presenter.py:89`; the same symptom as the status-bar line of [`EPIC-035N`](EPIC-035N_invalid_parameters_are_explained_where_they_are.md), which this task supersedes for the status bar).

Cited lines are from the request and a `grep` on 2026-10-08; verify each on the running app before coding. This task is specified briefly: it is Phase 3 — Alerting and transparency. The full acceptance criteria are re-confirmed against the code when the task is started (`execute-task`). A claim that does not hold is said so here and reported.

## 2. Acceptance criteria
- [ ] Each running bot shows a health strip with:
  - the age of its last price tick, classed ok, warn above 20 s and bad above 60 s;
  - the user-data stream state and how long it has been down;
  - the time and result of the last reconcile;
  - open tagged orders known to the bot versus on the exchange;
  - a read-only "Check now" button that runs a reconcile and places nothing.
- [ ] The status bar reflects the selected bot's venue and streams truthfully (`domain-truth-rule.md`, Truthful UI): no "not checked" or "not live" while that bot is running and connected, and no "live" while its feed is stale.
- [ ] The data source is the existing events and ports (`UserStreamHealthEvent`, the 035A tick age, the reconcile result); no new polling loop.
- [ ] [`EPIC-035K`](EPIC-035K_alerts_reach_a_user_who_is_away.md)'s Discord heartbeat reuses the same health snapshot, so the screen and the heartbeat cannot disagree.
- [ ] The thresholds (20 s, 60 s) are named constants in one place, not literals in a widget.

## 3. Design
One immutable health snapshot per bot, built in the application layer from the events and ports above and read by both the strip's presenter and the 035K heartbeat. QtWidgets only, OS theme, per `ui-presentation-rule.md`; a preview in `preview.py`. "Check now" goes through the async-UI action coordinator (`async-ui-action-rule.md`) and calls the existing reconciler in a read-only mode.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/ (the health snapshot)` | as the criteria require |
| `src/modules/bots/ui/bots_screen/ (the strip and its presenter)` | as the criteria require |
| `src/shell/ (the status bar)` | as the criteria require |

## 5. Testing
Tier per `ci-rule.md` §2; every regression test is shown red before the change. Planned tests:
- `test_the_strip_shows_the_age_of_the_last_tick_with_its_class`
- `test_a_down_user_stream_shows_how_long_it_has_been_down`
- `test_check_now_reconciles_and_places_nothing` (the fake exchange records zero placements)
- `test_the_status_bar_follows_the_selected_bots_streams`
- `test_the_heartbeat_and_the_strip_read_one_snapshot`
- a `preview.py` screenshot of ok, warn and bad

Not run yet.

## Resume
Not started. The owner asked on 2026-10-08 that this task not be started yet.
