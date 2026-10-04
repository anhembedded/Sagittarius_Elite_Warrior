# BOT-149 — An every-pair history reads the user's own pairs first

**Status:** 🔵 Backlog
**Source:** The PR #344 review, finding 3 (2026-10-04), raised while fixing [BUG-145](../bug_report/completed/BUG-145_spot_desk_history_exhausts_request_weight.md).
**Risk:** 🟡 — it changes `IAccountHistoryReader.active_symbols`' "Sorted" promise, which `AccountHistoryReaderContract` locks, and every implementer.
**Complexity:** M — a port contract, two readers, the cache, the fake and the contract tests.
**SPEC (optional):** [SPEC-013](../../Docs/SPEC/SPEC-013_see_my_account_on_a_desk.md) step 4
**Depends on:** BUG-145 (merged with PR #344)

---

## 1. Context and problem
BUG-145 caps a Spot every-pair history at `SPOT_EVERY_SYMBOL_SCAN_LIMIT` (5) pairs, taken in the order `active_symbols` returns. Both readers return them sorted (`spot_history_reader.py`, `futures_history_reader.py`). On the Spot Testnet account, which holds about 500 assets, the five pairs read are therefore `0GUSDT, 1000CATUSDT, …`. A pair with an open order, or the pair a bot trades, is almost never among them. The page's notice says so truthfully, and "Hide other pairs" reads the desk's pair, but the every-pair tab rarely shows the user's own activity.

## 2. Acceptance criteria
- [ ] On Spot, an every-pair page that is capped reads the pairs with an open order first, then the desk's pair if the query names one, then the held assets.
- [ ] Within each group the order stays deterministic. The page's `scanned_symbols` and its notice still name what was read and how many pairs were left out.
- [ ] Futures, which has no cap, is unchanged.

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
