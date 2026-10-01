# EPIC-028Q — The Phase 2 readers tell the truth about what they could not read

**Status:** ✅ Done (2026-10-01) — merged in PR #301
**Source:** the epic-level review on PR #300 (§3), 2026-10-01. The user agreed on 2026-10-01: *"đồng ý, làm theo đề xuất của bạn"* ("agreed, do as you propose").
**Risk:** 🟡 — history and balance figures shown as complete when they are not
**Complexity:** M — two readers, one refresh service, one gate's wording, fake routes
**Epic:** [EPIC-028](../README.md)
**Depends on:** [EPIC-028E](../completed/EPIC-028E_open_orders_and_history_readers.md), [EPIC-028F](../completed/EPIC-028F_commission_and_futures_account_controls.md)

---

## 1. Context and problem
The review found these defects in merged Phase 2 code:
1. **Futures order history silently drops orders.** Binance's `allOrders` does not return CANCELED or EXPIRED orders with no fill that are older than 3 days. `i_account_history_reader.py` promises "complete or raise, never truncated", and `HistoryPage` does not disclose the gap.
2. **"Every symbol" history leaves out closed trades.** `active_symbols` takes open positions and open orders only (`futures_history_reader.py`), so a round trip already closed inside the window never appears.
3. **Reader errors escape the port's contract.** Row mapping runs outside `history_read_failures` in both history readers, so a malformed row raises a raw `KeyError` or `InvalidOperation` instead of `AccountHistoryUnavailableError`.
4. **The leverage gate states an exchange fact that may be false.** ADR D7 and `account_control_gate.py` refuse any leverage change while a position is open, as "the rule Binance enforces". Binance may allow raising leverage with a position open; this needs a Testnet check.
5. **Spot rate-limit exposure.** A 7-day read costs 8 windows × weight 20, per symbol, per endpoint, and every page click re-reads the span.
6. **Smaller items:**
   - a negative `cummulativeQuoteQty` becomes a negative average price, where it should be `None`;
   - a failed summary read leaves the last balance on screen with no stale marker;
   - Multi-Assets mode is not read;
   - the Spot commission reader's docstring is wrong about python-binance.

## 2. Acceptance criteria
- [x] Order history says what it cannot see. A Futures page discloses that unfilled cancelled or expired orders older than 3 days are not returned, and the port's docstring states it as a limit.
- [x] "Every symbol" includes symbols traded in the window — on Futures, from `/fapi/v1/income`. *Spot deviates:* no Spot endpoint lists traded pairs, and the trades are read only after the pairs are chosen, so a sold-out pair cannot be found; Spot discloses that gap instead (§3).
- [x] Every row mapping runs inside the port's error translation, with a test feeding a malformed row to each reader.
- [x] The leverage gate's rule is documented as the app's own policy. The Testnet check is not possible from this repository's sessions (egress to `*.binance.*` is blocked), so the policy is stated as unverified against the exchange.
- [x] A negative `cummulativeQuoteQty` gives no average price.
- [x] A failed summary read publishes a stale marker. *The desk showing it* moves to [EPIC-028J](../incomplete/EPIC-028J_account_tabs_and_summary_panels.md), whose summary panel is the first consumer of either summary event.
- [x] The Spot history cost is bounded by caching the span per page, and a test counts the requests.
- [x] The fake Futures routes enforce the 7-day span and the 3-day purge. *Non-empty `userTrades`* moves to [EPIC-028O](../incomplete/EPIC-028O_order_contract_and_missing_reads.md): it needs the fake to fill market orders, which existing tests rely on it not doing. Reading Multi-Assets mode moves there too.

## 3. Design (as built)
- **Mapping inside the translation.** `history_reads.MAPPING_FAILURES` (`KeyError`, `TypeError`, `ValueError`, `ArithmeticError`) is translated by `history_read_failures` as `"<what>: malformed row: …"`. Both readers map inside the `with` block, and `active_symbols` does too.
- **Gaps are data, not prose.** `HistoryGaps(order_history, every_symbol)` is what a reader's `known_gaps()` returns, one sentence per gap. The order and trade history handlers copy them onto `HistoryPage.notices`:
  - an order page carries the order-history gaps, and the every-symbol gaps only when it covers every symbol;
  - a trade page carries only the every-symbol gaps, since a fill is never purged.
