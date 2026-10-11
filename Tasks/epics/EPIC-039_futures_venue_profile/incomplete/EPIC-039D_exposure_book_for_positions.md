# EPIC-039D — A Futures bot's position is derived from the exchange's evidence, like Spot's inventory, and checked against the exchange

**Status:** 🔵 Planned — not started
**Source:** the owner, 2026-10-10; [DESIGN §3](../DESIGN_2026-10-10_futures_venue_profile.md) and `trading/contracts/owner_budget.py`'s own note: "a Futures owner (the inventory becomes a position; one deriver behind the same registration)".
**Risk:** 🔴 — the bookkeeping that decides what a leveraged bot thinks it holds; a wrong position is a wrong stop, a wrong reconcile, a wrong liquidation guard
**Complexity:** L — a deriver, a book variant, a budget in margin/notional, a reconcile, the foreign-position rule
**Epic:** [EPIC-039](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) gains the Futures start refusals once `039H` lands; nothing for Spot.
**Design:** [DESIGN §3](../DESIGN_2026-10-10_futures_venue_profile.md) · **Decision:** D5, O2, O11 ([record](../DECISION_2026-10-10_futures_venue_profile.md))
**Depends on:** [039A](EPIC-039A_venue_profile_seam.md), [039C](EPIC-039C_futures_fake_exchange_matching.md) (a fake that fills).

---

## 1. Context and problem
On Spot, trading keeps an **owner book** per bot (ADR D6): the owner's open orders, an **inventory** (base held net of base-asset fees, with cost) *derived from the venue's history of tagged orders*, never supplied by the owner, and the send times. A Futures bot holds a **signed position** with an average entry, margin and no base asset. It must be derived the same way, and checked against what the exchange says.

