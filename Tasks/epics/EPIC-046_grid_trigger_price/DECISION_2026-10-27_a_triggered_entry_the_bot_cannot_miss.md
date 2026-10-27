# ADR — A Grid's trigger entry must not depend on the bot sampling the price at the right instant

**Epic:** [EPIC-046](README.md)
**Date:** 2026-10-27
**Status:** Accepted (O1–O6 at the author's recommendations, by the owner, 2026-10-27)
**Decided by:** the owner, 2026-10-27, in the author session: *"OK duyet"* (translated: "OK, approved"), answering the author's request to confirm O1–O6 or say "follow the recommendations"; read as accepting every recommendation below. Earlier direction from the owner, 2026-10-27, through the coordinating session: *"ket hop Đặt lệnh kích hoạt ngay trên sàn, để sàn tự bắt. Kích hoạt theo mức thấp nhất trong khoảng giữa hai lần lấy mẫu."* (translated: "combine: place the trigger order on the exchange so the exchange catches it; trigger on the lowest price between two samples"). The design below was then confirmed by the answer quoted first.
**Supersedes / superseded by (optional):** refines [ADR 046](DECISION_2026-10-22_a_grid_trigger_price.md) D2 (the price source) and D3 (the latch); supersedes nothing yet.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the code tree at `b12b95f` (`master-warrior`, 2026-10-27) |
| 🟢 User decision | decided by the owner, quoted above |
| 🔵 Proposed | the author's proposal; here accepted as a whole by the owner's answer |
| ❓ Open | blocks the named phase until answered |

## 1. Context

The report is [BUG-276](../../bug_report/incomplete/BUG-276_a_waiting_grid_with_a_trigger_price_never_sees_a_wick_that_touched_the_trigger.md): bot `ixr5v8`, LONG-style trigger `price <= 735` inside range 733–748 on `futures_mainnet`; the owner's 15m last-trade chart shows one wick to about 734.7, then the price back near 737.

**Established facts** (`b12b95f`):
- ✅ The gate is the band `[lower, trigger]` (733–735), judged on **one sampled price** (`grid_entry_gate.py` → `entry_gate`, `entry_band`).
- ✅ On a position venue the entry sees only the **mark** read over REST every 5 s (`grid_mark_exit.py` → `GridMarkExit.check`, `PriceTick.at(mark)`; `bot_price_watch.py` → `CHECK_EVERY_SECONDS`); the kline tick, which carries the low, is not offered to the entry (`grid_price_reaction.py` → `GridPriceReaction.on_tick`, `if not self._exits_on_mark`). On Spot the entry sees `tick.last` only, so the kline low is also dropped.
- ✅ A sample that opens the gate is confirmed by the fresh book price, which must still be inside the band (`grid_range_entry.py` → `GridRangeEntry._attempt`).
- ✅ The backtest enters on any candle that reaches the band (`waiting_replay.py` → `entry_band`), so it enters where the live bot can miss.
- ✅ The repository already places, records, supervises and cancels an exchange-resident conditional order for a Futures bot: the protective stop of `EPIC-039L` (`protection_futures.py`, `protective_stop_request.py`: `STOP_MARKET`, `WorkingType.MARK_PRICE`, saved client id, orphan cancel on a flat symbol), and the emergency stop cancels conditional orders of flat symbols (`futures_stop_steps.py`).
- ❓ Not verified from this checkout: which Binance endpoint carries a conditional order today (Binance has been moving conditional orders to a separate algo-order API) and whether an entry-side conditional order is accepted on the owner's account. The Futures adapter lives behind the trading port; only a testnet run settles this.

**The key finding.** The owner's direction has two parts that pull apart:
- **"Trigger on the lowest price between samples" alone cannot honour a limit.** After the wick the price is 737. Entering then buys 2 above the owner's 735 limit, which ADR 046 D1 forbids ("like a limit order"). The guard "place only if the fresh price is still inside 733–735" avoids that, but then a recovered wick, the owner's own case, still enters nothing. So this part helps only the stale-sample cases (a dip still on at the check, mark against last), not a wick that is over by the next sample.
- **Only a resting order held by the exchange honours the limit**, because the exchange sees every trade. That is the other half of the direction, and it is where the owner's case is actually fixed.

## 2. Decisions

| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **The entry is an order the exchange holds from the moment the bot starts waiting**, not a condition the bot polls. LONG: a buy at the trigger or better; SHORT: a sell at the trigger or better. | 🟢 Accepted | Owner, 2026-10-27 ("place the trigger order on the exchange") | Fixes BUG-276 for every wick; adds the first exchange-resident *opening* order, so every hazard in §6 becomes real money. |
| D2 | **Which order: a resting LIMIT at the trigger price (recommended), not a conditional market order.** The bot is waiting only while the price is on the worse side of the trigger, so a LONG buy limit at the trigger rests under the market and fills at the trigger or better, exactly the owner's "like a limit". | 🟢 Accepted | Owner, 2026-10-27 | A limit uses the order path the Grid ladder already uses (client id, tag, fills, reconcile, maker fee), no conditional-order API and no `MARK_PRICE` against last-trade mismatch (a limit fills on trades, the chart's price). A conditional market (`TAKE_PROFIT_MARKET`, `MARK_PRICE`) would fill at market after the touch, with slippage and a mark-based trigger; kept as the alternative if the testnet shows the limit cannot be the opening trade. |
| D3 | **Its size is the plan's opening trade at the trigger price**, which the Plan already computes (`entry_price` → trigger, ADR 046 D5). | 🟢 Accepted | Owner, 2026-10-27 | One sizing source; the Start checks already judge the ladder there (minimum, cap, budget). |
| D4 | **A fill is the entry.** When the order fills (fully), the bot takes `range_entered` and lays the ladder around the actual fill price, the opening trade already done. A partial fill keeps the bot waiting for the rest for a bounded time, then ends it by a rule the owner sets (O4). | 🟢 Accepted | Owner, 2026-10-27 | The start sequence gains an "opening trade already filled" input; it is the largest code change of the epic. |
| D5 | **The sampled gate stays as the fallback** for the case the order cannot be placed (venue refuses, rate limit): the bot waits on the existing rule and says so. | 🟢 Accepted | Owner, 2026-10-27 | The bot never silently has neither. |
| D6 | **The B-part, as the owner worded it ("the lowest price between two samples").** The bot keeps the lowest price seen since the last sample (the kline low from the stream, and the extremes of the mark samples) and **shows it** on the Bots screen and in the waiting words; it does **not** place anything from it. | 🟢 Accepted | Owner, 2026-10-27 | The owner sees whether the price touched the trigger and why the bot did or did not enter, with no new order behaviour. Honest limit: it explains a miss, it does not prevent one; D1 does. |
| D7 | **Phasing: D6 first (small, no venue behaviour), D1–D5 as their own epic, testnet-proven before mainnet.** | 🟢 Accepted | Owner, 2026-10-27 | Agrees with the coordinator's advice on the split; differs on what B can do (it cannot fix the owner's case alone, see §1). |

