# EPIC-027M — Enable trading, Emergency Stop and the session limits mean the right thing on Spot

**Status:** 🔵 Backlog
**Source:** follows the user's *"giao dịch spot"* request, 2026-09-26.
**Risk:** 🔴 — Emergency Stop is the last line of defense; a Spot version that leaves a holding behind is a silent failure.
**Complexity:** M — three handlers get a Spot branch through the market type, not through `if` chains.
**Epic (optional):** [EPIC-027](../README.md)
**Depends on:** [EPIC-027K](EPIC-027K_spot_trading_client_and_order_path.md), [EPIC-027L](EPIC-027L_spot_user_data_stream.md)

---

## 1. Context and problem
- Enable trading refuses to start when any position exists: "foreign positions refused"
  (`application/session/enable_trading/handler.py:119-127`). On Spot, holding assets is normal and
  says nothing about whether the app opened them.
- Emergency Stop closes with a MARKET order, `reduce_only=True`, on the opposite side
  (`application/session/emergency_stop/handler.py:193-202`). On Spot, "close" means selling the base
  holding. The quantity must be floored to the lot step, and the fee may already have been taken in
  the base asset.
- The session limits are USDT-notional (`src/config/config_keys.py:91`). That works for USDT-quoted
  pairs (ADR D9).

## 2. Acceptance criteria
- [ ] Enabling on Spot records the starting holdings as a baseline. It does not refuse because assets
      are present. What the app then trades is measured against that baseline.
- [ ] Emergency Stop on Spot: disable → cancel all open orders → sell the base holding of the armed
      symbol down to what the baseline held, floored to the lot step. A dust remainder below
      `MARKET_LOT_SIZE`/`NOTIONAL` is reported, not retried forever.
- [ ] Emergency Stop never sells assets the baseline held before enabling, and a test proves it.
      Selling the user's long-term holdings would be the worst possible failure.
- [ ] The four session limits apply to Spot orders unchanged, in USDT.

## 3. Design
- The baseline is the Spot analogue of "foreign positions refused". The app owns only the difference
  it created. It is written in the ADR before coding, because it decides what Emergency Stop may sell.
- Strategy pattern keyed by the venue's `market_type` inside each handler's close/reconcile step, not
  scattered `if market == SPOT` lines (`code/quality.md` §3).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/application/session/enable_trading/handler.py` | Spot baseline instead of refusal |
| `src/modules/trading/application/session/emergency_stop/handler.py` | Spot close = sell the owned difference |
| `src/modules/trading/domain/policies/` | a baseline policy (new) |
| `Docs/SPEC/` | the Emergency Stop SPEC gains a Spot section (with `EPIC-026B`'s SPEC-007) |

## 5. Testing
- Unit: baseline arithmetic, dust, never selling below the baseline.
- Integration: fake exchange with a pre-existing holding; Emergency Stop leaves it intact.
- Not run yet.
