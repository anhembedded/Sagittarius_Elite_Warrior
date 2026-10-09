# EPIC-037D — Sibling paths that do one job prove they give one result

**Status:** 🔵 Planned — not started
**Source:** the owner's systems-thinking review, 2026-10-09 (see the epic README for the quote)
**Risk:** 🟡 — parity tests can be slow or need fake-exchange support
**Complexity:** M — three parametrised families on the fake exchange and the replay
**Epic:** [EPIC-037](../README.md)
**Depends on:** None

---

## 1. Context and problem
Class A also covers sibling paths that drifted: BUG-194 (Start did not re-read the exchange's history; Stop and Resume did), BUG-191 (live exits compared closes; replay compared each candle's low and high), BUG-133 (the per-tick backtest loop lacked the static loop's SL/TP check), BUG-113 (a log fix applied to two sibling paths, not the third).

## 2. Acceptance criteria
- [ ] Family 1, inventory: Start, Resume and Stop each run with the user stream down on the fake exchange and end with the bot's inventory equal to the exchange's (one `pytest.mark.parametrize` over the entry points).
- [ ] Family 2, exits: live and replay evaluate the same wicked candle and agree on the SL/TP decision.
- [ ] Family 3, backtest loops: the static and the per-tick loop agree on exits for the same scenario.
- [ ] Each family is shown red by re-introducing its original bug (BUG-194, BUG-191, BUG-133).
- [ ] A short note in `testing-rule.md` names the pattern so a new sibling joins its family.

## 3. Design
Contract tests over a family of implementations, the same idea as the repository's interface-derived test doubles. Parametrise over entry points, never copy the test per path.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/integration/modules/bots/test_entry_paths_agree_on_inventory.py` | family 1 |
| `tests/unit/modules/bots/test_live_and_replay_agree_on_exits.py` | family 2 |
| `tests/unit/modules/backtesting/test_backtest_loops_agree_on_exits.py` | family 3 |
| `.claude/rules/testing-rule.md` | one clause naming the pattern |

## 5. Testing
Integration and unit tiers; red-then-green with each original bug re-introduced, recorded in Implementation notes.

## Implementation notes (written when done)
Not started.
