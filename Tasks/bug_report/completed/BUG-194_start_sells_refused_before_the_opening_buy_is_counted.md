# BUG-194 — Start buys the opening inventory, then halts on the first SELL (`owner_budget_sell_exceeds_inventory`)

- **Reported:** 2026-10-09 (the owner, Spot Mainnet, bot `vce9z8`, three starts between 10:44 and 10:47, via the coordinator session)
- **Severity:** 🔴 P1 — real money: every Start paid for the opening buy and then stopped with the base held and no ladder
- **Status:** ✅ Fixed (2026-10-09)
- **Board:** Start halted on its first SELL because trading's owner book counted the opening buy only from the user-stream fill; fixed by having Start re-derive the inventory from the exchange's record before any SELL, and by counting each trade id once in the owner book.
- **Context:** SPEC-014 (run a grid bot) → `src/modules/bots/` (`application/services/grid_start_sequence.py`) and `src/modules/trading/` (`application/owner_book.py`, `owner_books.py`)
- **Environment:** Linux, master-warrior at `56f6b22`, Spot Mainnet, ETHUSDT, 5 grids, capital 35 USDT, range 2381–2718. The mainnet key had been refused (`-2015`, IP whitelist) minutes before; the log shows `spot_mainnet user stream down for 162 s` at 10:46:58.

## Reproduction
1. Start a Grid bot while the venue's user data stream delivers nothing (down, or later than the next order).
2. The opening market BUY is accepted and fills on the exchange.
3. The first SELL of the ladder is checked against the owner's inventory.

Expected: the SELL is judged against the base the opening buy bought. Actual: inventory 0, `owner_budget_sell_exceeds_inventory`, `STARTING -> HALTED on start_refused`. Reproduced at the integration tier with the composed app over the fake Binance server (`stream_up=False`): `L3 SELL: owner_budget_sell_exceeds_inventory`, the production line.

## Symptom
```
opening buy slice 1 of 20.93729400 USDT -> done SEW-vce9z8-3f85de06b9
L1 BUY 0.00290000 @ 2448.4 -> placed
L3 SELL 0.00270000 @ 2583.2 -> owner_budget_sell_exceeds_inventory
STARTING -> HALTED on start_refused (L3 SELL: owner_budget_sell_exceeds_inventory); L1 cancelled
```
The same on the third start (10:46:54, a new run: `Derived inventory ... 0 ETH ... from the run start, 0 order(s)`, then the same refusal).

## Root cause
`GridStartSequence.run` bought the opening and laid the ladder with nothing between them that read the exchange (`grid_start_sequence.py`, `_buy_opening` → `_place_ladder`). Trading's owner book learns a fill only from the venue's report (`VenueEventEmitter.order_filled` → `OwnerBooks.apply_fill`, `venue_event_emitter.py:86`); `SpotTradingClient.place_order` returns the order unchanged and drops the exchange's own FILLED answer (`spot_trading_client.py:92`). With the stream down, or slower than the pacer's spacing, `OwnerBook.inventory` stayed 0 and `TradingLimitPolicy` refused the SELL. The module docstring recorded this as a "Known limit"; a resume repaired it only because registration re-derives from history.

Second defect found on the way: `OwnerBook.apply_fill` had no memory of trade ids, so once the inventory is derived from history a late stream report of the same fill would be counted twice (`OwnerBooks.install` only de-duplicates fills held during the registration).

The gate was green because the integration harness's pacer delivered the stream's reports before every order turn (`grid_fake_exchange.DeliveringPacer`), so no journey ever started with a silent stream.

## Fix
- `grid_start_sequence.py`: between the opening buy and the ladder, `_count_opening` has trading register the budget again (`GridHousekeeping.register`, the same re-derivation Stop, Resume and reconciliation use), and lays the ladder only when the derived inventory covers the ladder's SELLs. Otherwise the start halts with `start_refused` before any ladder order, naming what the exchange's record holds. INFO line: `opening buy counted from the exchange's record: X ETH held, the ladder sells Y`.
- `owner_book.py` / `owner_books.py` / `register_owner_budget/handler.py`: the book takes the derivation's `counted` predicate and remembers the trade ids it applied, so a fill reported by the history and the stream, or twice by the stream, moves the inventory once.
- Test fakes: `FakeTradingSession` can answer a registration from the venue's record at that moment (`register_owner_budget_answers_from`); the simulated venue records the base it sold; the fake Binance server stamps trade ids on its stream reports (`"t"`), as the real one does.

## Regression test
- `tests/integration/modules/bots/test_a_start_with_the_user_stream_down_on_the_fake_exchange.py` — both tests failed before: `L3 SELL: owner_budget_sell_exceeds_inventory` and inventory 0; green after. With the book's de-duplication disabled the late-report test goes red with `0.047952 == 0.023976`.
- `tests/unit/modules/bots/application/services/test_grid_executor_start.py` — three tests: the registration happens after the opening slices and before any ladder order (with the INFO line), an opening buy the exchange does not show halts without a ladder, a refused registration halts naming the refusal.
- `tests/unit/modules/trading/application/test_owner_book.py` — a counted fill, a fill reported twice and two distinct fills of one order.

## Verification
Commit tier green on the fix commit (ruff check, ruff format --check, mypy over `src`+`scripts`, `check_skill_prompt_references.py`); the unit and integration suites of `bots` and `trading` green. The full gate is GitHub Actions' `ci-local.ps1 -Full` on the PR head. Not run on a real exchange, by instruction.

## Not fixed here
- The `-2010` on the resume: BUG-195.
- Base left behind by Start and Stop is by design (D6: a new run counts only its own orders). The owner's ETH from runs `3f85de06b9` and `c33f75ab1a` stays on the account until sold by hand; see the hand-off in the PR.
- A start whose market buy fills below the plan's quantity (slippage) still halts at the SELL check, now before any ladder order and with the shortfall named; sizing the SELLs to what was bought, as Resume does (`resized_for_inventory`), would remove that halt.
