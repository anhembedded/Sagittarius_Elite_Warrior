# EPIC-037F — One place issues BOT and BUG ids, open PR branches included

**Status:** 🔵 Planned — not started
**Source:** the owner's systems-thinking review, 2026-10-09 (see the epic README for the quote)
**Risk:** 🟢 — a small script; network access to list branches
**Complexity:** S — one script and a guard update
**Epic:** [EPIC-037](../README.md)
**Depends on:** None

---

## 1. Context and problem
On 2026-10-09 two parallel sessions both took `BOT-173` (PR #453 and PR #456), and a third took `BUG-197` because `BUG-196` was not yet on origin. Each session sees only its own branch.

## 2. Acceptance criteria
- [ ] `scripts/next_id.py BOT|BUG|PRO` prints the next free id after scanning `origin/master-warrior` and every open `claude/*` branch on origin (via `git ls-remote` and a shallow fetch of their `Tasks/` trees).
- [ ] The execute-task, fix-bug and create-bug-report instructions say to take ids from the script.
- [ ] `test_task_board_is_consistent.py` (or a new guard) fails on a duplicate id across tasks and bugs.

## 3. Design
A single issuer, as a database sequence is. When the network is unavailable the script says so and refuses rather than guessing.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `scripts/next_id.py` | new |
| `.claude/skills/execute-task/SKILL.md`, `.claude/skills/fix-bug/SKILL.md`, `.claude/rules/create-bug-report-rule.md` | point at the script |
| `tests/unit/test_task_board_is_consistent.py` | duplicate-id check |

## 5. Testing
Unit test of the id scan on a temporary git repository with two branches holding the same next id.

## Implementation notes (written when done)
Not started.
