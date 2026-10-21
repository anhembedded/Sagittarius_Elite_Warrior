# ADR — A Futures plan whose exit sits too close to its estimated liquidation is refused

**Epic:** [EPIC-039](README.md)
**Date:** 2026-10-21
**Status:** Proposed (waits on the owner: O1)
**Decided by:** Pending. The author's default (0.5%) is in the code so the check exists; the owner's answer decides the number. A real-money threshold is not settled by default (`ONBOARDING.md` §7)

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the code at `68e1227` |
| 🔵 Proposed | an option awaiting a decision |
| ❓ Open | needs the owner |

## 1. Context
✅ On 2026-10-21 a Futures start passed `plan risk OK LIQUIDATION_ESTIMATE` with the exit 1.51 before the estimated liquidation (0.23% of the exit at 658) (`BUG-255`). The only near-liquidation check, `STOP_LOSS_NEAR_LIQUIDATION`, is a WARNING that needs a daily ATR the Start does not pass, and a WARNING never refuses a start (`FuturesStartChecks.refusal`). A stop that close can be skipped by a gap, leaving the liquidation.

## 2. Options
| # | Option | Trade-off |
| :-- | :--- | :--- |
| A | Refuse an exit closer than **0.5%** of its price (what the code does now, `FuturesGridThresholds.min_liq_gap_ratio`) | Refuses the incident (0.23%); the one existing test fixture sits at 0.58% and passes. 0.5% of 658 is 3.29 USDT of BNB, which a fast minute can cross. |
| B | Another ratio (1%, 2%) | A larger floor protects more and refuses more plans that start today; at 7x a normal gap to liquidation is several per cent. |
| C | Tie the floor to the daily ATR | Needs the Start to read the stored daily candles (not wired); the Plan already has them. Adapts to the symbol's volatility. |
| D | Keep a WARNING only | The incident repeats: a warning at Start is not shown to anyone. |

## 3. Recommendation
Keep A for now: it is the smallest check that refuses the incident, ATR-free, and the same in the Plan and at Start. Move to C when the Start reads the daily ATR.

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | Which floor: 0.5% (A), a larger ratio (B), or ATR-tied (C)? | the merge of the pull request that adds it | 2026-10-21 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| A as a default | `BUG-255` | In progress: awaits O1 | `tests/unit/modules/bots/domain/grid/test_a_stop_too_close_to_liquidation_is_refused.py` |
