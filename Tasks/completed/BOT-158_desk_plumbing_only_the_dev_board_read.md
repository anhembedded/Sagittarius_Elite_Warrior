# BOT-158 — The desks drop the plumbing only the Dev Board read

**Status:** ✅ Done (2026-10-06)
**Source:** the EPIC-033P stage 3 hand-back and the independent review of PR #372: "The Last signal pipe on the desks has no backlog task."
**Risk:** 🟡 — `test_two_desks_stay_apart.py` proves signal isolation through the pipe being removed, so that proof must move first
**Complexity:** S — two signals and their wiring, plus one test re-homed
**Epic (optional):** [EPIC-033](../epics/EPIC-033_windows_workbench/README.md)
**Depends on:** None

---

## 1. Context and problem
- **Last signal.** The user decided on 2026-10-05 that the armed strategy's last signal is shown nowhere (`EPIC-033P` Decisions). The chain `StrategyArmingCoordinator.on_signal_generated` → `StrategyCardViewModel.lastSignalText` still runs on both desks, and no widget reads it.
- **`DeskSessionControls.accountReconciled`.** It handed the session's confirmed positions and orders to a host that keeps its tables from events alone. That host was the Dev Board; no production code connects to it now.
- **Why it matters:** code nobody reads still has to be maintained, and it suggests a feature the app no longer has (`code/quality.md`).

## 2. Acceptance criteria
- [x] No `lastSignalText` and no `accountReconciled` in `src/`, and nothing that only fed them.
- [x] Signal isolation between the desks is still proved, through what a desk does show (its chart's strategy lines or its armed summary), by a test that goes red when the venues' signals cross.

## 3. Design
- Move the isolation proof of `test_two_desks_stay_apart.py` to an observable the desk keeps, then delete the two pipes and their tests.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/desk/strategy_card/` | drop `lastSignalText` and its feed |
| `src/modules/trading/ui/desk/desk_screen/desk_session_controls.py` | drop `accountReconciled` |
| `tests/integration/…/test_two_desks_stay_apart.py` | prove isolation on a kept observable |

## 5. Testing
- **Integration:** the re-homed isolation test, mutation-checked by crossing the venues.

## Implementation notes (written when done)
- **Re-homed first.** `test_two_desks_stay_apart.py::test_a_strategy_armed_on_one_venue_shows_on_that_desk_only` replaces the signal test: arming on the Spot desk reaches Spot's arming and Spot's armed summary; the Futures desk, read again, says nothing is armed. `DeskPresenter` now refuses another venue's strategy controls as it already refused another venue's ports (`test_desk_screen.py::test_a_desk_refuses_another_venues_strategy`).
- **Mutation checks.** Both desks given one arming and one armed reader (the venues crossed in `desk_screen_fixtures.py`): the isolation test fails on `futures.arming.armed_with`. The new guard removed: its test fails with "DID NOT RAISE".
- **Deleted.** `StrategyCardViewModel.lastSignalText`, `lastSignalChanged` and `set_last_signal_text`; `StrategyArmingCoordinator.on_signal_generated` and its protocol member; `DeskStrategy.listen`; `SignalFeed` (`ui/signal_feed.py`) and its place in `ScreenVenueFeeds`, since the card was its only reader; `DeskSessionControls.accountReconciled` and `ReconciledAccount`. With them went the three coordinator signal tests, the feeds' signal test and the five `accountReconciled` tests; the refused-before-reading case keeps its status-line assertion.
- **Kept.** `SignalGeneratedEvent.venue` and the engine's tests that stamp it: the strategy module still publishes the venue, and a reader may tell venues apart by it.
