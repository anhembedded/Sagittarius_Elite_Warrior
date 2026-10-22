# BOT-228 — The owner checkpoints keep the ids of orders that ended after the checkpoint

**Status:** 🔵 Backlog
**Priority:** P3
**Board:** `open_order_ids` of an owner checkpoint carries an id forward until a later read sees the order end, and a later read starts at `read_from`, after the order was created, so an order that fills or is cancelled between two reads is never listed again and its id stays for good (bot `6tszoz`: 76 ids for 48 ladder orders and 1 stop).
**Source:** Coordinator session `session_016sGQHsRy729Fp4cY1cTXfu`, from the owner's `state/trading/owner_position/6tszoz.json` of 2026-10-22 00:12 (+07), BUG-264 investigation.
**Risk:** 🟡 — it is in the replay that derives a bot's position and inventory; a wrong prune would drop a fill.
**Complexity:** S — the pruning rule is one function; the proof is a replay test across two reads.
**Depends on:** None.

---

## 1. Context and problem
`checkpointed_replay.still_open_orders` returns `read_open | (carried_open - ended)`, where `ended` is built only from orders the current read lists. The read starts at `max(start.read_from, now - READ_OVERLAP)`, so an order created before that and ended since is not listed, is not in `ended`, and stays in `carried_open` for ever. The file grows by one id per fill of an order that was open at a checkpoint. It also widens `owned` (the filter that decides which trades belong to the owner), harmlessly today.

## 2. Acceptance criteria
- [ ] A test replays two reads: an order open at the first checkpoint and filled between the reads is not in the second checkpoint's `open_order_ids`, and its trades are still folded exactly once.
- [ ] No id is dropped while its order may still fill (an order the read lists as open stays).
- [ ] The decision (prune by terminal status from a targeted order read, or by the trades that completed the order) is recorded with its trade-off.

## 3. Design
Open. Candidates: read the carried ids' status by id when the window excludes them; or drop a carried id once the trades folded since show its executed quantity reached its quantity.

## 3a. Reuse
`OrderRecord`, `is_terminal`, `still_open_orders`: used. A UI need: none.
