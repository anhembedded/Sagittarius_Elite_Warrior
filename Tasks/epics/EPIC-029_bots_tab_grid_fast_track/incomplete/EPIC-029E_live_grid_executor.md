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

  The budget is `max_open_orders = grid_count + 1`, `max_exposure_quote = capital_quote`, and
  `min_order_spacing` from configuration (ADR O1).
- [ ] **Start sequence.** The bot places the opening market buy by quote quantity, then the
  ladder, in price order outward from the last price, throttled by `min_order_spacing`.
  - The bot becomes RUNNING only after every level is RESTING.
  - A refusal while starting cancels what was placed and goes to ERROR, with the refusal named.

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
- [ ] **Stop.** The bot cancels every order carrying its tag. Then, by the user's choice in the
  dialog (O3), it keeps the base or sells it at market. Then it clears the budget, releases the
  lease and becomes STOPPED.
- [ ] **Stop loss and take profit.** When a `MarketTickEvent` crosses the stop loss or the take
  profit, the bot runs Stop with *sell base* forced. The stop reason is recorded and shown.

**Emergency Stop, restart and crashes:**

- [ ] **Emergency Stop.** `TradingSwitchChangedEvent(cause=EMERGENCY_STOP)` moves the venue's bots
  to HALTED with no further order. Resuming re-plans from the current price and holdings, then
  waits for the user's confirmation (O2).
- [ ] **Disable.** `TradingSwitchChangedEvent(cause=DISABLED)` moves a RUNNING bot to HALTED with
  `TRADING_DISABLED`. Resting orders stay on the exchange, and the UI says so.
- [ ] **Restart.** A bot that was RUNNING when the app closed loads as PAUSED_RECOVERING and places
  nothing. When the user enables trading on its venue, the bot reconciles (ADR §3.3) and resumes.
  These cases are proven:
  - a fill that happened while the app was closed is applied from order history;
  - an order the bot placed but never saved is adopted by its tag;
  - a missing inventory halts the bot with `INVENTORY_MISMATCH`.
- [ ] **Crash before saving.** If the app is killed between a submit and the store write, the next
  reconciliation still finds that order by its tag. No level ends up with two orders.

**Threading:**

- [ ] **Off the websocket thread.** Every submit, cancel and store write runs on the bot's worker,
  never on the websocket thread. A test asserts the thread identity.

## 3. Design

- **The actor (D9).** Each running bot has one `BotWorker` with a single queue.
  - Event handlers subscribed in `bots/module.py`'s `boot()` filter on the venue and the tag, copy
    the event into the queue, and return at once.
  - The worker owns the `GridRuntime`: the levels, the executed quantity per order, inventory, cost
    basis, realised profit and the pending counter orders.
- **The level state machine (ADR §3.2)** lives in `bots/domain/grid/grid_levels.py`. It is shared
  with the backtest (`EPIC-029D`), so a fill means the same thing in both.
- **Persist after acting.** After every change the worker writes the runtime through the store.
  The tag (D5) is what makes write-after-submit safe: an order that was submitted but never saved
  is still found by its tag at reconciliation.
- **Throttling** uses the budget's `min_order_spacing`, with a monotonic clock injected for tests.
  There is no `sleep` in tests (`testing-rule.md`).
- **Errors.** A `submit()` that raises (`spot_trading_client.py:107-108`) is caught on the worker.
  It becomes a named fault, and the FSM moves the bot to ERROR or HALTED (`code/errors.md`). It is
  never swallowed.
- **Logging** uses `App.Bots.<id>` (`logging-rule.md`). Each order logs the level, the side, the
  price, the quantity and the client order id. There is one log line per state transition.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/grid/grid_levels.py`, `grid_runtime.py` (new) | level state machine, runtime |
| `src/modules/bots/application/services/bot_worker.py` (new) | the actor |
| `src/modules/bots/application/services/grid_executor.py` (new) | start, fill, end, pause, stop, SL/TP |
| `src/modules/bots/application/services/grid_reconciler.py` (new) | ADR §3.3 |
| `src/modules/bots/application/event_handlers/*.py` (new) | fill, end, tick, switch → queue |
| `src/modules/bots/module.py` | subscribe in `boot()`; restore bots as PAUSED_RECOVERING |
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
