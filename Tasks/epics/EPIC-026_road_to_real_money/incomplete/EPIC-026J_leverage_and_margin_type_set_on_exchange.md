# EPIC-026J — Leverage and margin type are set on the exchange when a strategy is armed, and read back before the first order

**Status:** 🔵 Backlog
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §1.2 row 3; the user (2026-09-20): *"hãy cho
lô trình để có thể giao dịch thật"*.
**Risk:** 🟡 — two new signed calls; the failure mode is an order sized for 1x on an account set
to 20x, which is what happens today.
**Complexity:** S — two adapter methods, one step in the arm handler, one read-back check.
**Epic:** [`EPIC-026`](../README.md)
**SPEC:** updates `SPEC-010` §3 (arming sets the account) — hence after `EPIC-026C`.
**Depends on:** [`EPIC-026I`](EPIC-026I_resilient_submission.md) (the `recvWindow` and
`get_order` plumbing the new calls share)

---

## 1. Context and problem

`trading.live_leverage` (`config_keys.py:130`) is read by
`calculate_live_order_quantity()` (`strategy/domain/policies/position_sizing_bridge.py:42-61`)
to size the order. `grep -rn futures_change_leverage src/` finds nothing; neither does
`futures_change_margin_type`. The exchange therefore fills at whatever leverage and margin mode
the account last had — set by hand on the web UI, or by another tool — and `LivePosition.leverage`
(`live_position.py:60`) reports that fact back without anything comparing it to the config.

## 2. Acceptance criteria

- [ ] `ITradingClient.set_leverage(symbol, leverage)` and `set_margin_type(symbol, ISOLATED)` exist
      on the port and the adapter; both are idempotent against the exchange's "no need to change"
      error code, which the translator maps to success.
- [ ] `ArmStrategyCommandHandler` calls both **before** claiming the lease, and refuses to arm
      with a named `StrategyArmResult` reason if either fails or if the read-back
      (`get_positions(symbol)[0].leverage`, `margin_type`) disagrees with what was requested.
- [ ] Margin type is `ISOLATED` for every armed symbol (a user decision to record: cross margin
      lets one symbol's loss consume the whole balance; if the user wants cross, this criterion
      changes and says why).
- [ ] The venue banner shows the effective leverage of the armed symbol, read from the exchange,
      not from config.

## 3. Design

The calls are part of arming because that is the moment a symbol becomes the strategy's
(`SPEC-010` §3); enabling trading is account-wide and must not touch per-symbol settings.
Read-back is the same "truth from the exchange, not from the request" rule the ADR applies to
orders (`EPIC-021` ADR §4). The two calls go through `FuturesTradingClient` so the two-file
`LIVE` guard is unaffected (they are not order submissions and do not need the `LIVE` mode).

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/modules/trading/contracts/i_trading_client.py` | Two methods |
| `src/modules/trading/adapters/binance/futures_trading_client.py` | Implementations; idempotent on "no change" |
| `src/modules/trading/adapters/binance/binance_error_translator.py` | `-4046`-class "no need to change" → success |
| `src/modules/strategy/application/use_cases/arm_strategy/handler.py` | Set, read back, refuse on mismatch |
| `src/modules/strategy/contracts/strategy_arm_result.py` | New refusal reason |
| `tests/sanity/binance_fake_server.py` | Leverage and margin endpoints |
| `tests/unit/modules/strategy/application/use_cases/test_arm_strategy.py` | Set before lease; mismatch refuses |
| `tests/unit/modules/trading/contracts/test_trading_client_contract.py` | Both implementations |
| `Docs/SPEC/SPEC-010_….md` | §3, §5 rows |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Order of steps | `test_arm_strategy.py` | unit | set → read back → lease; a failure leaves no lease |
| Idempotent | contract suite with the fake's "no change" answer | unit + integration | success |
| Read-back mismatch | unit | unit | named refusal |
| Testnet | `tests/testnet/` opt-in: arm, `exchange-status` shows the leverage | human | recorded here |

Not run yet.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