- **`active_symbols(since)`.** The port method takes the window. On Futures it adds every symbol with income in the span, read in 7-day windows. A fill always books a commission, so a closed round trip is found. On Spot `since` is checked but not used.
- **`CachedAccountHistoryReader`** decorates the port. `VenueAssembly` wraps both venues' readers in it.
  - For 15 s after reading `(symbol, since)`, it serves any later `since` from that read, with older rows dropped.
  - A read further back, an expired entry or a clock stepped back goes to the exchange.
  - `active_symbols` is reused for the same `since` only.
  - Failures are never cached, and the lookback check runs on every call.
  - The cost is that a fill shows up at most 15 s late.
- **`AccountSummaryStaleEvent(reason, venue)`.** It is published once per run of failed summary reads: a raised error, or no summary, which is how `check_connection` reports most failures. The next good read republishes the summary even when unchanged, and that ends the marker. Failures take part in the service's ticket rule both ways.
- **Fake exchange.**
  - `/fapi/v1/income` is served from the history log.
  - Futures history spans over 7 days are refused with `-1127`.
  - `allOrders` drops unfilled cancelled or expired orders older than 3 days.
- **Spot average price.** A negative `cummulativeQuoteQty` now gives no average price; the mapper returns `None`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/history_gaps.py` | new |
| `src/modules/trading/contracts/i_account_history_reader.py` | `active_symbols(since)`, `known_gaps()`, limits stated |
| `src/modules/trading/contracts/history_page.py` · `application/history_paging.py` | `notices` |
| `src/modules/trading/application/queries/get_order_history/handler.py` · `get_trade_history/handler.py` | pass `since`, copy notices |
| `src/modules/trading/adapters/binance/history_reads.py` | `MAPPING_FAILURES` |
| `src/modules/trading/adapters/binance/futures_history_reader.py` · `spot/spot_history_reader.py` | mapping inside translation, `since`, gaps, income |
| `src/modules/trading/adapters/binance/spot/spot_history_payload_mapper.py` | negative quote → no average price |
| `src/modules/trading/adapters/binance/cached_history_reader.py` | new |
| `src/modules/trading/composition/venue_assembly.py` | wraps both readers |
| `src/modules/trading/contracts/events/account_summary_stale_event.py` | new |
| `src/modules/trading/application/account_summary_refresh_service.py` | stale marker |
| `src/support/binance_gateway/contracts/i_trading_session_factory.py` | `futures_income_history` |
| `account_control_gate.py` · `i_futures_account_control.py` · ADR D7 | policy wording |
| `spot_commission_rate_reader.py` · `i_commission_rate_reader.py` | SDK claim corrected |
| `contracts/testing/` (contract suite, fake reader, unarranged ports) | `since`, gaps |
| `tests/sanity/fake_exchange/futures_routes.py` · `history_log.py` | income, span, purge |

## 5. Testing
Each new condition was mutated and a test turned red, with two exceptions. `<` → `<=` on the refresh ticket survives but is equivalent, because tickets are unique. The PR #301 review found one more survivor: the cache's `since` guard on trades, whose test covered orders only. That guard now lives in one helper shared by orders and trades (`_SymbolHistoryCache`), and the earlier-`since` test runs on both kinds.
- **Malformed rows.** Each reader is fed a malformed row and raises `AccountHistoryUnavailableError` naming it (`test_history_readers.py`).
- **Income and gaps.**
  - Futures `active_symbols` includes a pair traded since `since` with nothing open, and reads income from the first window's start.
  - Each reader states its venue's gaps.
  - The handlers copy them by page kind and pass the query's `since` (`test_get_history_pages.py`).
- **Cache.**
  - The contract suite runs against the cache.
  - Reads are counted on the verified fake, for each case: a repeat, a later `since`, an earlier `since`, at the TTL, a clock stepped back, a failure, the lookback, active symbols.
  - Against the fake exchange, a second page sends no `/api/v3/myTrades` request, while the bare reader sends every window again (`test_history_readers_against_fake_server.py`).
- **Stale marker.**
  - One event per run of failures.
  - The marker clears on an unchanged good read.
  - It marks again after a recovery.
  - A late failure, or a late good read, is resolved by the ticket rule (`test_account_summary_refresh_service.py`).
- **Wiring.** `VenueAssembly` wraps each venue's real reader (`test_module_venue_contexts_binding.py`).
- **Runs.** `tests/unit` + `tests/integration`: 6683 passed, 4 skipped. `ruff`, `mypy` (839 files) and the architecture guards are green.

## Implementation notes (written when done)
- The review's §3 item 2 asked for Spot traded pairs "from the trades already read". That is circular: trades are read per pair after the pairs are chosen. The Spot gap is disclosed instead.
- The 15 s TTL trades freshness for request weight. EPIC-028J's tabs must keep `since` fixed while paging, or every page is a miss.
