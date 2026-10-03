# BOT-146 — The oversized trading and live-stream test files fit under the 400-line ceiling, and a guard keeps `tests/` from growing past it

**Status:** 🔵 Backlog
**Source:** the independent review of `PR #294` (`EPIC-028B`), finding 3, 2026-09-29: the two files were already over the ceiling and grew by about 40 lines each of venue plumbing. The review of `PR #295` (`EPIC-028C`), finding 1, raised the same thing for a third file; a finding that recurs needs a guard, not another split.
**Risk:** 🟢 — a mechanical move of test classes; no production code changes
**Complexity:** S — three files, split along their existing test classes, plus a baseline guard
**Depends on:** None

---

## 1. Context and problem
`architecture-rule.md` §5.4 sets a 400-line ceiling that applies to `tests/` as well as `src/`. Two files are over it:
- `tests/unit/modules/trading/application/orders/test_execute_order.py`: 632 lines before `EPIC-028B`, 677 after.
- `tests/unit/modules/trading/application/session/test_emergency_stop.py`: 654 lines before `EPIC-028B`, 689 after.
- `tests/unit/modules/market_data/adapters/binance/test_binance_websocket_service.py`: 496 lines before `EPIC-028C`, 567 after (per-market connections). Its socket-choice tests already moved to `test_kline_sockets.py`.

`test_god_files_only_shrink.py` guards `src/` only, so nothing stops these files from growing again.

## 2. Acceptance criteria
- [ ] All three files are split along their existing test classes or concerns (for example safety gates, live submission, limits; subscription bookkeeping, message parsing, reconnect) into files of 400 lines or fewer.
- [ ] A shrink-only line-count baseline covers `tests/` the way `test_god_files_only_shrink.py` covers `src/`: a test file over 400 lines may not grow, and one that drops below leaves the baseline. It has a `scanned_roots_registry` row and a `Retire when:` line.
- [ ] The shared builders (`_build_handler`, `_handler`, the venue scope setup) live in one helper module per use case, not copied into each new file.
- [ ] `pytest --collect-only` lists the same test IDs before and after, apart from the module path (no test added, removed or weakened).

## 3. Design
Move classes, not assertions. Where a test class needs the builders, import them from the helper module.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/unit/modules/trading/application/orders/test_execute_order*.py` | split by class; shared helper module |
| `tests/unit/modules/trading/application/session/test_emergency_stop*.py` | split by class; shared helper module |
| `tests/unit/modules/market_data/adapters/binance/test_binance_websocket_service*.py` | split by concern |
| `tests/unit/architecture/` | the `tests/` line-count baseline and its guard |

## 5. Testing
Compare collected test IDs before and after; run the trading unit tests.
- Not run.

## Implementation notes (written when done)
Not started.
