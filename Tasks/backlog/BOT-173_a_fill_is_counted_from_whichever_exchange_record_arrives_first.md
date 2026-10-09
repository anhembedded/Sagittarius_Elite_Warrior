# BOT-173 — A fill is counted from whichever exchange record arrives first, exactly once, keyed by trade id

**Status:** 🟡 In progress
**Board:** Trading's owner book and the bots' ladder learned a fill only from the user-data stream (or a history re-read); the order response, the stream and the trade history now each report a fill once, keyed by trade id, whichever arrives first.
**Source:** the owner, 2026-10-09 via the coordinator session: "a fill is counted from whichever exchange evidence arrives first — the order response, the user stream, or the REST trade history (reconcile) — exactly once, keyed by trade id; the stream becomes a latency path, not the source of truth." BUG-194 was one symptom; #452 patched only Start.
**Risk:** 🟡 — the order response becomes a second writer of the owner book and of the bus's fill event; a wrong key double-counts base (a SELL larger than the base held) or loses a fill (a ladder that never places its counter order)
**Complexity:** M — one new port, one parser, one ledger, one wiring change; Futures untouched
**SPEC:** [SPEC-014](../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** BUG-194 (#452, merged): trade-id de-duplication in `OwnerBook`.

---

## 1. Context and problem
`SpotTradingClient.place_order` returns the order unchanged and drops the exchange's own answer (`spot_trading_client.py:92`), although Binance returns `status` and `fills` (with `tradeId`) for a market order (`newOrderRespType FULL`, which the fake exchange returns too). Trading learns a fill only in `VenueEventEmitter.order_filled` (`venue_event_emitter.py`), called by `SpotUserDataStream._handle_execution_report` and nowhere else. Docstrings say so (`user_stream_watch.py`: "The stream is the only source of fills"; `spot_trading_client.py`: "the authoritative order lifecycle is what the Spot User Data Stream reports"; `owner_book.py`: "kept current by the venue's user-data path"). A silent or late stream therefore leaves the owner book without the opening buy and the SL/TP market sells (BUG-194), the bots' ladder without the fill, and the inventory wrong until a registration re-reads history.

Survey of where a fill is counted today:

| Place | Source | Dedup today |
| :-- | :-- | :-- |
| `OwnerBook.apply_fill` (trading) | the emitter (stream); the deriver's history replay at registration | `counted` (derivation) ∪ `_applied` (trade ids), BUG-194 |
| `OrderFilledEvent` on the bus (desk, bots) | the emitter (stream) | none: a duplicate report is a second event |
| `GridFacts._apply_fill` (bots) | the bus event | `AppliedFills` (client order id, trade id), EPIC-035P |
| `GridReconciler._catch_up` (bots) | REST order and trade history | records its trade ids in `AppliedFills` |

## 2. Acceptance criteria
- [ ] A market order's fills in the placement response are counted by the owner book and published as `OrderFilledEvent` (with their trade ids) while the user stream is down; the opening buy and a stop-loss or take-profit market SELL need no stream report.
- [ ] A fill is counted once in every arrival order: response then stream, stream then response, response then history (registration), history then response; the book's inventory, the bus (one `OrderFilledEvent` per trade) and the bots' ladder each see it once.
- [ ] The bots' ladder state obeys the same rule: a fill the response reported and the stream reports later is applied once (`AppliedFills`), and the stream-only statements in the bots docstrings are corrected. The stream-down halt (`USER_STREAM_DOWN`) stays, for the limit orders only the stream or a reconcile can see; this task does not remove it.
- [ ] A response with no readable trade id for a fill reports nothing for that fill and logs a WARNING (a fill with no key cannot be counted once); a rejected or unknown-outcome send reports nothing.
- [ ] Futures is unchanged (its response carries no fills).
- [ ] The docstrings and HLD text that state the old principle say the new one.
- [ ] Tests on the fake exchange with the stream down: the integration journey (Start, an SL/TP-style market SELL) and the arrival-order unit tests above; each goes red when the key or the response path is removed.

## 3. Design
**Principle.** Exchange evidence is a set of records about trades; a trade is counted when the first record of it arrives, and a later record of the same trade is recognised by its trade id and dropped. The stream is the lowest-latency source for resting orders, never the only one.

**Where the key lives.** Trading, at the one place a fill enters the app: `VenueEventEmitter.order_filled` (its docstring already makes it the single door, ADR D6). A bounded `ReportedTrades` ledger (new, `trading/application/reported_trades.py`, keyed by (symbol, trade id), the shape of the bots' `AppliedFills`) decides there whether a trade was reported; if so neither the owner books nor the bus see it again. Registration-time history stays covered by the book's `counted` predicate (BUG-194); the bots' `AppliedFills` stays for fills their own reconcile applied from history.

**How the response reaches the door.** A new port `IOrderFillReporter` (`trading/contracts`, ABC) with `order_filled(order, fill, fee, trade_id)`; `VenueEventEmitter` implements it, so the stream and the client report through one object. `SpotTradingClient` gets the reporter, parses the response (`spot_order_response_fills.py`: the order via the existing payload mapper, one `(price, quantity, fee, trade id)` per `fills` entry) and reports each fill after `create_order` returned. `ITradingClient.place_order` keeps its signature, so Futures, the read-only client and every double stay as they are (BUG-026); the fills travel as events, as every fill already does. `execute_order` records the order as sent before the send (existing), and the book already holds a fill that precedes `record_sent` (`_early`).
The emitter becomes one object per venue (`VenueAssembly.fill_events`, built once) handed to the stream and to the Spot client factory.

**Rejected alternatives.** (1) `place_order` returning `PlacedOrder(order, fills)`: breaks every `ITradingClient` implementer and caller for data that is an event anyway. (2) Applying the response in `execute_order`'s handler: application code would parse a Binance payload or need a second fill path to the bus. (3) Dropping the bots' `AppliedFills`: it also covers fills the bots applied from their own history reads, which trading's ledger does not see; it stays and the principle is the same.

**Seam, variant later (P7).** The port is the seam for a future REST-poll source or a Futures response; none is built. The ledger's limit is a constant like `AppliedFills`'.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `trading/contracts/i_order_fill_reporter.py` | new port |
| `trading/application/reported_trades.py` | new bounded ledger |
| `trading/adapters/binance/venue_event_emitter.py` | implements the port, de-duplicates on the ledger |
| `trading/adapters/binance/spot/spot_order_response_fills.py` | new: response → fills |
| `trading/adapters/binance/spot/spot_trading_client.py`, `spot_trading_client_factory.py` | report the response's fills |
| `trading/composition/venue_assembly.py` | one emitter per venue, shared |
| docstrings: `user_stream_watch.py`, `spot_trading_client.py`, `owner_book.py`, `grid_start_sequence.py`, `applied_fills.py`, HLD/SPEC where they say it | the new principle |
| tests | see §5 |

## 5. Testing
| Criterion | Test | Tier |
| :-- | :-- | :-- |
| response fills counted with the stream down; SL/TP market SELL | `tests/integration/modules/bots/test_fills_from_the_order_response_on_the_fake_exchange.py` | integration |
| each arrival order, one bus event per trade | `tests/unit/modules/trading/adapters/binance/test_venue_event_emitter_trade_dedup.py` | unit |
| response parsing, unreadable trade id, rejected send | `tests/unit/modules/trading/adapters/binance/spot/test_spot_order_response_fills.py` · `test_spot_trading_client.py` | unit |
| ladder applies once | `tests/unit/modules/bots/application/services/test_grid_duplicate_fill.py` (extended) | unit |

## Implementation notes (written when done)
Pending.