## 2a. Constitution check
The entry order is real-money behaviour, so none of D1–D7 is settled as a default; the owner decides.

| Invariant | Passes? | Evidence |
| :--- | :--- | :--- |
| P1 Mechanism over memory | ✅ | One entry gate stays the single definition; the order's price is derived from it, not copied |
| P2 Verify, don't restate | ✅ | §1 cites the tree at `b12b95f`; the exchange endpoint is marked unverified |
| P3 A copy drifts | ✅ | No second trigger rule: the order price and the sampled gate come from `grid_entry_gate.py` |
| P4 Green proves only what was tested | ✅ | Needs testnet evidence for fill, partial fill, cancel and orphan paths before mainnet (§7) |
| P5 Apply before you invent | ✅ | Reuses `EPIC-039L`'s record-then-send, supervise, orphan-cancel pattern and the Grid's own order path |
| P6 Fix the mechanism | ✅ | Replaces "sample and hope" with an exchange-held order; D6 alone would be a symptom patch |
| P7 Seam now, variant later | ✅ | `EntryGate` and the order port keep Spot and the conditional-market variant open |
| P8 Ratchets only fall | ✅ | No test weakened |
| P9 Decide alone | ✅ | Not decided alone: put to the owner |
| P10 Pyramid and units | ✅ | The examples are in quote units |
| P11 Prompt-grade artifacts | ✅ | One record, linked from the bug |
| Reversible; no real money, dependency, setting, Engine, user data or secret | ❌ real money | Orders that can open a position; hence the owner |

## 3. Alternatives considered

| Alternative | Why it lost |
| :--- | :--- |
| **Latch on a touch, then enter at the current price** (owner part 2 read literally) | Buys above the limit (737 for a 735 trigger); breaks ADR 046 D1. |
| **Touch evidence plus "fresh price still in the band"** | Safe, but a recovered wick (BUG-276) still enters nothing. |
| **Poll the mark faster / use the mark-price kline stream** | Narrows the gap, never closes it; costs weight on a venue with a reserve (`BOT-221`). |
| **Conditional market order (`TAKE_PROFIT_MARKET`, mark)** | Fills at market after the touch, mark-vs-last mismatch, an endpoint this checkout cannot verify; the limit is the plain version of the same promise. |
| **Do nothing but show the lowest price (D6 only)** | Explains the miss, repeats it. |

## 4. Open questions

