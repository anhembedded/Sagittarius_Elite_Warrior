# EPIC-029A — Trading can execute a bot's ladder: tagged client order ids, an owner budget, a switch event and the right id on a Spot cancel

**Status:** 🔵 Backlog
**Source:** [`PRO-006`](../../../proposal/PRO-006.md), accepted by the user on 2026-10-03
(*"Oki, duyệt"*, "OK, approved"). The design is in ADR D5–D8.
**Risk:** 🔴 — it changes the order path's safety gates (D6), the one place every order is
bounded.
**Complexity:** L — four additive seams across contracts, the execute handler, the session state,
three session handlers and the Spot parser, plus the fake exchange.
**Epic:** [EPIC-029](../README.md)
**Depends on:** the user's answers to ADR D6, O1 and O5 before the budget is merged. The tag, the
switch event and the cancel id do not wait for them.

---

## 1. Context and problem

A Grid keeps N resting LIMIT orders on one symbol. Today trading refuses the **second** one.
Every order marks its symbol as open (`trading/application/trading_session_state.py:231-236`).
`max_positions_per_symbol=1` and `min_order_interval=60s` then both refuse it
(`trading/contracts/trading_limits.py:89-94`), and on Spot nothing ever clears the mark (ADR §1.3).

A bot also cannot recognise its own orders. Ids are `SEW-` + 12 random hex characters, generated
inside trading (`trading/contracts/client_order_id.py:28-40`), and open orders are read
account-wide.

A bot learns of an Emergency Stop only by polling, because nothing is published
(`emergency_stop_result.py:49-54`).

The Spot parser reads `"c"` on every executionReport (`spot_user_data_event_parser.py:70`). Binance
documents that, on a cancel, `"c"` is the cancel request's id and `"C"` is the original order's
id. That claim is checked against Binance's documentation, not against a live payload.

## 2. Acceptance criteria

Revised after the review of PR #317 (round 1); see ADR D6, D7 and D21.

- [ ] **Tagged ids.** An `OrderRequest` with `client_order_tag="a3f9c1"` is submitted with a client
  order id matching `^SEW-a3f9c1-[0-9a-f]{10}$`.
  - Without a tag, the id still matches `^SEW-[0-9a-f]{12}$`.
  - A tag outside `^[a-z0-9]{6}$` is refused by `validate()` with a named error, and never reaches
    the exchange.
- [ ] **Registering a budget.** `register_owner_budget(owner_id, tag, created_at, budget)` and
  `clear_owner_budget(owner_id)` exist on `ITradingSession`.
  - A budget above the global caps (ADR O1) is refused, naming the cap it exceeds.
  - **The caller never supplies inventory.**
- [ ] **The inventory comes from the exchange.** On registration, trading derives the owner's
  inventory from exchange evidence:
  - the executions of orders carrying the tag since `created_at`, from order history;
  - minus their base-asset fees, from trade history, joined by the exchange order id that this task
    adds to `OrderRecord`.

  These cases are proven with the fake exchange:
  - a store that claims more inventory than the exchange shows has no effect on check 3;
  - a fee charged in the base asset is subtracted;
  - a fee charged in BNB is not.
- [ ] **The checkpoint.** Trading may persist an inventory checkpoint it computed itself, and
  re-derives only from the checkpoint onward. A checkpoint whose recorded tag or creation time does
  not match is discarded and the inventory is re-derived in full.
- [ ] **The five budget checks replace the signal limits** for a budgeted owner. One test per check
  proves it red and green:
  1. 10 LIMIT orders on one symbol, placed 250 ms apart, are accepted, and the 11th is refused by
     `max_open_orders=10` (`OWNER_BUDGET_OPEN_ORDERS`);
  2. a BUY that would take exposure (open BUY quote plus inventory at cost) above
     `max_exposure_quote` is refused (`OWNER_BUDGET_EXPOSURE`);
  3. a SELL larger than the owner's derived inventory is refused, even when the account holds more
     of the asset (`OWNER_BUDGET_SELL_EXCEEDS_INVENTORY`);
  4. two orders closer than `min_order_spacing` are refused (`OWNER_BUDGET_SPACING`);
  5. an order beyond the rate window is refused (`OWNER_BUDGET_RATE`).
- [ ] **Everyone else is unchanged.** For an owner without a budget (manual, strategy), every
  existing limit test passes unmodified.
  - `max_notional_per_order` (D21), the lease, the switch and the minimum notional still refuse a
    budgeted owner's order.
- [ ] **The book is updated before the event is published.** A Spot fill updates the owner book in
  trading's emission path **before** `OrderFilledEvent` reaches the bus. A test subscriber that
  places the counter SELL synchronously inside its handler is accepted every time. Cancels,
  expiries and partial fills update the book the same way.
- [ ] **A budget lasts one session.** Disabling or Emergency-Stopping the venue clears every
  budget and owner book. Registering again re-derives the inventory.
- [ ] **The venue's rate limits.** The O1 caps (spacing and orders per minute) are checked against
  the venue's `exchangeInfo.rateLimits` of type `ORDERS`, not only `REQUEST_WEIGHT`. The values are
  recorded in the implementation notes.
- [ ] **The switch event fires at the moment of change.** `TradingSwitchChangedEvent(venue, enabled,
  cause)` is published once per change:
  - enable → `ENABLED`, after the enable has committed;
  - disable → `DISABLED`;
  - Emergency Stop → `EMERGENCY_STOP`, **at its step 1** (the disable, `emergency_stop/handler.py:146`),
    before the cancels and sells.
- [ ] **The Spot cancel carries the original id.** A recorded Spot executionReport with
  `X=CANCELED`, `c=<cancel id>` and `C=<original id>` yields an `OrderEndedEvent` whose order
  carries the **original** id.
  - The test is red before the fix.
  - Once confirmed, the defect is filed as a `BUG-` and closed by this change.
