# EPIC-026Q — Mainnet has its own caps with a hard ceiling, and enabling trading on it requires a typed acknowledgement

**Status:** 🔵 Backlog
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §4; ADR D5 and `❓ O3`; the user
(2026-09-20): *"hãy cho lô trình để có thể giao dịch thật"*.
**Risk:** 🔴 — the limits that bound the first real loss; a cap read from the wrong venue's
configuration is a cap of 500 USDT on Testnet applied to real money.
**Complexity:** M — a second limit set keyed by venue, a ceiling that configuration cannot raise,
one dialog.
**Epic:** [`EPIC-026`](../README.md)
**SPEC:** updates `SPEC-004` §3 step 1 and §5, `SPEC-005` §3 step 6.
**Depends on:** [`EPIC-026P`](EPIC-026P_mainnet_venue_member_and_factory_parameter.md); `O3`
answered (the values are the user's).

---

## 1. Context and problem

`TradingLimits` are four numbers from `app_config.json` (`config_keys.py:83-92`) with Testnet
defaults chosen for a 15 000 USDT play balance (`live_trading_coordinator.py`, the `BUG-084`
comment). The breaker's two limits (`EPIC-026L`) are the same shape. On mainnet those numbers
must be smaller and must not be raisable by editing a JSON file past a ceiling the code owns —
the same reasoning that put the mainnet lock in a type rather than a flag (`EPIC-021` ADR §3).
Enabling is one click (`trading_presenter.py:629`); on mainnet one click is too little.

## 2. Acceptance criteria

- [ ] `TradingLimits` and the breaker limits are resolved **per venue**: `trading.limits.testnet.*`
      and `trading.limits.mainnet.*`; a missing mainnet block refuses to enable on mainnet with a
      named reason rather than falling back to Testnet's values.
- [ ] `MAINNET_CEILINGS` (a frozen constant in `trading/domain/policies/`) bounds every mainnet
      limit: a configured value above the ceiling is clamped **and** logged at `WARNING` under
      `App.TradingLimits` at boot, so the run-log scan shows it. The ceiling values are the user's
      (`O3`), quoted in the ADR.
- [ ] On mainnet, `EnableTradingCommand` carries an `acknowledgement: str` that must equal the
      venue's display name typed by the operator; the Trading screen's toggle opens a modal
      dialog asking for it, showing the mainnet limits and the account's balance; the CLI's
      enable path (`trade-once --live`) requires `--acknowledge-mainnet <name>`.
- [ ] The mainnet limits and the breaker values are shown on the Trading screen at all times
      next to the venue banner.
- [ ] Leverage on mainnet is capped by `MAINNET_CEILINGS.max_leverage`, enforced in
      `EPIC-026J`'s arm step (the exchange is asked for at most that).

## 3. Design

Defence in depth on the one path every order takes (`ExecuteOrderCommandHandler`): the limits
object it reads is built at boot by a `TradingLimitsResolver` that knows the venue, the config
and the ceilings — one function, unit-tested per venue. The acknowledgement is a field on the
existing command, checked in the handler as the first safety gate (a named block reason
`ACKNOWLEDGEMENT_REQUIRED`), so every surface inherits it. The dialog follows
`ui-presentation-rule.md` (a `QDialog`, OS theme, no custom colour beyond the danger token).

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `src/modules/trading/domain/policies/mainnet_ceilings.py`, `trading_limits_resolver.py` | Ceilings; per-venue resolution with clamp and warning |
| `src/modules/trading/contracts/trading_limits.py` | Venue on the limits DTO |
| `src/modules/trading/application/session/enable_trading/{command,handler}.py` | Acknowledgement gate |
| `src/modules/trading/contracts/enable_trading_result.py` | `ACKNOWLEDGEMENT_REQUIRED` |
| `src/modules/trading/ui/trading/mainnet_acknowledgement_dialog.py`, `trading_presenter.py`, `trading_view.py` | Dialog; limits shown |
| `src/presentation/cli/…trade_once…` | `--acknowledge-mainnet` |
| `src/config/config_keys.py`, `app_config.json` | Per-venue limit blocks |
| `tests/unit/modules/trading/domain/policies/test_trading_limits_resolver.py` | Per venue; missing mainnet refuses; clamp warns |
| `tests/unit/modules/trading/application/session/test_enable_trading.py` | Acknowledgement gate first |
| `tests/unit/modules/trading/ui/trading/test_mainnet_acknowledgement_dialog.py` | Typed name matches; mismatch keeps trading off |
| `Docs/SPEC/SPEC-004_….md`, `SPEC-005_….md` | Rows |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Resolver | unit | unit | Testnet unchanged; mainnet clamped with `WARNING`; missing block refuses |
| Gate | unit | unit | wrong or empty acknowledgement blocks before any network call |
| Dialog | Qt unit test (offscreen) | unit | mismatch leaves the toggle off |
| Testnet unaffected | existing suites | unit | green, no acknowledgement asked on Testnet |
| Human | on mainnet with `EPIC-026R`'s restricted key: the dialog appears, the wrong word refuses | human | recorded here |

Not run yet.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
