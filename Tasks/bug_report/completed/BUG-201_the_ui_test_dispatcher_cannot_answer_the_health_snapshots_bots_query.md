# BUG-201 — Every publish on the UI integration app logs a `[health-section] 'bots' raised AttributeError` WARNING

- **Reported:** 2026-10-13 (a coordinating session, from PR #472's author, who reproduced it; present on clean master `93ff7d0`)
- **Severity:** 🟢 P3 — a WARNING in every run of `test_workbench_conformance.py`; it fails the CI run-log scan only when a test in that file fails and pytest prints the captured log, where it hides the real failure under a second complaint
- **Status:** ✅ Fixed (2026-10-13)
- **Board:** The UI integration fixture's fake dispatcher answered the health snapshot's `GetBotStatusReportQuery` with a `_FakeResponse`, so the `bots` section raised `AttributeError ... state_counts` on every publish; fixed by answering that query with a real, empty `BotStatusReport`.
- **Context:** Health snapshot (`src/modules/operations/application/health_publisher.py`) → bots section (`src/modules/bots/application/services/bots_health_contributor.py`) → UI integration fixture `tests/integration/presentation/ui/conftest.py::app_engine`
- **Environment:** Linux container, Python 3.12, offscreen Qt, master `5cea632`.

## Reproduction
1. `pytest tests/integration/presentation/ui/test_the_health_snapshot_publishes_cleanly_on_the_ui_app.py` (added by this fix) on a tree without the fix.
2. `app_engine` boots the composed GUI app; `HealthCadence.publish_now()` publishes one snapshot. Always reproduces.

## Symptom
```
App.Operations.Health WARNING: [health-section] 'bots' raised AttributeError: '_FakeResponse' object has no attribute 'state_counts'
```

## Root cause
`app_engine` replaces the container dispatcher's `dispatch` with `mock_dispatch` (`conftest.py`), which answers every command or query it has no branch for with `_FakeResponse(success, data)`. Since `#470` the `bots` health contributor dispatches `GetBotStatusReportQuery` and calls `state_counts()` on the answer (`bots_health_contributor.py:43-49`). The generic fake has no such member; the collector (`health_section_collector.py:104`) catches the error and logs it as a WARNING. The fake answered a query it was never shaped for: it was built from the calls the suite made before the health publisher existed (`testing-rule.md`, `CS-001`), and a background publisher now sends queries nobody in the suite writes.

## Fix
The queries `mock_dispatch` answers with a real value now live in one table, `typed_query_answers.py`, replacing the inline `()` branch; `GetBotStatusReportQuery` joins it with a real `BotStatusReport()` (an app with no bot file; this suite starts no bot). `conftest.py`, a registered god-file, shrinks from 410 to 402 lines and its baseline is lowered to match. The generic `_FakeResponse` fallback stays strict, so the next query it cannot answer raises by name instead of passing silently. Other fake dispatchers of this shape: `test_main_window_state.py` wraps the real dispatcher, and the unit-tier `mock_dispatcher` fixtures are per-presenter `Mock`s that no publisher reads.

## Regression test
`tests/integration/presentation/ui/test_the_health_snapshot_publishes_cleanly_on_the_ui_app.py`: `test_one_publish_on_the_booted_app_logs_no_warning` (red before: the line above) and `test_the_bots_section_is_read_from_a_real_report_with_no_bot` (positive proof the section is answered). With the fix's branch disabled both fail; with it, both pass.

## Verification
- Regression tests red without the branch, green with it (above).
- `tests/integration/presentation`: 160 passed, 3 skipped, 1 failed: `test_workbench_conformance[True-1024x700]` (`backtest ... needs 719x706`), which fails identically on pristine master in this container and is not touched by this change.
