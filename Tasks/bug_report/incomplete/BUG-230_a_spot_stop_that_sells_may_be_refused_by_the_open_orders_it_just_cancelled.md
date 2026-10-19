# BUG-230 — A Spot bot's stop that sells its base may be refused by the open orders it just cancelled

- **Reported:** 2026-10-19 (author session of BUG-228, by reading the code)
- **Severity:** 🟡 P2. Same refusal as BUG-228 on Spot, where it halts the bot with the base unsold (no leveraged risk).
- **Status:** Open
- **Board:** Suspected, not reproduced: a Spot stop's market sells are ordinary entries to the owner budget, which can count the just-cancelled ladder when it is registered again.
- **Context:** `bots` → `application/services/positions/closer_spot.py` (`market_sell`) → `trading` → `domain/policies/trading_limit_policy.py`
- **Environment:** Code at `159fbfd`; not run.

## Reproduction
Not yet reproduced. The fake Spot exchange has no lagging open-orders list (BUG-228 added one for Futures only).

## Symptom
None observed on Spot.

## Root cause
Not yet established. By reading: `BotOrderGateway.market_sell` sends purpose ENTRY; a Spot order cannot be a CLOSE (`ExecuteOrderCommand.__post_init__` refuses it where the exchange has no reduce-only), so `_owner_budget_checks` applies the open-order count to the sell slices.

## Suggested next steps
Decide whether the Spot close needs its own exemption from the count (the inventory check already bounds what a sell can do) or whether the registration should not re-adopt orders the stop has just cancelled; reproduce with a lagging list on the fake Spot exchange first. Owner decision: a change to a trading limit.
