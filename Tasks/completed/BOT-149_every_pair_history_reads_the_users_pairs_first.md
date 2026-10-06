# BOT-149 — An every-pair history reads the user's own pairs first

**Status:** ✅ Done (2026-10-06)
**Source:** The PR #344 review, finding 3 (2026-10-04), raised while fixing [BUG-145](../bug_report/completed/BUG-145_spot_desk_history_exhausts_request_weight.md).
**Risk:** 🟡 — it changes `IAccountHistoryReader.active_symbols`' "Sorted" promise, which `AccountHistoryReaderContract` locks, and every implementer.
**Complexity:** M — a port contract, two readers, the cache, the fake and the contract tests.
**SPEC (optional):** [SPEC-013](../../Docs/SPEC/SPEC-013_see_my_account_on_a_desk.md) step 4
**Depends on:** BUG-145 (merged with PR #344)

---

## 1. Context and problem
BUG-145 caps a Spot every-pair history at `SPOT_EVERY_SYMBOL_SCAN_LIMIT` (5) pairs, taken in the order `active_symbols` returns. Both readers return them sorted (`spot_history_reader.py`, `futures_history_reader.py`). On the Spot Testnet account, which holds about 500 assets, the five pairs read are therefore `0GUSDT, 1000CATUSDT, …`. A pair with an open order, or the pair a bot trades, is almost never among them. The page's notice says so truthfully, and "Hide other pairs" reads the desk's pair, but the every-pair tab rarely shows the user's own activity.

## 2. Acceptance criteria
- [x] On Spot, an every-pair page that is capped reads the pairs with an open order first, then the desk's pair if the query names one, then the held assets.
- [x] Within each group the order stays deterministic. The page's `scanned_symbols` and its notice still name what was read and how many pairs were left out.
- [x] Futures, which has no cap, is unchanged.

## 3. Design
To be decided. One option keeps `active_symbols` a set of pairs and adds a priority to it, for example a `(symbol, reason)` pair whose reason is open order, traded or held, which `history_scope` sorts by. The other option has each reader return its pairs already in priority order and drops "Sorted" from the contract. The first keeps the order a policy in the application layer.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/i_account_history_reader.py` | The active-pairs contract carries priority or order |
| `src/modules/trading/adapters/binance/spot/spot_history_reader.py`, `futures_history_reader.py`, `cached_history_reader.py` | Implement it |
| `src/modules/trading/contracts/testing/` | Fake and contract test |
| `src/modules/trading/application/history_scope.py` | Read the user's pairs first |

## 5. Testing
Unit tests: a capped page on a fake holding many pairs plus one open-order pair reads the open-order pair. The contract test locks the new ordering for every implementer.

## Implementation notes
**Design chosen: the first option.** `IAccountHistoryReader.active_symbols` now returns `tuple[ActiveSymbol, ...]` (`contracts/active_symbol.py`): each pair once, with its strongest `ActiveReason` (open order, traded, held), sorted by symbol. The reader states the fact; the order stays a policy of the application layer. `active_symbols_from` builds that tuple for both readers, so the dedup-and-sort rule lives once.

`history_scope` ranks a capped page's pairs: open order, then the desk's pair, then traded, then held, each group by symbol. An uncapped page, and a capped one that fits, keeps plain symbol order, so Futures (no cap) is unchanged. A desk pair that is not active is not added (it would spend weight on a pair the venue does not name); a desk pair that also has an open order is read once.

Every implementer changed in the one commit: both readers, the cache, the verified fake (new `held_symbols`), `UnarrangedHistoryReader`, the contract tests (a pair once, sorted, a reason) and the adapter and integration tests. The scope has its own unit tests, mutation-checked (ranking by symbol only fails three of them).

**The desk's pair reaches the scope:** `HistoryRequest.desk_symbol` and the two history queries carry it to `history_scope`, and `HistoryTabsLoader.open` sets it from the presenter's symbol (the driving session approved this one UI change on 2026-10-06). A handler test shows a capped page reading open orders, then the desk's pair. The test-file split (`test_history_reader_active_symbols.py`) takes `test_history_readers.py` below the 400-line ceiling and its god-file baseline entry goes.

