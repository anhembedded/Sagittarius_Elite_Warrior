# BOT-146 — The execute-order and emergency-stop test files each fit under the 400-line ceiling

**Status:** 🔵 Backlog
**Source:** the independent review of `PR #294` (`EPIC-028B`), finding 3, 2026-09-29: the two files were already over the ceiling and grew by about 40 lines each of venue plumbing.
**Risk:** 🟢 — a mechanical move of test classes; no production code changes
**Complexity:** S — two files, split along their existing test classes
**Depends on:** None

---

## 1. Context and problem
`architecture-rule.md` §5.4 sets a 400-line ceiling that applies to `tests/` as well as `src/`. Two files are over it:
- `tests/unit/modules/trading/application/orders/test_execute_order.py`: 632 lines before `EPIC-028B`, 677 after.
- `tests/unit/modules/trading/application/session/test_emergency_stop.py`: 654 lines before `EPIC-028B`, 689 after.

`test_god_files_only_shrink.py` guards `src/` only, so nothing stops these files from growing again.

## 2. Acceptance criteria
- [ ] Both files are split along their existing test classes (for example safety gates, live submission, limits) into files of 400 lines or fewer.
- [ ] The shared builders (`_build_handler`, `_handler`, the venue scope setup) live in one helper module per use case, not copied into each new file.
- [ ] `pytest --collect-only` lists the same test IDs before and after, apart from the module path (no test added, removed or weakened).

## 3. Design
Move classes, not assertions. Where a test class needs the builders, import them from the helper module.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/unit/modules/trading/application/orders/test_execute_order*.py` | split by class; shared helper module |
| `tests/unit/modules/trading/application/session/test_emergency_stop*.py` | split by class; shared helper module |

## 5. Testing
Compare collected test IDs before and after; run the trading unit tests.
- Not run.

## Implementation notes (written when done)
Not started.
