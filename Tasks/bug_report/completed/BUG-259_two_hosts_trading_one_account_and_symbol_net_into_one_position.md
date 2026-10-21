# BUG-259 — A start went through beside another copy of the app trading the same account and symbol

- **Reported:** 2026-10-21 (the owner, desktop bot `xvp0x7` and VPS bot `y3embt`, both futures_mainnet BNBUSDT, via the coordinator session)
- **Severity:** 🔴 P1 — real money: in one-way mode Binance nets both bots into one position, and a close-position protective stop of one closes both
- **Status:** ✅ Fixed (2026-10-21)
- **Board:** Each data root enforced one active bot per symbol only locally, and nothing read the other owner's tagged orders; a Start now refuses a symbol whose open orders carry a bot tag that no bot of this data root holds ([decision](epics/EPIC-029_bots_tab_grid_fast_track/DECISION_2026-10-21_a_start_refuses_another_owners_orders_on_its_symbol.md)).
- **Context:** SPEC run a grid bot → `src/modules/bots/` → `application/kinds/grid/start/`
- **Environment:** master-warrior at `68e1227`, Futures mainnet, two hosts with separate data roots on one account. Reproduced at the unit tier; not on a real exchange.

## Reproduction
1. Host A runs a bot on BNBUSDT (ladder orders `SEW-<A>-…` rest).
2. Host B starts a bot on BNBUSDT from its own data root.

Expected: B refuses. Actual: B starts and lays its ladder beside A's.

## Symptom
Two bots' orders and one netted position on BNBUSDT; B's close-position stop would close A's position too.

## Root cause
The only guards that touch another owner are a closed session's position check (`session_readiness.py` → `SessionReadiness.ensure_ready`, skipped as `already_open`) and the registration's `FOREIGN_POSITION` (`owner_position_registrar.py:109`, only when the bot's own derivation is flat). The registration reads the owner's orders by its own tag (`owner_resting_orders.py:42`). Nothing looked at a tag the data root does not hold, so another owner's *orders* were never seen at a Start. The gate was green because no test put a foreign tag on the account.

## Fix
`start/other_owner_orders.py` (`other_owner_tags`, `other_owner_refusal`) and `GridStartPreconditions._other_owners_refusal`: before the lease, read the symbol's open orders and refuse with `VENUE_NOT_READY` naming the tag when no bot of the store holds it; `BotRunner.start` and `BotRunner.resume` pass the store's bots; a Resume that lays a ladder (HALTED, AWAITING_RECOVERY) is asked too, a RECOVERING one is not (D5); the words are per venue (D6). Decision record above (D1–D4; O1 refuse-or-warn; O2 a running bot).

## Regression test
`tests/unit/modules/bots/application/services/test_a_start_refuses_another_owners_orders_on_its_symbol.py` — a foreign tag refuses the start, leaves no lease or session opening, and the runner leaves the bot DRAFT with no order sent; a sibling's tag and an untagged order do not refuse. Red before (`check` ran through and the runner started).

## Verification
Commit tier, `tests/unit/modules/bots` and `tests/integration/modules/bots` (5855) green locally. Not run on a real exchange.
