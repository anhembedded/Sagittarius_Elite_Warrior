# BOT-158 — The desks drop the plumbing only the Dev Board read

**Status:** 🔵 Backlog
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
- [ ] No `lastSignalText` and no `accountReconciled` in `src/`, and nothing that only fed them.
- [ ] Signal isolation between the desks is still proved, through what a desk does show (its chart's strategy lines or its armed summary), by a test that goes red when the venues' signals cross.

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
