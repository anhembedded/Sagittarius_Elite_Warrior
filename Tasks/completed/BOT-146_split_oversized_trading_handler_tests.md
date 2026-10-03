# BOT-146 — The oversized trading and live-stream test files fit under the 400-line ceiling, and a guard keeps `tests/` from growing past it

**Status:** ✅ Done (2026-10-03)
**Source:** the independent review of `PR #294` (`EPIC-028B`), finding 3, 2026-09-29: the two files were already over the ceiling and grew by about 40 lines each of venue plumbing. The review of `PR #295` (`EPIC-028C`), finding 1, raised the same thing for a third file; a finding that recurs needs a guard, not another split.
**Risk:** 🟢 — a mechanical move of test classes; no production code changes
**Complexity:** S — three files, split along their existing test classes, plus a baseline guard
**Depends on:** None

---

## 1. Context and problem
`architecture-rule.md` §5.4 sets a 400-line ceiling that applies to `tests/` as well as `src/`. Three files are over it:
- `tests/unit/modules/trading/application/orders/test_execute_order.py`: 632 lines before `EPIC-028B`, 677 after.
- `tests/unit/modules/trading/application/session/test_emergency_stop.py`: 654 lines before `EPIC-028B`, 689 after.
- `tests/unit/modules/market_data/adapters/binance/test_binance_websocket_service.py`: 496 lines before `EPIC-028C`, 567 after (per-market connections). Its socket-choice tests already moved to `test_kline_sockets.py`.

`test_god_files_only_shrink.py` guards `src/` only, so nothing stops these files from growing again.

## 2. Acceptance criteria
- [x] All three files are split along their existing test classes or concerns into files of 400 lines or fewer:
  - `test_execute_order.py` (748) became `test_execute_order_safety_gates.py` (280), `test_execute_order_rejections.py` (174) and `test_execute_order_submission.py` (193).
  - `test_emergency_stop.py` (701) became `test_emergency_stop.py` (317) and `test_emergency_stop_spot.py` (254).
  - `test_binance_websocket_service.py` (567) became `test_binance_websocket_subscriptions.py` (207) and `test_binance_websocket_service.py` (375).
- [x] A shrink-only line-count baseline covers `tests/`. `test_god_files_only_shrink.py` now runs every check once per tree, against `baseline_god_files.json` for `src/` and the new `baseline_test_god_files.json` for `tests/` (28 files that predate the guard). Its registry row lists both roots, and its `Retire when:` line names both baselines. Mutation-verified: a line added to a baselined test file fails `test_known_god_files_do_not_grow[tests]`, and a new 401-line test file fails `test_no_new_god_files_appear[tests]`.
- [x] The shared builders live in one helper module per use case: `orders/execute_order_builders.py` and `session/emergency_stop_builders.py`. `test_execute_protective_order.py`, which had imported `_handler` and `_order_request` from the old `test_execute_order.py`, now imports them from the builders module. The websocket files share only two `MarketType` aliases, which each keeps.
- [x] `pytest --collect-only` lists the same 157 test IDs before and after (class and test name, module path aside): `diff` is empty.

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
- Test IDs over `orders/`, `session/` and `market_data/adapters/binance/`: 157 before, 157 after, `diff` empty.
- `tests/unit/modules/trading/application` and `tests/unit/modules/market_data/adapters/binance`: 296 passed.
- `tests/unit/architecture`: 488 passed. The ratchet is mutation-verified on both its `tests/` failure modes.

## Implementation notes (written when done)
- **Classes moved, not assertions.** A scratch script cut the files at class boundaries. The private helpers became public names in the builders modules (`_handler` became `make_handler`, `_metadata_provider` became `static_metadata_provider`, and so on), and unused imports were removed with `ruff --fix`. No test body changed apart from those names.
- **The split exposed one copy:** `test_execute_protective_order.py` imported its handler from another test module. That is exactly the coupling a builders module removes.
- **`tools/measure_god_files.py` takes a root** (`src` or `tests`, `--root` on the command line). `tools/` stays unmeasured: it is small and has not grown.
- **Baselines must equal their measurements (PR #316 review, finding 2).** A fourth check, `test_baseline_entries_match_their_measurement`, fails an entry recorded above its file's current count, so the commit that shrinks a file also tightens its baseline. It found two loose `src/` entries, `app_bootstrapper.py` (550, measured 543) and `backtest_presenter.py` (2260, measured 2259), now tightened.
- **Docs that cited the old file now name the new ones:** HLD 10 (`TestConcurrentDispatch`) and SPEC-005's proof table. Closed task and bug records keep their historical paths; the open `EPIC-026I` plan now names `test_execute_order_submission.py`.