### Facts verified on `master-warrior` `076d339`
- `trading/application/owner_book.py` (`OwnerBook`, `nothing_counted`), `owner_books.py` (`OwnerBooks`, `OwnerShare`, `OwnerEventBuffer`: a registration opens a buffer before its reads, replays uncounted fills by trade id under the lock), `owner_inventory_deriver.py` (reads history since `run_started_at`, keeps tagged orders, replays fills joined by exchange order id, minus base-asset fees; checkpoints via `IOwnerInventoryCheckpoints` for runs longer than the venue's 30-day history), `earlier_runs_deriver.py` (what earlier runs left, never traded: `BUG-196`).
- `trading/contracts/owner_budget.py`: `OwnerBudget(max_open_orders, max_exposure_quote, min_order_spacing, max_orders_per_window, window)`; `max_exposure_quote` = "open BUY quote plus the inventory at cost"; `OwnerInventory(quantity, cost)`; caps `OwnerBudgetCaps`.
- `trading/contracts/owner_budget_registration.py` (`OwnerBudgetRegistration`, `OwnerBudgetRefusal`, `…Result`) and the `register_owner_budget` use through the trading session port (read `i_trading_session.py`).
- `trading/application/position_state_reconciler.py` and `position_refresh_service.py` keep `known_open_symbols` and `LivePosition` current from `ACCOUNT_UPDATE`.
- `LivePosition` is **one-way only**: direction from the sign of `position_amt`, `liquidation_price` read from the exchange (`contracts/live_position.py`). `OrderFilledEvent.fee_amount` is `None` for Futures (see 039G; **to verify**).
- A symbol has one lease holder (one owner per symbol), so a position on the symbol belongs to the bot **only if none existed before it started**.
- The bot-side log line to avoid reproducing: `gap reconcile disagrees (inventory_mismatch: saved 0 against 0.00679320 derived from the exchange)` (RESEARCH §7).

## 2. Acceptance criteria
- [ ] A trading-side `OwnerPositionDeriver` (beside `owner_inventory_deriver.py`; same inputs: tag, symbol, `run_started_at`) replays the owner's tagged fills into `OwnerPosition(quantity: signed Decimal, average_entry: Decimal | None, realized_pnl, fees)`; a closed or flipped position resets the average entry correctly (a flip's remainder enters at the flip price). Funding is **not** in it (it is a wallet event, 039G).
- [ ] The owner book for a Futures venue holds the position instead of the inventory behind the **same registration call**; the Spot book is byte-identical in behaviour (Spot journeys unchanged). Whether this is a second class (`OwnerPositionBook`) or a strategy inside `OwnerBook` is decided by the 400-line / 15-method rule (`architecture-rule.md` §5.4): `owner_book.py` is large already — prefer a second class behind one `IOwnerBook`-style port, **no `if futures`** inside `OwnerBook`.
- [ ] The budget for a Futures owner is judged in **notional and margin**: an order is refused when the resulting worst-case position notional exceeds `capital × leverage` (O2) or the bracket cap, or when initial margin exceeds the margin the owner committed. The existing caps (open orders, spacing, orders per window) apply unchanged. `OwnerBudget` gains the Futures figure as a new optional field with a default that leaves Spot judgement identical.
- [ ] **Cross-check:** on registration, on each reconcile and after a stream gap, the derived position is compared with the exchange's `positionRisk` for the symbol; a difference larger than one step is a named `POSITION_MISMATCH` the reconciler reports (never silently overwritten, never "fixed" by trusting the bot's record) — the exchange wins, the disagreement is logged at WARNING once per cause (`position_state_reconciler.py`'s rule).
- [ ] **Foreign position:** if `positionRisk` shows a non-zero position on the symbol that no tagged order of this run explains (older than `run_started_at`), registration refuses with `OwnerBudgetRefusal.FOREIGN_POSITION` (a new member), named in the user's words ("ETHUSDT already has a long position of 0.050 that this bot did not open; close it or pick another symbol"). It is **not** counted as the bot's, and it is reported like Spot's "earlier runs" (`BUG-196`): recorded, never traded.
- [ ] A fill the bot did not order (a forced close, an ADL) is detected as a position change with no tagged fill and surfaces as `POSITION_CHANGED_UNORDERED` for the guard (`039F`) — not applied silently to the book.
- [ ] Concurrency: the new book is used under the same lock discipline as `OwnerBooks` (`TradingSessionState` holds the books and calls them under its lock); the `OwnerEventBuffer` replay applies to it unchanged.
- [ ] Spot: `OwnerInventory`, `OwnerBook`, `OwnerBooks` behaviour and tests unchanged.

## 3. Design
Same shape as the Spot book on purpose (the repo's own pattern, ADR D6: derive from evidence, never supplied), so the executor can ask one question — `IExposureBook.held()` — and a Spot and a Futures answer differ only in type (`INVENTORY` quantity ≥ 0 vs signed position). Cross-checked against `positionRisk` rather than replaced by it, because `positionRisk` is account-level and cannot tell the bot's position from a foreign one (O11). The "earlier runs" idea transfers to "foreign position": what was there before, report it, never trade it.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `trading/contracts/owner_position.py` (new) | `OwnerPosition`, refusal member `FOREIGN_POSITION`, `POSITION_MISMATCH` |
| `trading/application/owner_position_deriver.py` (new), `owner_position_book.py` (new) | derive and hold |
| `trading/application/owner_books.py` | construct the right book per venue profile (one factory, not a branch inside the book) |
| `trading/contracts/owner_budget.py`, `owner_budget_registration.py` | the Futures budget field; the refusal |
| `bots/contracts/i_exposure_book.py` (new), `bots/application/services/…` adapters | `IExposureBook` for Spot (wraps the inventory) and Futures |
| `trading/application/position_state_reconciler.py` | the cross-check hook |

## 5. Testing
Tier: unit (derivation, book, budget), integration on the Futures fake of 039C (registration, mismatch, foreign position). Red-first.
- `test_a_long_then_partial_close_then_flip_derives_the_signed_position_and_entry`
- `test_the_derived_position_equals_the_fakes_position_risk_after_a_ladder_of_fills`
- `test_a_position_older_than_the_run_is_foreign_and_refuses_registration`
- `test_a_mismatch_with_position_risk_is_reported_not_overwritten`
- `test_a_fill_without_a_tag_changes_the_position_and_is_reported_as_unordered`
- `test_the_futures_budget_refuses_notional_above_capital_times_leverage` · `test_the_spot_budget_judgement_is_unchanged`
- `test_a_stream_gap_buffer_replays_uncounted_fills_into_the_position_book`
Not run yet.

## Pitfalls
- Average entry on a **reduce** does not change; on an **add** it is the weighted average; on a **flip** the remainder's entry is the flip fill's price. Property-test it against a naive replay.
- Trade ids: Futures fills carry no per-fill `trade_id` today (`order_filled_event.py`: `None` for Futures) — the dedup the Spot book uses (`EPIC-035P`) needs another key (order id + cumulative quantity); decide and record it, or the stream's second report of a fill double-counts.
- Fees: Futures fees are in the quote asset (no base-asset fee), so the Spot "net of the opening fee" sizing rule does not apply; do not copy it.
- Do not add `if venue is futures` to `OwnerBook`; the factory chooses the book (D1).

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: read `owner_book.py`, `owner_books.py`, `owner_inventory_deriver.py` and `i_trading_session.py`, and write down which method each Futures variant replaces.
