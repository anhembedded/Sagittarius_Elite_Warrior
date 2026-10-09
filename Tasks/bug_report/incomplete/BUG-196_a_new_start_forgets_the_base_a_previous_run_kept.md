# BUG-196 — A new Start forgets the base a previous run kept: it is never sold by the ladder and never shown to the owner

- **Reported:** 2026-10-09 (the owner, Spot Mainnet, bot `vce9z8`, ETHUSDT, via the coordinator session)
- **Severity:** 🟡 P2 — real money left idle and unaccounted (about 0.0166 ETH, about 41.9 USDT on the account after two halted starts); no order is wrongly placed
- **Status:** Open
- **Board:** After Stop (keep) and a new Start, the bot trades and shows only the new run's base: the base the previous run kept stays on the account, owned by nobody and visible nowhere.
- **Context:** SPEC-014 (run a grid bot) → `src/modules/bots/` (`domain/bot.py`, `application/services/grid_housekeeping.py`) and `src/modules/trading/` (`application/owner_inventory_deriver.py`)
- **Environment:** Linux, master-warrior at `37216c6` (BUG-194's fix); observed on Spot Mainnet 2026-10-09, reproduced on the fake exchange.

## Reproduction
Integration tier, the composed app over the fake Binance server: Start a Grid bot (RUNNING, opening buy filled), Stop it with `BaseHandling.KEEP`, Start it again. Observed on the fake exchange:

| After | Account BTC (seed 10) | Bot's owner book |
| :-- | :-- | :-- |
| first Start | 10.023976 | 0.023976 |
| Stop (keep) | 10.023976 | — |
| second Start | 10.047952 | 0.023976 |

The account holds 0.047952 BTC bought by the bot; the book of the second run holds 0.023976, the second opening only. The first run's 0.023976 is nobody's.

## Symptom
Two starts, each buying an opening inventory, each ended (BUG-194 halted both, then Stop): about 0.0166 ETH stays on the account. No ladder level sells it, no screen names it.

## Root cause
By design of ADR D6 (review round 2), and stated as such in `owner_inventory_deriver.py:11-12` ("base a previous run kept is not counted, since its orders predate `run_started_at`"):
1. `Bot._next_lifecycle` stamps a new `run_started_at` on `start` from DRAFT or STOPPED (`bot.py:164-166`); a resume from HALTED keeps it.
2. `GridHousekeeping.register` (`grid_housekeeping.py:65-76`) and `GridStartPreconditions.check` (`grid_start_preconditions.py:~100`) send that instant as the registration's `run_started_at`.
3. `OwnerInventoryDeriver.derive` reads order and trade history only from it (`owner_inventory_deriver.py:121-127`), so the previous run's tagged buys are outside the read.
Nothing compares the inventory the new run starts with against what the bot's earlier runs left, so the loss is silent.

Not the cause of BUG-195: a Resume from HALTED is the same run (`run_started_at` unchanged), and the 0.0083 ETH that resume derived was its own run's. BUG-195's `-2010` needs the account's free and locked base at the time (not in the log).

## Fix
Pending the owner's decision on the product behaviour (carry the base into the next run, refuse Start, or report it); see the hand-off.

## Regression test
Not written yet; it asserts the decided behaviour on the reproduction above.

## Verification
Not run.
