# EPIC-026C — `SPEC-010`, arm a strategy on a symbol and disarm it, is written and proven

**Status:** 🔵 Backlog
**Source:** [`PRO-005`](../../../proposal/PRO-005.md) §1.4; the user (2026-09-20): *"chi nhỏ task"*.
**Risk:** 🟢 — documentation; the human row is the one `EPIC-025B`/`C` already wait for.
**Complexity:** S — arm/disarm handlers, the lease, `LiveStrategySession` and the tick path exist
(`EPIC-022`, `EPIC-025` PR 2.1c–2.1g).
**Epic:** [`EPIC-026`](../README.md)
**SPEC:** `SPEC-010` — reserved 🔵 in [`Docs/SPEC/README.md`](../../../../Docs/SPEC/README.md)
**Depends on:** the user's Testnet confirmation that closes
[`EPIC-025B`](../../EPIC-025_module_theo_bounded_context/incomplete/EPIC-025B_phase1_trading_and_surfaces.md)
and [`EPIC-025C`](../../EPIC-025_module_theo_bounded_context/incomplete/EPIC-025C_phase2_strategy.md)
— the same run is this SPEC's human row, so the two records cite one observation.

---

## 1. Context and problem

Arming is the moment a strategy claims a symbol (`SPEC-005` §5, `PRO-003` §4.1.2) and the tick
path starts turning signals into `ExecuteOrderCommand`
(`src/modules/strategy/application/services/live_strategy_session.py`,
`live_trading_coordinator.py`). `ArmStrategyCommandHandler` refuses to re-arm while trading is on
(`EPIC-022` §4.1). Stage 2 hangs three new behaviours on this exact moment — leverage set on the
exchange (`EPIC-026J`), the protective stop's parameters (`EPIC-026K`), the breaker's scope
(`EPIC-026L`) — and each of them must update this SPEC. It has to exist.

## 2. Acceptance criteria

- [ ] `Docs/SPEC/SPEC-010_arm_a_strategy_on_a_symbol_and_disarm_it.md` exists from the template
      and is ✅ in the index's main table.
- [ ] §3 covers: choosing the strategy and its parameters, validation
      (`strategy_param_validation.py`), the lease claim, the engine start, the first tick; and
      disarm as the mirror, including that an open position is **not** closed by disarming.
- [ ] §5 has a row per `StrategyArmResult` refusal (trading on, symbol leased by another owner,
      unknown key, invalid parameters) and for a tick arriving during re-arm (the snapshot rule in
      `LiveStrategySession`'s docstring).
- [ ] §6 states: one live symbol only (`config_keys.py:98`); a signal for another symbol is
      ignored; arming does not enable trading and does not send an order by itself.
- [ ] §8 cites `tests/unit/modules/strategy/application/use_cases/test_arm_strategy.py`, the
      contract suite for `ITradingSession`'s lease, the tick-path integration test
      (`tests/integration/application/test_live_trading_pipeline_against_fake_server.py`), and the
      human row: arm on Testnet, see the first order from a signal, disarm, see the lease released.

## 3. Design

As `EPIC-026A`. One addition: §7 names `IArmedStrategy`, `IStrategyArmingControl`,
`ITradingSession` (the lease) and `IOrderSubmission` — the four ports stage 2 will extend — so
the pull requests that extend them find this file by name.

## 4. Changes, per file

| File | Change |
| :--- | :--- |
| `Docs/SPEC/SPEC-010_arm_a_strategy_on_a_symbol_and_disarm_it.md` | New |
| `Docs/SPEC/README.md` | `SPEC-010` moves to the main table as ✅ |
| `Docs/SPEC/SPEC-005_place_a_manual_order.md` | §5's lease row links `SPEC-010` |
| `tests/unit/modules/strategy/application/use_cases/test_arm_strategy.py` | Only if a §5 row is uncovered |

## 5. Testing

| Criterion | Check | Tier | Expected |
| :--- | :--- | :--- | :--- |
| Index consistent, paths exist | `.venv/bin/python -m pytest tests/unit/architecture/test_spec_index_is_consistent.py -q` | unit (guard) | green |
| Refusals covered | `.venv/bin/python -m pytest tests/unit/modules/strategy/application/use_cases/test_arm_strategy.py -q` | unit | green |
| Tick → order | `.venv/bin/python -m pytest tests/integration/application/test_live_trading_pipeline_against_fake_server.py -q` | integration | green |
| Human row | the user's `EPIC-025B`/`C` run: arm, first order, disarm, lease released | human | one observation, cited by three records |

Not run yet.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
