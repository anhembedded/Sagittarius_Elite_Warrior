# BUG-195 — A resume lays its BUY, then the first SELL is refused by the exchange (`-2010`, insufficient balance) with 0.0082917 ETH derived as held

- **Reported:** 2026-10-09 (the owner, Spot Mainnet, bot `vce9z8`, resume confirmed 10:45:57, via the coordinator session)
- **Severity:** 🟡 P2 — the resume halts again; the base stays held and unsold
- **Status:** Open
- **Board:** A confirmed resume placed its BUY and the exchange then refused the first SELL for insufficient balance although trading derived 0.0082917 ETH as held; cause not established.
- **Context:** SPEC-014 (run a grid bot) → `src/modules/bots/application/services/grid_resume_sequence.py`, `grid_start_sequence.place_ladder`
- **Environment:** as BUG-194.

## Reproduction
Not yet reproduced. After BUG-194's first start: Resume proposed `5 orders from 2492.51 with 0.00829170 held`; Confirm at 10:45:57.

## Symptom
```
L1 BUY 0.0029 @ 2448.4 -> placed
WARNING limit SELL was refused by name: order_invalid [named-refusal]
L3 SELL 0.00280000 @ 2583.2 -> APIError(code=-2010): Account has insufficient balance for requested action.
STARTING -> HALTED on start_refused; L1 cancelled
```

## Root cause
Not yet established. The SELL (0.0028) is below the derived inventory (0.0082917), so the bot's own checks passed; the exchange disagreed. The code resizes SELLs to the inventory (`resized_for_inventory`), so a plan-sized SELL is not the cause. Candidates, none verified:
- ETH locked by an order that is not this bot's (the owner's manual or other-bot SELL): free ETH below 0.0028 while the account's total is not;
- the derived history counting a fill whose base the account no longer holds (moved or sold by hand between the runs);
- the halted run's ETH not being where the bot thinks (the account-wide holding was never compared with the derived inventory before the SELL).
What decides it: the account's ETH free and locked at 10:45:57 and its open orders at that time (not in the log).

## Relation to BUG-196
Checked 2026-10-09: not the same cause. BUG-196 (a new Start forgets the previous run's base) needs a new `run_started_at`, which a Resume from HALTED never stamps (`bot.py:164-166`); the 0.0082917 ETH the resume derived was its own run's. What BUG-196 does add to the candidates above: an account that holds base the bot does not track makes "free base on the account" and "inventory derived by the bot" differ in both directions, so the comparison named in the first suggested step stays necessary.

## Fix
None yet for the cause. **Mitigation (`BOT-174`):** a Resume of a halted bot is refused, before anything is queued, when the account's free base (plus the base locked in the bot's own resting SELLs, which the resume cancels) is below the SELLs its ladder lays; the refusal names both numbers and the base other orders lock. It is a guard, not the root-cause fix: the bug stays Open until the divergence it came from is established.

## Regression test
Not written. Candidate: a fake exchange whose free base is lower than the derived inventory; the resume names the shortfall instead of reporting a bare `-2010`.

## Verification
Not run.

## Suggested next steps
1. Get the owner's ETH free/locked and open orders for the time of the refusal.
2. If the candidate is confirmed, compare `BotOrderGateway.holding` (free + locked today) with the derived inventory before the ladder, and read free separately from locked.
