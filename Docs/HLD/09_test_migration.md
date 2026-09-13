# §9 — What happens to the tests: move, rewrite, delete, retarget

- **Status:** 🔵 Proposed 2026-09-13 (ADR D18), in answer to the user: *"mình chưa cần nhắc test sẽ
  viết lại, xóa bỏ như nào"* ("we have not yet said how the tests will be rewritten or removed").
  Numbers below were measured on `master-warrior` at `85230368`; the scripts to re-measure are
  in §9.6.
- **Why this needs its own section.** The test suite is the safety net that lets a migration
  change structure without changing behaviour. If the suite is rewritten carelessly it stops
  being evidence; if it is left as is, it becomes vacuous — a guard that scans a directory the
  migration emptied passes forever. Both have happened in this repository.

## 9.1 The pattern applied — tests travel with the code, and behaviour is characterised first

Three named practices, no invention:

| Practice | Origin | What it means here |
| :--- | :--- | :--- |
| **Tests travel with the code they test** | the Strangler Fig migration discipline (Fowler) | a test is moved in the same commit as its subject, by `git mv` plus an import rewrite, **without changing its body**. If the body must change for the test to pass, it is not a move — it is a rewrite, and it is written down as one |
| **Characterisation tests before restructuring** | Feathers, *Working Effectively with Legacy Code* | where a behaviour is about to lose its current test (a screen that becomes a surface), its assertions are inventoried first and the new test is written from the inventory, not from the new code |
| **Golden master** | approval testing | the backtest's trade log for a fixed dataset and strategy is captured in Phase 0 and asserted bit-identical through Phase 3 — the "bit-identical" promise in `EPIC-025D` becomes a test, not a sentence |

The tiers do not change (ADR D7): unit, integration, sanity, testnet keep their meaning and their
place in `scripts/ci-local.ps1`. The sanity tier gains **zero** tests (`testing-rule.md` §1).

## 9.2 The suite today, by what the migration does to it

| Tier | Files | Tests | Of which |
| :--- | :-: | :-: | :--- |
| `tests/unit` | 353 | 2,896 | `presentation/` 219 files / 1,974 tests (68 % of unit); `domain/` 51 / 427; `application/` 49 / 277; `infrastructure/` 23 / 177 |
| `tests/integration` | 32 | 105 | `presentation/` 20 files (11 under `ui/`, of which 7 are Dev Board Qt-click tests); `infrastructure/` 7; `application/` 3 |
| `tests/sanity` | 6 | 16 | process-level: composition root, circular imports, thread affinity, self-check |
| `tests/testnet` | 2 | 3 | opt-in, real credentials |

Coupling to the old layout, measured:

| Coupling | Files | Consequence |
| :--- | :-: | :--- |
| Tests of the Trading screen / the Dev Board screen | 13 / 16 (2 in both) | their **subject disappears** in Phase 1 (screens become surfaces, widgets become cards) → rewrite category |
| Tests importing the composition root (`binance_bot_module`, `app_bootstrapper`, `main`) | 28 | one fixture change in Phase 0 (`shell.create_app`) keeps them unchanged |
| Tests naming `src/<layer>/…` paths as strings | 16 | retarget category |
| Path-scanning guards (`ast`, `rglob`) | 20 | retarget in Phase 0, with a non-emptiness assertion, or they go vacuous |
| Tests on `TradingSessionState` / `LiveStrategySession` | 24 / 15 | move with their subject (Phase 1 / Phase 2); the lease and the per-symbol session add tests, remove none |
| Tests of code the plan deletes (`RunBacktestCommand`, `BacktestState`, the two order events, `StatGrid`) | 5 | delete category |
| Tests needing a live `qtbot` | 29 (unit) | stay in unit; they are card and kit tests, not screen tests |

## 9.3 The four categories and the rule for each

**1. Move** — the default, and the bulk of the suite (domain, application, infrastructure, kit,
qml, components, state, registry). Rule: `git mv` to the mirrored path under the same tier
(`tests/unit/modules/<id>/…`), rewrite imports, change nothing else. A moved test whose body had to
change is reported as a rewrite. Expected count change: **zero**.

**2. Rewrite** — only where the subject ceases to exist: the Trading and Dev Board Presenters,
their view models and the Dev Board integration tests. Rule, in order: (a) inventory every
assertion of the old tests into a table *behaviour → old test → new owner (card or surface)*, in
the phase's task file; (b) write the card's test module from the inventory — one card, one test
module, under `tests/unit/modules/trading/ui/` or `…/strategy/ui/`; (c) the surface's test asserts
only layout facts (which places, which contributions, in which order) and **no** behaviour; (d)
delete the old test in the same pull request, and only after (b) covers every row of (a). Expected
count change: **down** — the 59 duplicated members had duplicated tests; two tests of one behaviour
become one. The integration Qt-click tests (`test_dev_board_manual_order_qt_click.py` and its
siblings) are rewritten against the surface, same tier, because they are the only tests that press
real buttons; they are not moved to unit.

