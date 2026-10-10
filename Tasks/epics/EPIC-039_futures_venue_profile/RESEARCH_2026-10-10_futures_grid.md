# RESEARCH — How Futures grid bots work, and what Binance's Futures API requires of one

**Epic:** [EPIC-039](README.md)
**Date:** 2026-10-10
**Collected by:** the session that scaffolded this epic. Every link in §1–§5 was **opened** (fetched and read); §6 lists what was only seen in search listings and is **not** relied on; §8 lists what did not render, so the implementing task reads the official page itself. Used by [`DESIGN_2026-10-10_futures_venue_profile.md`](DESIGN_2026-10-10_futures_venue_profile.md) (cited there as R1–R9, which are these section numbers).

> **Caveat.** The bot-mechanics sources are exchange/vendor help pages, not independent measurements, and they describe *their* bots (Pionex, Bitget), not Binance's grid product. The API sources are Binance's own developer documentation but several of its pages rendered only in part. Where a number or a rule matters to code, the task says **to verify** and the implementer reads the official page first.

## 1. Pionex — Futures Grid Bot (vendor help page, opened)
- **Modes.** Long opens a long position at start, buys lower and sells higher in the range; Short is the mirror; **Neutral opens no initial position**, places sells above and buys below the market, needs less margin and has "a more favorable liquidation price".
- **Initial position.** The part of the range above the current price opens a position immediately; the part below is placed as pending buys. Neutral opens none.
- **Leverage and margin.** Leverage up to 100×; the maximum adjustable leverage on a running bot depends on the current position's notional. *Extra margin* is a reserved cushion that lowers the estimated liquidation price for a long and raises it for a short; grid profits count as margin automatically.
- **Liquidation price.** An estimate, **worst case: assumes every pending order on the risk side has filled**; recalculated when leverage, margin, investment, range, funding or mark price change; liquidation is on **mark price** and cannot be reversed.
- **Trigger price.** An optional launch trigger: the bot stays pending until the market reaches it; separate from stop loss and take profit.
- **Stop loss / take profit.** When one fires the bot stops, cancels all pending orders, then closes the held position at market.
- **Funding.** Settled every 8 hours; longs pay shorts when the rate is positive and the reverse when negative; it appears in unrealized PnL. Grid profit is the sum of completed buy–sell cycles; total PnL is realized plus unrealized (floating PnL on mark price).
- **Trailing move.** Moves the range with a moving average; available on Long and Short grids, **not Neutral**; "Trail Down on a Long adds positions at lower prices, so position size and margin keep growing."
- **Listed risks.** Leverage can cause losses greater than accumulated grid profit; **when price exits the range the bot holds its maximum position and sits idle while floating losses grow and realized grid profit stops**; opposing grids only partly hedge; in a strong one-way trend the bot earns less than a manual position.
- **Meaning here:** the three directions and the "opening exposure is the difference" model (DESIGN §5); the worst-case liquidation estimate (§6); mark-price triggers (§8); out-of-range as an explicit parameter (O6); trailing and extra margin as later extension cases (§11).
- Source: https://intercom.help/pionex/en/articles/14616311-futures-grid-bot

## 2. Bitget — Futures Grid 101 (vendor academy page, opened)
- **Neutral (dual grid):** runs both sides; the user reviews the estimated liquidation prices of the long side and the short side **separately**; advanced options include trigger price, maximum and minimum exit prices, auto profit transfer and **auto margin transfer** (from the Spot account). Long/Short advanced options include a starting condition (price, RSI or BOLL), termination, TP/SL and a trailing grid.
- **Leverage and margin:** the page's text says default leverage 5× adjustable to 125×, "reserve funds" on by default as a risk buffer, and warns the estimated liquidation price "is not a guarantee": "sharp moves, partial fills, or slippage can test your margin more aggressively than projections suggest." It gives no leverage recommendation and does not cover funding.
- **Meaning here:** a Neutral plan has two liquidation estimates (DESIGN §5.3); the liquidation estimate is always labelled an estimate; a starting condition is a generic option all kinds could share (DESIGN §10).
- Source: https://www.bitget.com/academy/Futures-Grid-101

## 3. Binance — Change Position Mode (official docs, opened)
- `POST /fapi/v1/positionSide/dual`, parameter `dualSidePosition` (`"true"` = Hedge Mode, `"false"` = One-way), weight 1. It applies to **every symbol**; after the CM migration UM and CM share one setting. **Rejected if there is any open order (`-4067`) or open position (`-4068`).**
- One-way: one position per symbol, `positionSide` is `BOTH`. Hedge: long and short tracked separately; `positionSide` must be `LONG`/`SHORT` and **`reduceOnly` cannot be sent**.
- **Meaning here:** the bot never changes position mode (an account-wide setting that fails with orders open); it refuses to start unless the account is One-way, which the connection check already enforces (`HEDGE_MODE_UNSUPPORTED`). One-way plus `reduceOnly` is the combination the Long/Short counters rely on.
- Source: https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Change-Position-Mode

