# EPIC-029E — A running Grid bot keeps its ladder on Spot through fills, cancels, stops, restarts and Emergency Stop

**Status:** 🔵 Backlog
**Source:** [`PRO-006`](../../../proposal/PRO-006.md). The user's words, 2026-10-03: *"plan đẩy
nhanh 1 bot grid để nhanh chóng giao dịch thật"* ("fast-track one Grid bot to trade for real
quickly"), and "for real" means Spot Testnet. The design is in ADR D9–D13 and §3.
**Risk:** 🔴 — this sends real orders. The failure modes are duplicated orders, a lost counter
order, a ladder resumed on a stale plan, and inventory the bot believes it has but does not.
**Complexity:** L — an actor, a level state machine, start, stop and pause sequences, stop loss
and take profit, and reconciliation.
**Epic:** [EPIC-029](../README.md)
**Depends on:** `EPIC-029A` (tag, owner budget, switch event, cancel id, fake exchange LIMIT
matching), `EPIC-029B` (entity, FSM, store) and `EPIC-029C` (plan). Also on the user's answers to
ADR O2 and O3.

---

## 1. Context and problem

ADR §1.2–§1.4 list what trading offers:

- a LIMIT GTC submit with no accepted event;
- fill events that carry only this fill's quantity, on the websocket thread;
- open orders read account-wide;
- an Emergency Stop that cancels everything and sells the inventory, and publishes nothing.

The executor must be correct under exactly that contract.

## 2. Acceptance criteria

All criteria are proven against the fake exchange (`EPIC-029A` makes resting LIMIT orders fill).

**Starting:**

- [ ] **Preconditions.** Start refuses, naming the reason, unless all of these hold:
  - the venue is a Spot venue with trading enabled;
  - the plan has no REFUSED verdict;
  - the symbol lease is claimed under the bot's id;
  - the owner budget is registered.

  The budget is:
  - `max_open_orders = grid_count + 1` (the number of levels, ADR §3.2);
  - `max_exposure_quote = capital_quote`;
  - the spacing and rate window from configuration (ADR O1).

  Trading derives the inventory; the bot never supplies it (ADR D6).
- [ ] **Start sequence.**
  1. The opening buy goes in **slices** at or below `max_notional_per_order` (ADR D21, §3.4),
     spaced by the budget.
  2. Then the ladder, outward from the last price. The level nearest the price stays EMPTY.
  3. The bot becomes RUNNING only after every other level is RESTING.

  A refusal after the opening buy cancels what was placed, then goes to **HALTED** with the refusal
  named (`start_refused`), with the inventory derived. A refusal before any order leaves the bot
  in DRAFT or STOPPED.

**Fills and cancels:**

- [ ] **A full fill flips the level.** A full fill at a BUY level places the SELL one level up, and
  a full fill at a SELL level places the BUY one level down. Exactly one counter order is placed
  per full fill, even when the fill arrives as three partial events.
- [ ] **Profit is booked once per cycle.** Realised grid profit increases by
  `(sell − buy) × qty − fees` once per completed cycle. It matches `EPIC-029C`'s per-grid profit
  for the same levels.
- [ ] **A level that ends without filling.**
  - While RUNNING, an `OrderEndedEvent` for a RESTING level (cancelled or expired from outside the
    bot) re-places it once.
  - A second end at the same level within a minute halts the bot with `LEVEL_KEEPS_ENDING`.
  - A rejection halts at once, with the exchange's reason.

**Pause and stop:**

- [ ] **Pause.** Placing stops. Fills are still recorded and no counter order is placed. Resume
  places the counter orders the pause held back, then continues.
- [ ] **Stop.** The bot cancels every order carrying its tag, then keeps the base or sells it at
  market by the user's choice in the dialog (O3).
  - It becomes STOPPED **only after a read shows zero open orders carrying its tag**
    (`stop_confirmed`). Then it clears its budget and releases the lease.
  - Before any cancel or sell, including a STOPPING retry after a switch-off, the bot re-registers
    its budget, which re-derives the inventory (ADR D6, review round 2). Without a budget its tagged
    orders are refused (`OWNER_BUDGET_MISSING`).
  - While the switch is off, cancels are refused (`cancel_order/handler.py:78`), so the bot waits
    in STOPPING and retries when trading is enabled. A test shows STOPPING survives a disable and
    an app restart.
- [ ] **ERROR can be left.** From ERROR, Stop runs the same sequence, re-registering first. ERROR
  keeps the lease until STOPPED.
- [ ] **Leases come back after a restart.** A restored bot that is not DRAFT or STOPPED reclaims its
  lease when trading is enabled (ADR D12). A manual order on its symbol is then refused again.
- [ ] **Stop loss and take profit.** When a `MarketTickEvent` crosses the stop loss or the take
  profit, the bot runs Stop with *sell base* forced. The stop reason is recorded and shown.
  - Every market exit (stop loss, take profit, Stop with *sell base*) is **sliced** at or below
    `max_notional_per_order`, spaced by the budget's `min_order_spacing` (ADR D21, §3.4).
  - A test exits 5,000 USDT of base in 10 tagged slices, 250 ms apart.
  - A refused or failed exit slice halts the bot, naming the unsold remainder.

**Emergency Stop, restart and crashes:**