| # | Question (put to the owner in Vietnamese in the author session) | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 ✅ | Resting **limit at the trigger** (D2, recommended) or a **conditional market order**? | D1 | 2026-10-27 |
| O2 ✅ | The price falls through the band and keeps falling below the range lower bound after the fill (733): the existing range exit (ADR 044 D7) would close the new position at once at a loss. Keep that rule, or hold the position and the ladder until the owner decides? Recommendation: **keep the rule, and refuse the trigger at Design if it sits closer than a stated distance to the lower bound**, so a fill and an exit cannot be one move. | D4 | 2026-10-27 |
| O3 ✅ | While the order rests, the loss cap, the trading switch and the owner budget cannot veto it on the exchange. Recommendation: **cancel the resting order the moment the trading switch goes off, the loss cap trips or an emergency stop runs** (the emergency stop already cancels conditional orders of flat symbols), and register the budget for the order's value at placement. | D1 | 2026-10-27 |
| O4 ✅ | A partial fill: wait for the rest for N minutes, then keep the partial as the opening trade and lay the ladder, or cancel the rest and lay at once? Recommendation: **cancel the rest after a short bound and lay the ladder over what filled**. | D4 | 2026-10-27 |
| O5 ✅ | Spot: the same resting limit (it reserves the quote asset while it rests). Include it in the epic, or Futures first? Recommendation: **Futures first**, Spot as the next slice of the same epic. | scope | 2026-10-27 |
| O6 ✅ | Phasing: D6 first as a small PR, D1–D5 as an epic with a testnet gate. Confirm? | D7 | 2026-10-27 |

## 5. How the order is kept (the design, if D1 is accepted)

- **Place.** On entering `AWAITING_RANGE` with a trigger and the price on the worse side: record first (client id saved), then send, as the protective stop does. The id carries the bot's tag so the order is recognisable as the bot's.
- **Keep.** On the price watch's beat the bot reads the order by its client id: standing (nothing to do), filled (take D4), cancelled or rejected by the exchange (place again, or fall back per D5, and say it). A rejection on a balance change after placement is exactly this case and must never leave the bot silent.
- **Replace / cancel.** The order is cancelled before anything else that ends the wait: Stop, halt, delete, `bot edit` of range, direction or trigger (then placed again at the new price), the loss cap, the trading switch, a symbol that stops trading. A cancel that fails halts the bot and says an entry order may still stand, never "stopped".
- **Restart.** At boot a `RECOVERING` waiting bot reads the exchange for its tagged entry order before anything else: found and matching, adopt; found and not matching, cancel; absent, place. A tagged entry order with **no bot record in the waiting state** is cancelled (an orphan would buy with no bot running), by the same sweep that cancels an orphan protective stop on a flat symbol.
- **Two processes, two accounts.** Only the writing host places or cancels; the read-only second process never does (`boot()` returns before any restore). The order lives on the account of the bot's venue configuration, so a VPS bot's order is on the VPS account's exchange side and a desktop copy of the same definition on another account holds none: the sweep is per account and per bot tag. A bot that moves host without being stopped would leave its order behind; the host-move path must cancel before it hands over. **Unestablished** and needing a read of the EPIC-045/047 host code before the epic starts.
- **Bounded life.** If the exchange supports an expiry on the order, use it as a backstop so an orphan that every other mechanism missed still dies; to verify on testnet.

## 6. Failure modes and limits

| Failure | Effect | Mitigation |
| :--- | :--- | :--- |
| App and VPS both down, order rests | The order fills with nobody managing the position | Expiry backstop; the position then has the protective stop only if one is placed with it (O2 and the stop need to be one design) |
| Order fills while the bot is halted or deleted | A position with no ladder | Cancel before halt or delete; the orphan sweep; the existing "bot holds something although it waited" refusal (`grid_range_entry.py` → `_holds_something`) stays |
| Exchange rejects at fill (margin) | Bot waits believing it is entered nowhere | Keep-step reads the order's final state; alert |
| Trigger edited while resting | Stale price | Cancel-and-replace on any change of the gate |
| Limit rests but price gaps through it | Fills better than the trigger (good) or not at all | Accepted limit semantics |

**Limits.** This design needs the order's quantity to be known at placement; a plan whose size depends on the price at entry beyond the trigger would need re-placing. A NEUTRAL grid has no trigger (ADR 046 O1), unchanged.

**Pattern names.** Limit order versus stop order; exchange-resident (server-side) order versus client-side polling; record-then-send (write-ahead intent); reconcile at startup; orphan sweep; backstop expiry (time to live).

## 7. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D6 | Slice 1 of the epic, own PR | Not started | The lowest price seen, shown; no order behaviour |
| D1–D5 | Slice 2+ of the epic, own tasks | Not started | Testnet proof (fill, partial fill, cancel, orphan sweep, the endpoint check of §1) required before any mainnet bot |
