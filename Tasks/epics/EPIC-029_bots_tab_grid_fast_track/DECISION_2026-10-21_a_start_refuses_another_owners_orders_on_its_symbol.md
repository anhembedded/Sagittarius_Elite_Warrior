# ADR — A start refuses a symbol whose open orders carry a bot tag this data root does not hold

**Epic:** [EPIC-029](README.md)
**Date:** 2026-10-21
**Status:** Accepted (the owner may veto: O1)
**Decided by:** the author session, on the coordinator's instruction of 2026-10-21 ("decide and implement how a start must refuse, or at least loudly warn"); recorded so the owner can veto

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the code at `68e1227` |
| 🤖 Agent decision | delegated and decided under ONBOARDING §7 |
| ❓ Open | needs the owner |

## 1. Context
On 2026-10-21 the owner ran desktop bot `xvp0x7` and VPS bot `y3embt` on one Binance Futures account and one symbol (BNBUSDT), each from its own data root. ✅ Each data root enforces "one active bot per symbol" only locally (`other_active_bot.py`, `occupancy_of`). In one-way mode Binance nets both bots into one position and a close-position stop closes both.

✅ What already stood at `68e1227`: a *closed* session refuses every position of the account unless a claim explains it (`session_readiness.py` → `SessionReadiness.ensure_ready`, `position_explainer.py` → `PositionExplainer.unexplained`, BUG-250); a registration refuses a position that the bot's own fills do not explain when the bot's derivation is flat (`owner_position_registrar.py` → `OwnerPositionRegistrar.derive_and_install`, `FOREIGN_POSITION`). What stood nowhere: the other owner's **orders**. An *open* session answers `already_open` without reading; the registration reads only the bot's own tag (`owner_resting_orders.py` → `resting_orders`); and a position that nets with the bot's own is a divergence found only after it is traded on.

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | A Start **refuses** when the symbol's open orders (regular and conditional, `IAccountActivity.open_orders`) carry a bot tag (`SEW-<tag>-…`, `tag_of`) that no bot of this data root holds. It reads before the symbol is claimed, so a refusal leaves no lease and no session opening. The words name the tag, the order count and the cause (another copy of the app on the account) and the way out. | Accepted | 🤖 Agent decision | A start beside a live foreign owner cannot net into its position. A foreign owner's leftover orders (a deleted bot's) also refuse, with the tag named, until cancelled. |
| D2 | "Known to this data root" is the tag of every bot the store holds (`IBotStore.load_all`), the starting bot's included; the caller passes them (`BotRunner.start` → `GridStartPreconditions.check(venue_bots=…)`). | Accepted | 🤖 Agent decision | A RECOVERING or stopped sibling with orders left is not another owner. Trading stays free of the bots store. |
| D3 | A read that fails refuses the start (`VENUE_NOT_READY`), never passes. | Accepted | 🤖 Agent decision | The registration reads the same orders next, so a start that could not read here could not register either. |
| D4 | Untagged orders (`SEW-<12 hex>`, or a person's) are not judged. | Accepted | 🤖 Agent decision | A manual order is a person's, not a bot's. |
| D5 | A Resume from HALTED or AWAITING_RECOVERY, which proposes and lays a ladder, is asked as a Start is (`GridStartPreconditions.open_session_for_resume`); a RECOVERING bot, which only reconciles its own orders, is not. | Accepted | 🤖 Agent decision | The same netting cannot be reached by resuming a bot whose orders were cancelled when its sibling host started. |
| D6 | The check runs on Spot too: two bots of two hosts would trade one balance of the symbol's assets. The words say so ("the same balance"), not "nets into one position". | Accepted | 🤖 Agent decision | Refusing on Spot is as defensible as on Futures; the cause in the message is per venue. |

## 3. Alternatives considered
- **Warn only.** Loses: the harm is silent netting and a stop that closes the other bot's position; a WARNING after the ladder is laid is too late, and a log scan treats WARNINGs as findings the owner already ignores.
- **Judge the position instead of orders.** Loses as the only check: a flat moment has no position but its ladder is resting, and the position check already exists (`FOREIGN_POSITION`).
- **Trading holds the known tags.** Loses: `trading` would need the bots store or a registry of stopped bots; the caller already holds the store.
- **A shared lock on the account (a heartbeat both hosts reach).** Loses: needs a new mechanism and a service both hosts reach; `EPIC-029J` stays the home of a real lease across hosts.

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | Refuse (this record) or warn only? | nothing: the refusal ships; a veto reverts `GridStartPreconditions._other_owners_refusal` | 2026-10-21 |
| O2 | A *running* bot whose symbol later gains another owner's orders (the other host starts second, after this check is over). Detect in the running watch and halt or alert? Not done here: the second host's own start is the one that now refuses. | `EPIC-029J` | 2026-10-21 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1–D4 | `BUG-259` | Verified | `tests/unit/modules/bots/application/services/test_a_start_refuses_another_owners_orders_on_its_symbol.py` (red before, green after); `src/modules/bots/application/kinds/grid/start/other_owner_orders.py`, `grid_start_preconditions.py` |