- [ ] **Any switch-off halts.** `TradingSwitchChangedEvent` with `cause` DISABLED or
  EMERGENCY_STOP moves the venue's bots to HALTED, with no further order.
  - After a disable, the UI says that the resting orders are still on the exchange.
  - A submit or cancel refused with `TRADING_SWITCH_OFF` or `CONNECTION_NOT_READY` is classified
    as `switch_off`, never `fault`. A test drives the Emergency Stop race: a submit refused between
    the disable and the event leads to HALTED, not ERROR.
- [ ] **Resuming from HALTED is always safe** (ADR D13). Resume runs these steps, in order:
  1. cancel every order carrying the bot's tag;
  2. derive the inventory (D6);
  3. propose a new plan from the current price and that inventory;
  4. place nothing until the user confirms it (O2).

  These cases are proven: resuming after a disable with the old ladder still resting, and after an
  Emergency Stop that left the inventory sold, partly sold or untouched (bought before the latest
  enable, ADR §1.4). The sold case is proven **while the user also holds the asset**: the
  re-derived inventory is zero, because Emergency Stop tagged the bot's share (ADR D6, round 2).
- [ ] **Restart.** A bot that was STARTING loads as HALTED, because it may hold a half-sliced
  opening buy. A bot that was RUNNING or PAUSED when the app closed loads as RECOVERING and places
  nothing. When the user enables trading on its venue, the bot reconciles in the order of
  ADR §3.3 and returns to its prior state. These cases are proven:
  - a fill that happened while the app was closed is applied from order history, before any
    adoption;
  - an order the bot placed but never saved is adopted by its tag, and its level is not re-placed;
  - a saved inventory that differs from the derived one halts with `INVENTORY_MISMATCH`;
  - a user who holds the base asset outside the bot is **not** halted, because the check is
    holding ≥ inventory;
  - an account holding below the derived inventory halts with `HOLDING_BELOW_INVENTORY`.
- [ ] **Crash before saving.** If the app is killed between a submit and the store write, the next
  reconciliation still finds that order by its tag. No level ends up with two orders.

**Threading:**

- [ ] **Off the websocket thread.** Every submit, cancel and store write runs on the bot's worker,
  never on the websocket thread. A test asserts the thread identity.

- **D20 is checked and applied atomically (PR #318 review).** `StartBotCommandHandler` reads
  every bot, checks that none is active, then saves the transition, with no lock between the two:
  two concurrent starts could both pass. Harmless while nothing dispatches start; this task must
  make the check and the `start` transition one step, under one store lock or on the single
  dispatcher thread that owns bot commands, and test two starts racing.

## 3. Design

- **The actor (D9).** Each running bot has one `BotWorker` with a single queue.
  - Event handlers subscribed in `bots/module.py`'s `boot()` filter on the venue and the tag, copy
    the event into the queue, and return at once.
  - The worker owns the `GridRuntime`: the levels, the executed quantity per order, inventory, cost
    basis, realised profit and the pending counter orders.
- **The level lifecycle (ADR §3.2)** is declared in `bots/domain/grid/grid_level_fsm_matrix.py`.
  It has the same undeclared-transition test as the bot lifecycle (`code/quality.md` FSM cohesion).
  It is shared with the backtest (`EPIC-029D`), so a fill means the same thing in both.
- **Persist after acting.** After every change the worker writes the runtime through the store.
  The tag (D5) is what makes write-after-submit safe: an order that was submitted but never saved
  is still found by its tag at reconciliation.
- **Throttling** uses the budget's `min_order_spacing`, with a monotonic clock injected for tests.
  There is no `sleep` in tests (`testing-rule.md`).
- **Errors.** A `submit()` that raises (`spot_trading_client.py:107-108`) is caught on the worker.
  It becomes a named fault, and the FSM moves the bot to ERROR or HALTED (`code/errors.md`). It is
  never swallowed.
- **Logging** uses the logger `App.Bots.GridExecutor` (`logging-rule.md`'s
  `App.<module>.<class>`). The bot id goes in the message as a field. Each order logs the bot id,
  the level, the side, the price, the quantity and the client order id. There is one log line per
  state transition.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/grid/grid_level_fsm_matrix.py`, `grid_runtime.py` (new) | level lifecycle, runtime |
| `src/modules/bots/application/services/bot_worker.py` (new) | the actor |
| `src/modules/bots/application/services/grid_executor.py` (new) | start, fill, end, pause, stop, SL/TP |
| `src/modules/bots/application/services/grid_reconciler.py` (new) | ADR §3.3 |
| `src/modules/bots/application/event_handlers/*.py` (new) | fill, end, tick, switch → queue |
| `src/modules/bots/module.py` | subscribe in `boot()`; restore bots per ADR D12 |
| `tests/unit/modules/bots/application/**`, `tests/integration/modules/bots/**` (new) | below |

## 5. Testing

- **Unit (fake ports):**
  - every criterion above, each with a deterministic clock and queue drain;
  - partial-fill accumulation;
  - one counter order per full fill;
  - pause holds and resume releases;
  - every reconciliation branch.
- **Integration (fake exchange, `tests/integration/`):** a 6-level grid starts, two fills cycle, a
  cancel from outside is re-placed, an Emergency Stop halts, and a restart reconciles. The
  exchange's open orders are asserted against the bot's levels at each step.
- **Testnet tier** (`SEW_TESTNET_TESTS=1`, user-run): `EPIC-029H`.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