## 4. Binance — USDⓈ-M Futures Trade endpoints (official docs, opened; the page rendered partially)
- **New Order** `POST /fapi/v1/order`: types `LIMIT, MARKET, STOP, STOP_MARKET, TAKE_PROFIT, TAKE_PROFIT_MARKET, TRAILING_STOP_MARKET`; `positionSide` defaults to `BOTH` in One-way; **`reduceOnly` defaults to false and cannot be sent in Hedge Mode, nor with `closePosition=true`**; `timeInForce` includes `GTC, IOC, FOK, GTX, GTD, RPI` (the visible text does not define GTX as post-only — **to verify** before relying on it to avoid taker fees); `newClientOrderId` must match `^[\.A-Z\:/a-z0-9_-]{1,36}$` and be unique among open orders; `workingType` is `MARK_PRICE` or `CONTRACT_PRICE` (default contract price) for stop orders; `priceProtect` limits a stop's trigger when mark and contract price diverge.
- **closePosition** (documented under the *New Algo Order* section): closes the whole position, used with `STOP_MARKET`/`TAKE_PROFIT_MARKET`; cannot be combined with `quantity` or `reduceOnly`. The page structure suggests **conditional orders are placed through an Algo Order endpoint** now; the repository already maps it (`futures_algo_order_mapper.py`) — **to verify** the current endpoint and parameters before `039L`.
- **Modify Order** `PUT /fapi/v1/order`: only LIMIT; loses queue priority; `reduceOnly=true` on a modify is rejected with `-5047` unless the original was reduce-only.
- **Auto-Cancel All Open Orders** `POST /fapi/v1/countdownCancelAll` (weight 10): cancels a symbol's open orders when a countdown expires; repeated calls reset it; `countdownTime=0` disables it. A usable dead-man for a ladder (and a conflict with "leave orders resting" — `EPIC-038` O1).
- **Meaning here:** DESIGN §7–§8 (`reduceOnly` counters, mark-price stops, one-way only, `closePosition` for the protective stop, the countdown as an option).
- Source: https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/New-Order

## 5. The repository's own authority for the liquidation formula
`trading/contracts/liquidation_estimate.py` states Binance's one-way formula `LP = (WB + cum − side × Q × EP) ÷ (Q × MMR − side × Q)` with `WB` the isolated margin (or wallet balance for cross), `cum` the bracket's maintenance amount, `MMR` its maintenance-margin rate, `side` ±1; and states that under Cross margin it is **optimistic** because it sees one position alone, and that funding is not counted. This epic reuses it and does not re-derive it; the task that uses it (`039F`) checks the formula against the official page.

## 6. Seen in search results only — not opened, not relied on
- A third-party Binance bot guide (search summary): the Binance futures grid has direction (neutral/long/short), margin type (cross/isolated) and leverage up to 20×, and "no stop-loss or take-profit options" — a claim about Binance's *own product*, unverified.
- KuCoin's help page (the fetch was redirected and not followed): auto-add margin "not supported for neutral futures grid" appeared in a search summary only.
- A trader-forum post (search summary): a two-sided position earns funding while the rate favours it and is liquidated when it turns — community opinion, not documentation.
- An MCP-tool description (search summary): "margin type cannot be changed while a position or open order exists" for Binance Futures — consistent with Binance's position-mode rule (§3) but not confirmed for margin type; **to verify**.

## 7. Evidence from the owner's own run (2026-10-09 log)
Spot Grid `ke95g7`, ETHUSDT on `spot_mainnet`: opening buy 0.00679320 ETH, six ladder orders, then `RUNNING -> HALTED on halt (price_feed_stale: last tick 62 s ago; the limit is 60 s)` at 21:11:18, six `cancel … -> done`, and the base left held. This is the halt policy ([DESIGN §8](DESIGN_2026-10-10_futures_venue_profile.md)) that Futures cannot inherit. Also in the log at start: `gap reconcile disagrees (inventory_mismatch: saved 0 against 0.00679320 derived from the exchange); confirming with a second run` — an inventory warning the Futures exposure book must not reproduce (`039D`).

## 8. What did not render, so the implementer reads the official page
The research session could not read, from `developers.binance.com`: the **Change Initial Leverage** and **Change Margin Type** pages (the fetch returned the Trade overview), the **user-data stream** pages for `ORDER_TRADE_UPDATE` and `ACCOUNT_UPDATE` (reason types such as funding, fields such as realized profit and commission, client-order-id prefixes of forced closes), the **notional and leverage bracket** page, and anything on **funding** and **liquidation**. Each is therefore marked **to verify** in the DESIGN and is an acceptance criterion of the task that depends on it: `039C` (stream fields), `039E` (leverage and margin type), `039F` (liquidation and forced-close identification), `039G` (funding and commission), `039L` (conditional orders). The documentation index the site publishes for machines (`llms-full.txt`, linked from its home page) is a possible way to read them.

## 9. What was searched for and not found
- Binance's own help page for its **Futures Grid** product (parameters, trigger price, liquidation) — only third-party and other exchanges' pages came back.
- Any source on **Bybit's** grid bot.
- Independent measurements of grid-bot returns or liquidation rates on Futures: none; every performance statement here is a vendor's.
