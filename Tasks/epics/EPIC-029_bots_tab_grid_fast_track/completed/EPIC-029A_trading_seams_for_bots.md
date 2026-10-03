# EPIC-029A — Trading can execute a bot's ladder: tagged client order ids, an owner budget, a switch event and the right id on a Spot cancel

**Status:** ✅ Done (2026-10-03)
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

- [x] **Tagged ids.** An `OrderRequest` with `client_order_tag="a3f9c1"` is submitted with a client
  order id matching `^SEW-a3f9c1-[0-9a-f]{10}$`.
  - Without a tag, the id still matches `^SEW-[0-9a-f]{12}$`.
  - A tag outside `^[a-z0-9]{6}$` is refused by `validate()` with a named error, and never reaches
    the exchange.
- [x] **Registering a budget.** `register_owner_budget(owner_id, tag, run_started_at, budget)` and
  `clear_owner_budget(owner_id)` exist on `ITradingSession`.
  - A budget above the global caps (ADR O1) is refused, naming the cap it exceeds.
  - **The caller never supplies inventory.**
- [x] **The inventory comes from the exchange.** On registration, trading derives the owner's
  inventory from exchange evidence:
  - the executions of orders carrying the tag since `run_started_at` (the bot's current run, ADR D6
    r2), from order history;
  - minus their base-asset fees, from trade history, joined by the exchange order id that this task
    adds to `OrderRecord`.

  These cases are proven with the fake exchange:
  - a store that claims more inventory than the exchange shows has no effect on check 3;
  - a fee charged in the base asset is subtracted;
  - a fee charged in BNB is not;
  - base kept by a previous run (Stop with *keep base*) is not counted by a new run.
- [x] **The checkpoint.** Trading may persist an inventory checkpoint it computed itself, and
  re-derives only from the checkpoint onward. A checkpoint whose recorded tag or creation time does
  not match is discarded and the inventory is re-derived in full.
- [x] **The five budget checks replace the signal limits** for a budgeted owner. One test per check
  proves it red and green:
  1. 10 LIMIT orders on one symbol, placed 250 ms apart, are accepted, and the 11th is refused by
     `max_open_orders=10` (`OWNER_BUDGET_OPEN_ORDERS`);
  2. a BUY that would take exposure (open BUY quote plus inventory at cost) above
     `max_exposure_quote` is refused (`OWNER_BUDGET_EXPOSURE`);
  3. a SELL larger than the owner's derived inventory is refused, even when the account holds more
     of the asset (`OWNER_BUDGET_SELL_EXCEEDS_INVENTORY`);
  4. two orders closer than `min_order_spacing` are refused (`OWNER_BUDGET_SPACING`);
  5. an order beyond the rate window is refused (`OWNER_BUDGET_RATE`).

  The five checks run **whatever the order's `purpose`**: a Spot SELL marked CLOSE beyond the
  inventory is refused by check 3, because the budget branch runs before the `only_reduces` return
  (`trading_limit_policy.py:51-55`).
- [x] **A tagged order needs a budget.** Any order carrying a `client_order_tag` with no budget
  registered for that tag is refused with `OWNER_BUDGET_MISSING`. This holds after a disable has
  cleared the budgets, too.
- [x] **Everyone else is unchanged.** For an owner without a budget (manual, strategy), every
  existing limit test passes unmodified.
  - `max_notional_per_order` (D21), the lease, the switch and the minimum notional still refuse a
    budgeted owner's order.
- [x] **The book is updated before the event is published.** A Spot fill updates the owner book in
  trading's emission path **before** `OrderFilledEvent` reaches the bus. A test subscriber that
  places the counter SELL synchronously inside its handler is accepted every time. Cancels,
  expiries and partial fills update the book the same way.
- [x] **A budget lasts one session.** Disabling or Emergency-Stopping the venue clears every
  budget and owner book. Registering again re-derives the inventory.
- [x] **Emergency Stop tags the coins it sells for a bot.** Emergency Stop takes a snapshot of the
  owner books before its step-1 clear. It splits each asset's liquidation per budgeted owner: each
  share, up to that owner's inventory, carries the owner's tag, and only the surplus beyond every
  bot's inventory is untagged.
  - Case proven: an Emergency Stop in the session that bought the inventory, **while the user also
    holds the asset**, leaves a re-derived inventory of zero for the bot. The user's coins are
    untouched.
- [ ] **The venue's rate limits.** *(Not verified: Binance is unreachable from the build container; see the implementation notes. Handed to `029H`.)* The O1 caps (spacing and orders per minute) are checked against
  the venue's `exchangeInfo.rateLimits` of type `ORDERS`, not only `REQUEST_WEIGHT`. The values are
  recorded in the implementation notes.
