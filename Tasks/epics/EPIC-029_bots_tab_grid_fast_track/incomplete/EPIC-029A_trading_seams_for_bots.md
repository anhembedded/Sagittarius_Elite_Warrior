# EPIC-029A — Trading can execute a bot's ladder: tagged client order ids, an owner budget, a switch event and the right id on a Spot cancel

**Status:** 🔵 Backlog
**Source:** [`PRO-006`](../../../proposal/PRO-006.md), accepted by the user on 2026-10-03
(*"Oki, duyệt"*, "OK, approved"). The design is in ADR D5–D8.
**Risk:** 🔴 — it changes the order path's safety gates (D6), the one place every order is
bounded.
**Complexity:** L — four additive seams across contracts, the execute handler, the session state,
three session handlers and the Spot parser, plus the fake exchange.
**Epic:** [EPIC-029](../README.md)
**Depends on:** the user's answer to ADR O1 (the global caps) before D6 is merged. The other three
seams do not wait for it.

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

- [ ] **Tagged ids.** An `OrderRequest` with `client_order_tag="a3f9c1"` is submitted with a client
  order id matching `^SEW-a3f9c1-[0-9a-f]{10}$`.
  - Without a tag, the id still matches `^SEW-[0-9a-f]{12}$`.
  - A tag outside `^[a-z0-9]{6}$` is refused by `validate()` with a named error, and never reaches
    the exchange.
- [ ] **Registering a budget.** The `register_owner_budget(owner_id, OwnerBudget)` and
  `clear_owner_budget(owner_id)` operations exist on `ITradingSession`. A budget above the global
  caps (ADR O1) is refused with the cap it exceeds.
- [ ] **The budget replaces the signal limits.** For an owner with a budget, 10 LIMIT orders on one
  symbol, placed 250 ms apart, are all accepted, and the 11th is refused by `max_open_orders=10`.
  - A BUY that would take exposure above `max_exposure_quote` is refused, naming the exposure.
    Exposure is the open BUY orders' quote plus the owner's inventory at cost.
  - A SELL larger than the owner's own inventory is refused, even when the account holds more of
    the asset. A bot never sells the user's pre-existing holdings.
  - Two orders closer together than `min_order_spacing` are refused.
- [ ] **Everyone else is unchanged.** For an owner without a budget (manual, strategy), every
  existing limit test still passes unmodified.
  - The lease, the switch, `max_notional_per_order` and the minimum notional still refuse a
    budgeted owner's order.
- [ ] **The owner book follows events.** A BUY fill moves quote from open orders into inventory,
  and a SELL fill reduces inventory at average cost. A cancel or expiry frees its open quote. This
  is proven with the fake exchange's fill and cancel events, including partial fills.
- [ ] **A budget lasts one session.** Disabling or Emergency-Stopping the venue clears every
  budget and owner book.
  - Re-registering accepts a seed of open orders and inventory.
  - An inventory seed above the account's holding of that asset is refused.
- [ ] **The venue's rate limit.** `min_order_spacing`'s cap (O1) is checked against the venue's
  `exchangeInfo.rateLimits` and recorded in the task's implementation notes.
- [ ] **Switch event.** `TradingSwitchChangedEvent(venue, enabled, cause)` is published once per
  change:
  - enable → `ENABLED`;
  - disable → `DISABLED`;
  - Emergency Stop → `EMERGENCY_STOP`, published after its cancels and sells have finished.
- [ ] **The Spot cancel carries the original id.** A recorded Spot executionReport with
  `X=CANCELED`, `c=<cancel id>` and `C=<original id>` yields an `OrderEndedEvent` whose order
  carries the **original** id.
  - The test is red before the fix.
  - Once confirmed, the defect is filed as a `BUG-` (`create-bug-report-rule.md`) and closed by this
    change.
- [ ] **The fake exchange behaves like the venue.**
  - A resting Spot LIMIT order fills when `set_last_price` crosses it, and the fill emits an
    executionReport.
  - A cancel emits `X=CANCELED` with both `c` and `C`.
- [ ] **Manual Spot finding.** The finding of ADR §1.3, that a manual Spot order blocks the symbol
  until trading is enabled again, is reproduced by a test. It is filed as a `BUG-` if confirmed.
  It is fixed here only if the fix is the same mechanism; otherwise it gets its own task.

