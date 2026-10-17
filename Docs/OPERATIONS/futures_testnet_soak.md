Status: Current

# Futures testnet soak and checks T1–T5 (optional runbook)

`EPIC-039L`. Futures mainnet is open to bots; the owner decided on 2026-10-17 (O2) that nothing in the code waits for this runbook and that they manage the risk. Following it is how the owner learns what the fake exchange cannot tell them. It is run on **Futures testnet only**; never place or test an order on mainnet for it. Design and the questions behind each check: [`DECISION_2026-10-16_futures_protective_stop_minimum.md`](../../Tasks/epics/EPIC-039_futures_venue_profile/DECISION_2026-10-16_futures_protective_stop_minimum.md) §6.

## 1. The 14-day soak

1. Start one Futures Grid bot on Futures testnet with a stop loss set, and leave the app (or `run`) up for 14 days.
2. Read the log file (never scrollback) for `FAILED|ERROR|Traceback|ResourceWarning` and for `[protective-stop]` lines.
3. A pass is: no unexplained halt; every halt that closed a position says why; a protective stop stands whenever a position is open (the `[protective-stop]` lines and the exchange's open conditional orders agree); the count of divergences the app reported against fills the bot ordered is zero (T5).

## 2. The checks

| # | Check, on testnet | What the answer decides |
| :-- | :--- | :--- |
| T1 | Is a `STOP_MARKET closePosition=true` rejected when there is no position? Which error code? | How early the start learns a stop could not stand |
| T2 | Does a `closePosition` stop survive the position passing through zero and stay `NEW`, or become `EXPIRED`? | How often the stop is re-armed |
| T3 | A triggered `closePosition` BUY stop while long (and the reverse): nothing, or a new position? | Only then `NEUTRAL_BOTH_SIDES_VERIFIED` may become true; until then Neutral is not counted as protected |
| T4 | Is a trigger already beyond the mark rejected, with what code and words? | The start's wording when the stop cannot be placed |
| T5 | `ORDER_TRADE_UPDATE` vs `ACCOUNT_UPDATE` for one trade (single fills and a burst), and a triggered stop's order update vs `ALGO_UPDATE` | `POSITION_CHANGED_UNORDERED` and foreign-fill detection rest on it |

Record each answer in the decision record's §6, with the date.
