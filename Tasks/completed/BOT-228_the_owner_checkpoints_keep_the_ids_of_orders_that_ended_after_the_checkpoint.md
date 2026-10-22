# BOT-228 — The owner checkpoints keep the ids of orders that ended after the checkpoint

**Status:** ✅ Done (2026-10-22)
**Board:** A carried order id left the owner checkpoint only when a later read listed the order ended, and that read starts after the order was created, so a filled order stayed for good (bot `6tszoz`: 76 ids for 49 live orders); each carried id now keeps what it still owes to fill and goes when the fills a read folded for it reach that, never on a guess.
**Source:** Coordinator session `session_016sGQHsRy729Fp4cY1cTXfu`, from the owner's `state/trading/owner_position/6tszoz.json` of 2026-10-22 00:12 (+07), BUG-264 investigation.
**Risk:** 🟡 — it is in the replay that derives a bot's position and inventory; a wrong prune would drop a fill.
**Complexity:** S — the pruning rule is one function; the proof is a replay test across two reads.
**Depends on:** None.

---

## 1. Context and problem
`checkpointed_replay.still_open_orders` returns `read_open | (carried_open - ended)`, where `ended` is built only from orders the current read lists. The read starts at `max(start.read_from, now - READ_OVERLAP)`, so an order created before that and ended since is not listed, is not in `ended`, and stays in `carried_open` for ever. The file grows by one id per fill of an order that was open at a checkpoint. It also widens `owned` (the filter that decides which trades belong to the owner), harmlessly today.

## 2. Acceptance criteria
- [x] A test replays two reads: an order open at the first checkpoint and filled between the reads is not in the second checkpoint's `open_order_ids`, and its trades are still folded exactly once.
- [x] No id is dropped while its order may still fill (an order the read lists as open stays).
- [x] The decision (prune by terminal status from a targeted order read, or by the trades that completed the order) is recorded with its trade-off.

## 3. Design
**Decision: prune by the trades that completed the order.** The checkpoint carries, beside each open id, what that order still owes to fill (`open_order_remaining`: the order's quantity when a read first lists it, less the owner's counted fills of it). A read subtracts the fills it folds for the id (`checkpointed_replay.still_open_orders`) and drops the id when nothing is owed. It is done at the mechanism that builds the next checkpoint, with no sweep.

| Option | Cost | Risk | Verdict |
| :--- | :--- | :--- | :--- |
| Read each carried order's status by id | a new method on `IAccountHistoryReader` and its five implementers, the Futures session client and one request per live order (49 on `6tszoz`) at every derivation | none for correctness, but weight on every registration | Rejected: the weight buys what the fills already say |
| **Drop an id when the counted fills reach its quantity** | one stored figure per id, no exchange read | a premature drop is impossible: counted fills never exceed what the order executed | **Chosen** |
| Widen the order window back to the oldest carried order | up to 30 daily Spot requests per derivation | none | Rejected: it undoes what the checkpoint is for |

**Price paid (a test locks it):** an order cancelled with nothing filled leaves no fill to say it ended, so its id stays until the run's checkpoint is discarded; a Grid cancels at a rung drop or a stop, where it fills all day. An id an older checkpoint carried has no figure and stays too, and so does an order that reports a quantity of zero: the Futures protective stop is a `closePosition` order with no quantity, so no figure could say it is done (found in the review of PR 720; a test locks it). so the owner's current `6tszoz` file keeps its 76 until that run ends; its new ids prune.

## 3a. Reuse
`OrderRecord`, `is_terminal`, `still_open_orders`: used. A UI need: none.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/application/checkpointed_replay.py` | `ReplayStart`/`Replayed` carry `open_order_remaining`; the loop sums the fills it folds per order; `still_open_orders` returns `StillOpen` and drops an order nothing is owed on |
| `src/modules/trading/contracts/i_owner_inventory_checkpoints.py`, `i_owner_position_checkpoints.py` | the checkpoint gains `open_order_remaining` (default empty) |
| `src/modules/trading/adapters/persistence/json_owner_inventory_checkpoints.py`, `json_owner_position_checkpoints.py` | the field is stored as `open_order_remaining` and read back with a default for an older file |
| `src/modules/trading/application/owner_inventory_deriver.py`, `owner_position_deriver.py` | pass the figures into the replay and into the saved checkpoint |

## 5. Testing
`tests/unit/modules/trading/application/test_a_checkpoint_forgets_the_orders_their_fills_completed.py` (unit): ten resting orders, seven filled between two reads, the second read lists none of them: the checkpoint holds the other three and the seven fills are folded once (red before: all ten stayed); a half-filled order stays with its half and goes when the rest is filled, the half read twice counted once; an order with no fill stays; an id with no figure stays; the figures survive the file. Trading unit tier, `tests/integration/application` and `tests/unit/architecture` pass.

## 6. Docs touched
none, because `trading` has no `Docs/MODULES/trading/` folder.

## Implementation notes
The Futures deriver shares the loop, so one change covers both venues. Not verified: a derivation over the real exchange; the full gate is GitHub Actions'.
