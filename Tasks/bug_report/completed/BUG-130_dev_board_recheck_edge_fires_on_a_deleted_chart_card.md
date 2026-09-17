# BUG-130 — Dev Board's arm-strategy integration tests time out (retracted: this file's own root cause was wrong)

- **Reported:** 2026-09-17 (found while driving EPIC-025 PR #226 to green)
- **Severity:** 🟡 P2 — two integration tests timing out (2000ms `waitUntil`), plus a real log-scan `ERROR`
- **Status:** ✅ Closed 2026-09-17 — **not a distinct bug.** This report's own "confirmed pre-existing" claim and its `_recheck_edge`/deleted-`ChartCard` root-cause hypothesis were both **wrong**, corrected the same day by an independent session's PR review (`pull_request_review.submitted`, review id `5236379445`) that reproduced the two failures correctly and found the real cause: a genuine regression inside PR #226 itself, fixed in the same PR (`tests/integration/presentation/ui/conftest.py`).

## What this report got wrong, and how
The original filing claimed both tests fail identically on a clean worktree of `origin/master-warrior`'s tip (commit `9a0888cf`), "confirming" the failure predates PR #226. That reproduction was run from `/home/user/Sagittarius_Elite_Warrior` (this session's actual checkout, on the PR branch) with `PYTHONPATH=..` and the *test files'* absolute paths pointed at the worktree — but `PYTHONPATH=..` resolves the `Sagittarius_Elite_Warrior` package from **this checkout**, not from the worktree, regardless of which directory the collected test file lives in. So the "master-warrior reproduction" actually ran master-warrior's *old test files* against **this PR branch's own `src/`** — the exact same code both times, dressed up as an independent comparison. `ONBOARDING.md`'s own "verify, don't restate" principle exists for exactly this failure mode; this report is the case study of skipping it.

Real reproduction, done properly by the independent reviewer session (a fresh checkout with its own environment) and confirmed here after the fix: on real `origin/master-warrior`, both tests **pass**. The failure only exists on the PR branch, and only until the fix below landed.

Written up as [`CS-006`](../../../Docs/CASE_STUDIES/CS-006_the_comparison_that_compared_itself.md), whose check — `scripts/verify_against_base.py` — replaces the broken recipe so a future "compare against a clean tree" attempt cannot repeat this exact mistake.

## Real root cause (found by the review, verified here)
`6678d456` (PR 4.3m, this same PR) added a new required constructor parameter to `ArmStrategyCommandHandler.__init__` — `config_store: LiveStrategyConfigStore` (`src/modules/strategy/application/use_cases/arm_strategy/handler.py:56-60`, the "the handler persists the arming itself" change). Every production and unit-test call site was updated; `tests/integration/presentation/ui/conftest.py:290`'s `mock_dispatch` fixture — which hand-constructs the real handler rather than a fake, deliberately, per its own docstring — was not:

```python
if command_type is ArmStrategyCommandHandler:
    handler = ArmStrategyCommandHandler(
        engine.context.container.resolve(LiveStrategySession),
        engine.context.container.resolve(ITradingSession),
    )
```

This raised `TypeError: ArmStrategyCommandHandler.__init__() missing 1 required positional argument: 'config_store'` on every real "arm strategy" click routed through the fixture. `StrategyArmingCoordinator.on_arm_clicked()` catches this as a generic `Exception` and converts it to a status message rather than letting it propagate, which is why the symptom was a `waitUntil` timeout (the awaited `armedSummary` state never arrived) rather than a loud crash — and, verified after the fix, it also explains the `_recheck_edge: Signal source has been deleted` log `ERROR` this report originally chased as a separate mechanism: running both full test files with `--log-cli-level=ERROR` after the fix produces **zero** `ERROR` records, so that was a downstream symptom of the same broken arm flow (the dashboard's chart state cycling through an incomplete/retried arming path), not an independent defect in `HistoryPaginationController`/`ChartCard` lifecycle as originally hypothesized.

## Fix
One line, `tests/integration/presentation/ui/conftest.py`: resolve and pass `LiveStrategyConfigStore` as the handler's third constructor argument (plus the matching import). `LiveStrategyConfigStore` needs no explicit container binding — it takes only `IConfig`, which the engine already provides, so `container.resolve(LiveStrategyConfigStore)` auto-constructs via reflection, the same way `StrategyArmingService`'s own `container.singleton(IStrategyArming, StrategyArmingService)` binding already resolves it in the real composition root (`port_bindings.py:100`). Confirms the review's own aside was right: this was test-fixture breakage only, not a live-app defect.

## Regression test
No new test needed — the two tests this report originally cited already are the regression tests, and they were already failing for the right reason (a real `TypeError` from the real handler, swallowed by the coordinator's generic exception handling): `tests/integration/presentation/ui/test_dev_board_known_gaps.py::test_strategy_dropdown_arms_the_selected_strategy` and `tests/integration/presentation/ui/test_dev_board_manual_order_qt_click.py::test_a_real_long_click_on_the_armed_symbol_reaches_the_real_pipeline`. Verified: both fail before the fixture fix, both pass after (`2 passed` in isolation; `10 passed, 4 skipped` for the two full test files together, with `--log-cli-level=ERROR` showing no `ERROR` record).

## Suggested next steps
None — closed. Left as a record of the verification-methodology mistake (§ above) rather than deleted, per `ONBOARDING.md`'s own preference for correcting a wrong claim in place over erasing it.
