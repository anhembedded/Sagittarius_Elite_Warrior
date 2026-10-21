# BOT-223 — Restart journeys run with the order session closed, so the opening's refusals are met

**Status:** 🔵 Backlog
**Priority:** P2
**Board:** The composed-app test worlds seed the order session open, so a journey skips every refusal the opening can give; `BUG-250` lived behind it until the owner's VPS met it.
**Source:** `BUG-250`'s fix PR (#680) and its review (check A6): the blind spot was named for the coordinator, who asked for it to be filed on 2026-10-21 ("file your open items (1) and (2) as backlog entries").
**Risk:** 🟡 — tests only, but a sweep can turn existing journeys red where they relied on the seeded session.
**Complexity:** M — about thirty journeys use the seeded default; most need no change, the restart ones do.
**Depends on:** None.

---

## 1. Context and problem
`booted_futures_bots` (`tests/integration/modules/bots/futures_bots_world.py`) and `booted_two_venues` (`two_venues_bots_world.py`) call `session_state.enable(...)` by default (`open_session`, `open_sessions`), and `booted` for Spot does the same. A restart journey then emits the switch event over an open session and never meets `SessionReadiness`'s refusals (a position, a closed connection). `test_a_restart_in_the_middle_of_the_ladder_recovers_its_orders_and_its_position` passed for months while a Futures bot left by a host stop could not be resumed (`BUG-250`). `BUG-250`'s journey passes `open_sessions=False`, which closes it for Resume and Stop only; a HALTED Futures bot holding a position after a restart (its Resume opens the same session) has no journey, and neither has an Emergency-Stop-then-resume over a position.

## 2. Acceptance criteria
- [ ] A guard or a world default makes a journey that boots the app a second time (a restart) on a position venue name its session choice: closed unless it says why it seeds it open.
- [ ] A journey for a HALTED Futures bot with a position resumed through a closed session (it passes `venue_position_claims` today, untested end to end).
- [ ] A journey for the session reopened after an Emergency Stop with a position on the account refuses with the positions named.
- [ ] No existing journey is weakened: each that moves to a closed session keeps its assertions.

## 3. Design
Prefer the guard (an AST scan over `tests/integration/` for two `booted_*` entries in one test with the default) over a changed default, so a new world cannot reintroduce the blind spot (`CS-001` style: the net ships with the case). Give the guard a `Retire when:` line and a row in `tests/unit/architecture/scanned_roots_registry.py`.

## 3a. Reuse
`booted_two_venues(open_sessions=False)`, `_restarted_with_two_bots_left` (the BUG-250 journey): used. A UI need: none.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/unit/architecture/` (new guard) | restart journeys name their session choice |
| `tests/integration/modules/bots/` | the HALTED and Emergency-Stop journeys; moved restart journeys |
| `tests/unit/architecture/scanned_roots_registry.py` | the guard's scanned root |

## 5. Testing
The guard has a mutation case (`test_the_scanners_can_fail`, as `test_every_order_is_reconciled.py` does); the journeys run on the fake exchange. Not run.

## 6. Docs touched
none, because the test tiers' contract (`ci-rule.md` §2) already says a restart journey meets the real opening; a one-line addition to `testing-rule.md` §1 only if the guard needs a rule to cite.