## 3. Design

- **Tag (D5).** `OrderRequest.client_order_tag: str | None = None`.
  - `generate_client_order_id(tag)` formats the tagged id and keeps a single module-level format
    definition.
  - The tag reaches the generator through the preview handler, which is where ids are made today
    (`preview_order/handler.py:102`).
  - The tag is validated in `validate()` and `preview()`. Both refuse before any network call.
- **Owner budget (D6).** `OwnerBudget` is a frozen dataclass in `trading/contracts/` with
  `max_open_orders: int`, `max_exposure_quote: Decimal` and `min_order_spacing: timedelta`.
  - `TradingSessionState` keeps an **owner book** per budgeted owner, under the same lock as today
    (`BUG-088`). The book holds:
    - the open orders by client order id, each with side, price and remaining quantity (a
      quote-sized market buy counts its `quote_quantity` until it fills);
    - the inventory: base quantity and cost;
    - the last send time.
  - Fills are matched to the owner by client order id, recorded at submit.
  - The full signature is `register_owner_budget(owner_id, budget, seed: OwnerBookSeed | None)`.
    The seed is the open orders plus the inventory, used after a reconciliation. Disable and
    Emergency Stop clear every book.
  - `TradingLimitPolicy.evaluate` gains a branch on `context.owner_budget`: with a budget it
    evaluates the three budget checks, and without one the existing four.
  - The new gates are `OWNER_BUDGET_OPEN_ORDERS`, `OWNER_BUDGET_COMMITTED_QUOTE` and
    `OWNER_BUDGET_SPACING`. They are named, never silent, and follow `code/errors.md`.
  - Fill and end events release an order's commitment. A partial fill releases its share.
  - The global caps come from configuration (ADR O1). They are read where the existing limits are
    read (`trading/composition/adapter_bindings.py:132-165`).
- **Switch event (D7).** `TradingSwitchChangedEvent(BaseEvent)` lives in
  `trading/contracts/events/`. It is emitted from the enable, disable and Emergency Stop handlers
  through the venue's event emitter, after the state change has committed. It is never emitted
  for a refused enable.
- **Spot cancel id (D8).** The parser prefers `payload["C"]` when `X == "CANCELED"` and `C` is
  non-empty. That is the original id. Otherwise it uses `c`.
- **Interface change.** Adding abstract methods to `ITradingSession` updates every implementer: the
  real session, the contract test and the fake (architecture rule §2).

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `trading/contracts/order_request.py` | `client_order_tag` field |
| `trading/contracts/client_order_id.py` | the tagged format, and tag validation |
| `trading/contracts/owner_budget.py` (new) | the `OwnerBudget` value object |
| `trading/contracts/i_trading_session.py` | `register_owner_budget`, `clear_owner_budget` |
| `trading/contracts/trading_limits.py` | the three new gate names |
| `trading/contracts/events/trading_switch_changed_event.py` (new) | the event |
| `trading/application/trading_session_state.py` | per-owner budget book |
| `trading/domain/policies/trading_limit_policy.py` | the budget branch |
| `trading/application/orders/execute_order/handler.py` | pass the owner's budget into the context; record against the budget |
| `trading/application/orders/preview_order/handler.py` | pass the tag to the generator |
| `trading/application/session/{enable_trading,disable_trading,emergency_stop}/handler.py` | emit the switch event |
| `trading/adapters/binance/spot/spot_user_data_event_parser.py` | the `C` on cancel |
| `trading/composition/adapter_bindings.py` | read the global caps |
| `src/config/app_config.json` | O1 keys, **only after the user approves** |
| `trading/contracts/testing/fake_trading_session.py`, `contract_trading_session.py` | new methods |
| `tests/sanity/fake_exchange/spot_account_state.py`, `spot_routes.py` | LIMIT matching, and the cancel report with `C` |
| `Docs/VOCABULARY/README.md` | Owner budget, Client order tag |

## 5. Testing

Unit tests:

- tag formatting and refusal, mutation-checked (format, length, alphabet);
- budget policy: each of the four gates red and green, and the owner-book update on fill, partial
  fill and end;
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