- [x] **The switch event fires at the moment of change.** `TradingSwitchChangedEvent(venue, enabled,
  cause)` is published once per change:
  - enable → `ENABLED`, after the enable has committed;
  - disable → `DISABLED`;
  - Emergency Stop → `EMERGENCY_STOP`, **at its step 1** (the disable, `emergency_stop/handler.py:146`),
    before the cancels and sells.
- [x] **The Spot cancel carries the original id.** A recorded Spot executionReport with
  `X=CANCELED`, `c=<cancel id>` and `C=<original id>` yields an `OrderEndedEvent` whose order
  carries the **original** id.
  - The test is red before the fix.
  - Once confirmed, the defect is filed as a `BUG-` and closed by this change.
- [x] **The fake exchange behaves like the venue.**
  - A resting Spot LIMIT order fills when `set_last_price` crosses it, and the fill emits an
    executionReport.
  - A cancel emits `X=CANCELED` with both `c` and `C`.
  - The order book lives in a new `spot_order_book.py`, because `spot_account_state.py` is at 398
    of 400 lines.
- [x] **Manual Spot finding.** The finding of ADR §1.3, that a manual Spot order blocks the symbol
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
| `trading/contracts/trading_limits.py` | the six new gate names (five checks plus `OWNER_BUDGET_MISSING`) |
| `trading/contracts/events/trading_switch_changed_event.py` (new) | the event |
| `trading/application/owner_book.py` (new) | the book |
| `trading/application/owner_inventory_deriver.py` (new) | inventory from exchange evidence, checkpoint |
| `trading/application/trading_session_state.py` | books by owner; cleared on disable |
| `trading/adapters/binance/venue_event_emitter.py` | apply to the book before publishing |
| `trading/adapters/binance/spot/spot_history_payload_mapper.py` | map `orderId` into `OrderRecord` (the Spot history mapper, not the order-payload mapper) |
| `trading/adapters/binance/futures_history_payload_mapper.py`, `futures_algo_order_mapper.py`, `trading/contracts/testing/contract_account_history_reader.py`, `trading/ui/desk/account_tabs/preview.py` | every other `OrderRecord(...)` constructor gains the field; no default is used, so a missing one fails loudly (`BUG-026`) |
| `trading/application/session/emergency_stop/handler.py` | snapshot the books before the clear; tag each owner's liquidation share |
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
- budget policy: each of the five gates red and green, a CLOSE-purpose Spot SELL beyond inventory
  refused, and `OWNER_BUDGET_MISSING` for a tagged order with no budget;
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

Eight commits on `claude/wizardly-cerf-fc5b5x`, in the order the design builds:

| Commit | What it delivered |
| :--- | :--- |
| `feat(trading): carry a bot's tag in the client order id` | D5. `generate_client_order_id(tag)` keeps one format definition (`SEW-{tag6}-{hex10}`, untagged `SEW-{hex12}`); `tag_of()` reads it back. A malformed tag is refused when `OrderRequest`/`PreviewOrderQuery` is built (`InvalidClientOrderTagError`), so it never reaches the exchange. |
| `fix(bug-141): read a cancelled Spot order's own id from "C"` | D8, filed and closed as [`BUG-141`](../../../bug_report/completed/BUG-141_spot_cancel_report_names_the_cancel_request.md); red test first. |
| `feat(trading): publish TradingSwitchChangedEvent …` | D7. The three session handlers take an `IEventPublisher`. Emergency Stop publishes inside step 1, after the disable and before any order is read, and also when trading was already off (it still cancels and sells); a disable that raised publishes nothing. |
| `feat(trading): owner budget contracts, owner book and the budget checks` | D6 part 1: `OwnerBudget`, `OwnerBudgetCaps` (O1), `OwnerBudgetFacts`; the six new `TradingLimitViolation` names; the policy's budget branch (notional cap plus the five checks, or `OWNER_BUDGET_MISSING`), before the `only_reduces` return. |
| `feat(trading): derive an owner's inventory from the venue's history` | D6 part 2: `OrderRecord.exchange_order_id` on every constructor (no default); one inventory formula (`owner_inventory_policy.py`) shared by the book and the deriver; `OwnerInventoryDeriver` with a JSON checkpoint per tag. |
| `feat(trading): register owner budgets and judge tagged orders by them` | D6 part 3: `register_owner_budget`/`clear_owner_budget` on the port, service, fake and contract suite; `RegisterOwnerBudgetCommandHandler`; `OwnerBooks` held by `TradingSessionState` and cleared on every enable and disable; the execute path; the three O1 keys. |
| `feat(trading): update owner books before publishing, tag a bot's liquidation` | D6 part 4: `VenueEventEmitter` applies fills and ends to the books before emitting; Emergency Stop splits each Spot sale per bot (`split_liquidation`). |
| `test(epic-029a): …` | The fake exchange's LIMIT matching (`spot_order_book.py`) and cancel report with `c` and `C`; the integration tests; `BUG-142`; vocabulary, HLD and boards. |