- [ ] **The fake exchange behaves like the venue.**
  - A resting Spot LIMIT order fills when `set_last_price` crosses it, and the fill emits an
    executionReport.
  - A cancel emits `X=CANCELED` with both `c` and `C`.
  - The order book lives in a new `spot_order_book.py`, because `spot_account_state.py` is at 398
    of 400 lines.
- [ ] **Manual Spot finding.** The finding of ADR §1.3, that a manual Spot order blocks the symbol
  until trading is enabled again, is reproduced by a test and filed as a `BUG-` if confirmed. It is
  fixed here only if the fix is the same mechanism; otherwise it gets its own task.

## 3. Design

- **Tag (D5).**
  - `OrderRequest.client_order_tag: str | None = None`.
  - `generate_client_order_id(tag)` keeps a single format definition.
  - The tag reaches the generator through the preview handler (`preview_order/handler.py:102`).
  - It is validated in `validate()` and `preview()`, before any network call.
- **Owner budget (D6).** `OwnerBudget` is a frozen dataclass: `max_open_orders`,
  `max_exposure_quote`, `min_order_spacing`, `max_orders_per_window` and `window`.
  - **`OwnerBook` lives in a new `trading/application/owner_book.py`.** It holds:
    - the open orders by client order id (side, price, remaining quantity; a quote-sized market
      buy counts its `quote_quantity` until it fills);
    - the inventory (base, net of base-asset fees, with its cost);
    - the send times inside the window.

    `TradingSessionState` (304 lines) only holds the books by owner, under its existing lock
    (`BUG-088`), so it stays under the 400-line ratchet.
  - **Deriving the inventory** is a new application service, `OwnerInventoryDeriver`. It reads
    order history and trade history through the venue's account readers and filters by tag.
  - **The emission path updates the book.** The venue's event-emission path (the stream adapter's
    call into `venue_event_emitter.py`) first calls the session's `apply_fill` or `apply_end` for
    budgeted owners, and only then publishes. Trading is never a peer subscriber of its own events
    for this.
  - **The policy.** `TradingLimitPolicy.evaluate` branches on `context.owner_budget`: with a
    budget it evaluates the five checks above, and without one the existing four.
  - **Configuration.** The global caps are read with the existing limits
    (`trading/composition/adapter_bindings.py:132-165`).
- **Switch event (D7).** `TradingSwitchChangedEvent(BaseEvent)` lives in
  `trading/contracts/events/`. It is emitted by the enable handler (after commit), the disable
  handler, and the Emergency Stop handler right after its step-1 disable.
- **Spot cancel id (D8).** The parser prefers `payload["C"]` when `X == "CANCELED"` and `C` is
  non-empty.
- **Interface change.** New abstract methods on `ITradingSession` update every implementer: the
  real session, the contract test and the fake (architecture rule §2).

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `trading/contracts/order_request.py` | `client_order_tag` field |
| `trading/contracts/client_order_id.py` | the tagged format, and tag validation |
| `trading/contracts/owner_budget.py` (new) | `OwnerBudget` |
| `trading/contracts/order_record.py` | the exchange order id, for joining fees |
| `trading/contracts/i_trading_session.py` | `register_owner_budget`, `clear_owner_budget` |
| `trading/contracts/trading_limits.py` | the five new gate names |
| `trading/contracts/events/trading_switch_changed_event.py` (new) | the event |
| `trading/application/owner_book.py` (new) | the book |
| `trading/application/owner_inventory_deriver.py` (new) | inventory from exchange evidence, checkpoint |
| `trading/application/trading_session_state.py` | books by owner; cleared on disable |
| `trading/adapters/binance/venue_event_emitter.py` | apply to the book before publishing |
| `trading/adapters/binance/spot/spot_order_payload_mapper.py` | map `orderId` into `OrderRecord` |
| `trading/domain/policies/trading_limit_policy.py` | the budget branch |
| `trading/application/orders/execute_order/handler.py` | pass the budget into the context; record against the book |
| `trading/application/orders/preview_order/handler.py` | pass the tag to the generator |
| `trading/application/session/{enable_trading,disable_trading,emergency_stop}/handler.py` | emit the switch event |
| `trading/adapters/binance/spot/spot_user_data_event_parser.py` | the `C` on cancel |
| `trading/composition/adapter_bindings.py` | read the global caps |
| `src/config/app_config.json` | O1 keys, **only after the user approves** |
| `trading/contracts/testing/fake_trading_session.py`, `contract_trading_session.py` | new methods |
| `tests/sanity/fake_exchange/spot_order_book.py` (new), `spot_account_state.py`, `spot_routes.py` | LIMIT matching, and the cancel report with `C` |
| `Docs/VOCABULARY/README.md` | Owner budget, Owner book, Client order tag |

## 5. Testing

Unit tests:

- tag formatting and refusal, mutation-checked (format, length, alphabet);
- budget policy: each of the five gates red and green;
- the owner book updated on fill, partial fill and end, before publication;
- inventory derivation, including base-asset fees, BNB fees, a checkpoint mismatch, and a store that
  claims more than the exchange shows;
- that no budget leaves the existing four limits untouched, by re-running their suite unmodified;
- the parser's cancel id, with a recorded payload; red before the fix.

Integration tests with the fake exchange:

- a budgeted owner places 10 LIMIT orders;
- the fake fills one, and its commitment is released;
- the 11th is refused;
- the switch event fires on enable, disable and Emergency Stop.

Static checks and the per-commit architecture guards also run.

**Testnet:** one manual cancel on Spot Testnet, whose logged `OrderEndedEvent` names the original
id. The user runs it, as in `EPIC-028N`.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