**3. Delete** — only with the subject. Rule: the deleted test is listed in the task file with the
sentence "subject deleted; behaviour exists nowhere else", and the reviewer checks that sentence.
Five files today. A test may never be deleted because it is inconvenient.

**4. Retarget** — guards and path-coupled tests. Rule: every guard that scans a path gains, in Phase
0, an assertion that the scan found at least one file, so that a moved directory fails the guard
instead of silencing it. The five architecture guards named in HLD §6.1 and the existing ones
(`test_no_cross_screen_imports`, `test_screen_layer_structure`, `test_card_layer_structure`,
`test_application_layer_structure`, `test_only_the_session_factory_constructs_binance_client`,
`test_order_submission_mode_live_is_restricted`, `test_quick_widget_only_in_embed`,
`test_qml_library_does_not_import_screens`, the sanity `test_composition_root` and
`test_circular_imports`) are generalised to the new paths **before** any code moves, in the same
Phase 0 pull request as the new guards, and gathered under `tests/unit/architecture/` (the declared
exception to mirroring, HLD §3.2). Sanity guards stay in sanity.

## 9.4 Per phase — what moves, what is rewritten, what the safety net is

| Phase | Move | Rewrite | Delete | Safety net added |
| :-: | :--- | :--- | :--- | :--- |
| 0 | `unit/application/use_cases/{sync,database,stream}`, the market-data queries, `unit/infrastructure/{persistence, binance market side}`, `unit/presentation/ui/screens/data_management` (9 files / 52 tests), the two `integration/*database*` flows | — | — | the golden master for backtest; the retargeted guards with non-emptiness; `tests/unit/architecture/` created; `pytest --collect-only -q` count recorded as the baseline |
| 1 | `unit/domain/trading`, `unit/application/use_cases/trading` (except arm/disarm), `unit/infrastructure/binance` futures side, the 24 `TradingSessionState` files | Trading + Dev Board presenter and view-model tests (13 unit files / 91 tests) → card tests; 7 Dev Board integration tests → surface tests | — | the lease tests (refuse, release, owner mismatch); "two surfaces, two instances" test; `dev.mode=false` boots test; the regression tests for `BUG-112/116/117` untouched and green |
| 2 | `unit/domain/strategies`, the strategy services, arm/disarm, the 15 `LiveStrategySession` files | strategy card and last-signal card tests from the inventory | — | per-symbol session tests; `ISizingPolicy` tests carry the old `position_sizing_bridge` cases unchanged (ADR D17) |
| 3 | `unit/domain/backtesting`, `unit/application/use_cases/backtest`, `unit/presentation/ui/screens/backtest` (24 files / 161 tests), 4 backtest integration flows | — | the 5 files on `RunBacktestCommand`, `BacktestState`, the order events, `StatGrid` | the golden master must still pass **before** the delete |
| 4 | `unit/presentation/ui/{kit,qml,components,common,state,registry}` → `support/ui_kit` and `support/charting` mirrors (about 90 files) | — | — | the UI-map guard |
| 5 | — | `test_main_window_state.py` against `NavigationService` | — | the Engine's screen conformance suite runs on every surface |

## 9.5 What is forbidden during the migration

- `@pytest.mark.skip`, `xfail`, or a commented-out test to get a phase through. A red test is
  either fixed or its deletion is justified under category 3.
- A rewritten test that asserts **less** than the inventory row it replaces.
- Moving a test to a different tier, or adding a sanity test.
- Deleting a guard because "the directory it scans is gone" — that is the vacuous-guard failure
  §9.3 rule 4 exists to prevent; retarget it.
- Reporting a phase done without the count delta explained: *moved N, rewritten M → K, deleted D
  (each with its reason), added A*.

## 9.6 How each phase proves it

```bash
pytest --collect-only -q tests/unit tests/integration 2>/dev/null | tail -1     # the count, before and after
pytest tests/unit/architecture -q                                                # guards, as named failures
pwsh -NoProfile -File scripts/ci-local.ps1 -Full > /tmp/ci.log 2>&1              # the gate; grep the LOG_FILE it prints
grep -rn "pytest.mark.skip\|xfail" tests --include=*.py | wc -l                  # must not grow
python3 tools/measure_duplicate_members.py                                       # Phase 1's 59 → 0 (script committed in Phase 0)
```

The task file of each phase carries the table of §9.4's row filled in with real numbers, and the
assertion inventory of every rewrite.