**Departures from the task text, each for a reason:**

- **The registration is one object**, `OwnerBudgetRegistration(owner_id, tag, symbol, run_started_at, budget)`, not four arguments (`code/quality.md` §7). It also names the **symbol**: the inventory is read from that symbol's history, and taking it from the lease instead would have made the derivation depend on an unrelated call order.
- **Budgets are Spot-only for now** (`VENUE_NOT_SPOT`): only Spot has an inventory to bound. A Futures owner is a recorded extension case in `owner_budget.py` (a position instead of an inventory, behind the same registration).
- **A registration is refused while trading is off** (`TRADING_SWITCH_OFF`), and a disable that lands during its history reads wins (`switch_epoch`): "a budget lasts one session" holds at both ends.
- **Registration also adopts the owner's resting orders** from the venue's open orders, so a reconciliation after a restart starts from what is really open; the task named only the inventory.
- **`OwnerBooks` is its own class** with its own lock, rather than more methods on `TradingSessionState` (now 340 lines): the book is reached from the order pool, the websocket thread and the session handlers.
- **A budgeted order does not touch the signal bookkeeping** (no symbol marked open, no session count), so a bot's ladder never blocks a manual order on another symbol, nor the reverse.
- **On Spot, `ExecuteOrderCommand` already refuses a reducing purpose**, so a "Spot SELL marked CLOSE" cannot be built; the policy's budget branch still runs first, which the policy test proves, and which matters for any future venue with reduce-only.
- **`repo_root()` moved to `core/repo_root.py`** so `trading` (checkpoints) and `bots` (store) share it.

**The venue's ORDERS rate limits — not verified live.** The build container cannot reach Binance (`Service unavailable from a restricted location`), so `exchangeInfo.rateLimits` was not read. Binance's Spot API documentation states an `ORDERS` limit per 10 seconds and per day per account, and a `MAX_NUM_ORDERS` filter of 200 per symbol. The approved caps give one bot at most 40 orders per 10 seconds by spacing (250 ms) and 10 per 10 seconds by rate (60 per minute), and 100 open orders, under the 200 per symbol. **Several bots on one account share the account's `ORDERS` limit, and the caps are per budget, not per account**: that sum is not bounded by this task. The user should read the live values on Spot Testnet (`029H`) and decide whether an account-wide cap is needed.

**Verification.** Every commit: `ci-local.ps1 -SkipTests` PASS with the log grepped, architecture guards, and the touched tests; the last full local run of unit and integration was 7813 passed, 4 skipped (before this commit's integration tests). New tests: the tag (format, refusals), the parser's cancel id (red before), the switch event per handler, the policy's five checks at and past each ceiling, the owner book, the inventory policy through the book and the deriver (base-asset fee, BNB fee, a previous run's base, a checkpoint, a checkpoint of another run, a run past the lookback), the registration handler's refusals and its race with a disable, the execute path (ten then the eleventh, inventory, spacing, a missing budget, another owner's tag, a disable clearing it), the emission order (a mutation run, apply after emit, turned two tests red), the liquidation split, and against the fake exchange: a ladder of ten with the eleventh refused and a fill freeing a slot, a counter sell up to the inventory net of the fee, a cancel reaching the book and the bus under the order's own id, a registration deriving the inventory from the fake's history, and an Emergency Stop leaving a derived inventory of zero and the user's 10 BTC in place. The full gate is GitHub Actions' `ci-local.ps1 -Full` on the pull request.

**Not verified:** the Spot Testnet manual cancel whose logged `OrderEndedEvent` names the original id (the user runs it, as in `EPIC-028N`), and the live `ORDERS` rate limits above.

**Manual Spot finding (ADR §1.3):** reproduced and filed as [`BUG-142`](../../../bug_report/incomplete/BUG-142_manual_spot_order_blocks_its_symbol_until_re_enable.md). It is the signal limits' position bookkeeping on Spot, not the owner budget, so per this task it is not fixed here.
