# EPIC-028S — The PR 309 re-review's findings closed: fail-closed reconciliation, a desk that re-reads after a fill, F9 proven in the composed app

**Status:** ✅ Done (2026-10-02)
**Source:** the user, 2026-10-02: *"tiếp, làm 1 + 2 + 3 trong một PR"* ("go on, do 1 + 2 + 3 in one PR"). The three items are from the author's report after PR 309 merged: (1) the re-review's optional findings a–e, (2) the desk order panel not re-reading after a fill, (3) an F9 integration test with a venue on.
**Risk:** 🟢 — two one-line wirings, a stricter contract rule, comments and tests.
**Complexity:** S — no new mechanism; the integration fixture is the largest piece.
**Epic:** [EPIC-028](../README.md)
**SPEC:** [SPEC-005](../../../../Docs/SPEC/SPEC-005_place_a_manual_order.md), [SPEC-013](../../../../Docs/SPEC/SPEC-013_see_my_account_on_a_desk.md)
**Depends on:** [EPIC-028M](EPIC-028M_retire_single_trading_screen_and_docs.md) (merged, PR 309)

---

## 1. Context and problem
The independent re-review of PR 309 (head `661ec14`) passed with five optional findings, and the first review left one more open:
- **a.** `EnableTradingResult.account_was_read` was a deny-list of the block reasons decided before the read. A block reason added later would count as "read", and its empty tuples would wipe the Dev Board's tables: the defect PR 309 fixed.
- **b.** Five comments still named the deleted Trading screen's files (`trading_presenter.py`, `TradingView`, `test_trading_presenter_*.py`).
- **c.** No desk re-read its order panel after a fill (`desk_presenter.py` re-read it only on `accountChanged`), so a strategy's fill left the panel's available balance and sellable holding from before it. The Dev Board's F9 already re-read, and its docstring said "as a desk does".
- **d.** The new Dev Board tests added function-local imports.
- **e.** `test_the_dialog_rereads_its_balances_when_the_session_changed_the_account` killed its mutant on `context is None`, not on an old balance.
- **First review, finding 5.** No test exercised F9 with a venue enabled in the composed app: the suite boots with trading off.

## 2. Acceptance criteria
- [x] `account_was_read` is true only for a success and the refusals decided after the read; every `EnableTradingBlockReason` must be classified by a test.
- [x] A desk's order panel re-reads its balances after each of its venue's fills, and not after the other venue's.
- [x] No comment or docstring in `src`/`tests` presents a file of the deleted screen as current.
- [x] The re-read test sees 1000 replaced by 900. The new tests' imports are at the top of the file.
- [x] In the composed app with Spot Testnet on, against the fake Binance server:
  - F9 shows the venue's balance;
  - a Buy while trading is off is refused in words and never sent;
  - a resting Limit reaches the exchange and joins the Dev Board's Open orders.

## 3. Design
- **a. An allow-list (`_DECIDED_AFTER_READING`).** It fails closed. A derived property, not a field: `_blocked()` is the only place that decides before reading, and a field would change every constructor (pitfall 1 of `pitfalls/source.md`).
  - `test_enable_trading_result.py` asserts that the two sets partition `EnableTradingBlockReason`, so a new reason fails until someone places it.
  - The handler's tests already pin each side against the real read order.
- **c. One connection in `DeskPresenter`:** `feeds.orders.orderFilled → order_entry.refresh`, beside the fill marker. With it, the Dev Board's "as a desk does" holds.
- **F9 integration.** A fixture in the new test file boots `create_app()` with `exchange.trading_venues = ["spot_testnet"]`, the venue's key pair in the environment, and `Client.API_TESTNET_URL` on `run_binance_fake_server()`. The chart's market data uses this directory's seeded fakes, and the order dialog is a recorded Yes. The real dispatcher, handlers and adapters run.
  - Two seams are set directly rather than driven, each said in the file:
    - the "trading on" test enables the session state, because the toggle would also start the user-data websocket, which the fake server does not speak;
    - `binance.base_client.get_loop` returns one fixture-owned loop. `BUG-075`: `python-binance` gives each worker thread a new loop and never closes it. The orphan surfaced as an unraisable exception on the first run.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/enable_trading_result.py` | deny-list → allow-list `_DECIDED_AFTER_READING` |
| `src/modules/trading/ui/desk/desk_screen/desk_presenter.py` | a fill re-reads the order panel |
| `src/modules/strategy/module.py`, `src/modules/market_data/ui/market_tick_feed.py` | stale references reworded |
| `tests/unit/modules/trading/contracts/test_enable_trading_result.py` | new: classification and both sides |
| `tests/unit/modules/trading/ui/desk/test_desk_live_feeds.py` | the fill re-read, venue-filtered |
| `tests/unit/modules/trading/ui/dashboard/test_dashboard_presenter.py` | imports to the top (and five redundant local `Decimal`/`datetime` imports gone); the re-read test reads first; three comments reworded |
| `tests/unit/architecture/test_guard_scans_its_registered_root.py` | a reference to the retired guard in the past tense |
| `tests/integration/presentation/ui/test_dev_board_f9_against_fake_server.py` | new: F9 in the composed app with a venue on |
| `tests/integration/presentation/ui/test_dev_board_order_dialog.py` | points at the new file |
| `Docs/SPEC/SPEC-005_place_a_manual_order.md`, `SPEC-013_see_my_account_on_a_desk.md` | proof row; a fill re-reads the panel |

## 5. Testing
| Criterion | Test | Tier | Mutation that fails it |
| :--- | :--- | :--- | :--- |
| allow-list | `test_enable_trading_result.py` (all), handler tests in `test_enable_trading.py` | unit | `UNEXPECTED_POSITIONS` dropped from the set: the classification and the parametrized "read" test fail |
| desk fill re-read | `test_desk_live_feeds.py::test_a_fill_of_the_venue_rereads_the_order_panels_balances` | unit | the connection removed: 1000 ≠ 900 |
| re-read replaces | `test_dashboard_presenter.py::test_the_dialog_rereads_…` | unit | `accountChanged → entry.refresh` removed: 1000 ≠ 900 (previously `AttributeError`) |
| F9 composed | `test_dev_board_f9_against_fake_server.py` (3 tests) | integration | `orderAccepted → on_order_filled` removed: the Open orders wait times out after the POST reached the exchange |

## Implementation notes (written when done)
- **The first F9 run found two wrong assumptions in the test, not in the app.**
  - The gate is `TRADING_SWITCH_OFF`; there is no `TRADING_DISABLED`.
  - The board's default symbol is ETHUSDT, so the row assertion uses the board's own symbol.
- **`BUG-075` appeared as an unraisable `BaseEventLoop.__del__` ("Invalid file descriptor").** It is fixed in this fixture by owning the clients' loop. The file passes with `-W error::pytest.PytestUnraisableExceptionWarning`.
- **Verification:** the fast gate, architecture guards, the trading and strategy unit suites, and the presentation integration tests. Results are in the PR.
