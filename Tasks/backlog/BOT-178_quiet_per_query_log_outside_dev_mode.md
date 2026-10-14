# BOT-178 — The Engine's per-query `Executing query:` line is written only in developer mode

**Status:** 🟡 In progress
**Priority:** P2
**Board:** The Engine's dispatcher logged `Executing query: <name>` at INFO on every poll (bots status and list every 10 s, connection checks), burying fills, orders and warnings; the app now drops that one record unless `dev.mode` is on, and the Engine-side DEBUG patch is proposed in the task.
**Source:** The owner, 2026-10-14: *"không phải dev thì tắt luôn mất cái log này giúp tui"* ("when not in developer mode, switch this log off for me"), relayed by the coordinator session.
**Risk:** 🟢 — one record is dropped outside developer mode; every other level and line is untouched, and no level is raised, so the run-log scan is unaffected.
**Complexity:** S — one filter, one call at the composition root, tests, one doc section.
**Depends on:** None.

---

## 1. Context and problem
The desktop's log fills with INFO lines every few seconds:

```
2026-10-14 21:04:43,183 - App - INFO - Executing query: GetBotStatusReportQuery
2026-10-14 21:04:43,183 - App - INFO - Executing query: ListBotsQuery
2026-10-14 21:04:52,220 - App - INFO - Executing query: GetExchangeConnectionStatusQuery
```

They are not in `src/`: the Engine's `Dispatcher.dispatch` writes them (`sagittarius_engine/kernel/dispatcher.py:35`, at the pinned `engine.ref` commit), through the container's one `ILogger`, so on the single `App` logger. `Docs/OPERATIONS/LOGGING.md` §5 had accepted them for the headless host (2 880 a day) and named a filter as the alternative, rejected because it "would hide the queries of a failing run". That objection does not hold for this record: a failed dispatch is its own ERROR line (`<name> failed`), which a filter on the INFO query line does not touch. The desktop's 10 s polling is also far past the 2 880 a day the decision weighed, and `logging-rule.md` §6 puts a per-dispatch trace at DEBUG.

## 2. Acceptance criteria
- [ ] Outside developer mode a dispatched query writes no INFO record.
- [ ] In developer mode (`--dev`, `--debug`, or `dev.mode` in the file) it does.
- [ ] A dispatched command still logs at INFO, a failed query still logs its ERROR, and a WARNING from any `App.*` logger still logs.
- [ ] The Engine is not edited; the Engine-side fix is written down as a patch below.
- [ ] Building the graph again does not stack the filter.

## 3. Design
The Engine's dispatcher has no logger of its own, so there is no "dispatcher logger" to put at DEBUG: the level is the `App` logger's, shared by everything, and lowering it would hide the INFO lines that matter. What the app owns is what that logger lets through, so it installs a `logging.Filter` on the `App` logger (`QueryDispatchFilter`), through `quiet_query_dispatch_outside_developer_mode(config)`, called by `create_app` right after the Engine's `StdLogger` is built. The filter is on the logger, not on a handler, because the Engine rebuilds the handlers (`create_app` builds its logger twice, `console_log_stream.py`), and a logger's filters survive that.

A record is matched on what the Engine attaches to it (`record.extra["submodule"] == "Dispatcher"`, INFO) and on its `Executing query: ` prefix. The prefix is the one string left: the dispatcher records no query-versus-command flag, and the command line must keep its level. That residue is why the module says when it retires; the Engine patch below removes it. Developer mode is `dev.mode`, which `--dev` and `--debug` set through `DevMode.config_overrides` and the file sets directly, so one value covers the three ways in.

Pattern applied (`CONSTITUTION.md` P5): the existing `console_log_to` precedent, an app-side adjustment of the Engine's logging with the Engine untouched (decision O7).

## 3a. Reuse
`load_app_config` / `DevMode` (`.claude/rules/capabilities.md`): used, `dev.mode` is the one developer-mode value. `console_log_to`: not used, it retargets a stream, not a record. No UI need.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/shell/dispatch_log_filter.py` (new) | `QueryDispatchFilter` and the installer, outside developer mode only, idempotent |
| `src/shell/composition_root.py` | calls the installer after the Engine's `StdLogger` is built |
| `tests/unit/shell/test_query_dispatch_is_quiet_outside_dev_mode.py` (new) | both modes, command/ERROR/WARNING levels, no stacking, on the real graph and dispatcher |
| `tests/integration/presentation/test_run_process_beside_other_processes.py` | the process test that bounded the line at two per health interval now asserts none in a plain `run` |
| `Docs/OPERATIONS/LOGGING.md` | §5: the 2026-10-13 acceptance is replaced by this behaviour |

## 5. Testing
Unit tier, on `create_app()` and the Engine's real `Dispatcher` (`CS-002`): AC1 `test_a_dispatched_query_writes_no_info_record_outside_developer_mode`; AC2 `test_a_dispatched_query_writes_its_info_record_in_developer_mode`; AC3 `test_a_dispatched_command_still_logs_at_info_outside_developer_mode`, `test_a_failing_query_still_logs_its_error_outside_developer_mode`, `test_a_warning_from_the_app_still_logs_outside_developer_mode`; AC5 `test_the_filter_is_installed_once_however_often_the_graph_is_built`. Integration: `test_a_plain_run_writes_no_dispatcher_query_lines` in a real `run` process. `run` accepts no `--dev`, so developer mode is proved at the unit tier only.

## 6. Docs touched
`Docs/OPERATIONS/LOGGING.md` §5 (the dispatcher line). No `Docs/MODULES/*.md`: no module's shape, boundary, lifecycle, thread or timing constant changes.

## Implementation notes (written when done)
**Engine-side patch (proposed, not applied; an Engine change needs the owner's separate confirmation, `ONBOARDING.md` §2).** In `sagittarius_engine/kernel/dispatcher.py`, `Dispatcher.dispatch`, log the query line at DEBUG and keep the command line at INFO:

```python
        log_dispatch = logger.debug if msg_type == "query" else logger.info
        log_dispatch(
            f"Executing {msg_type}: {handler_class.__name__}",
            extra={"submodule": "Dispatcher"},
        )
```

`tests/test_full_coverage.py:693` asserts the command line at INFO and still passes; a test for the query line at DEBUG is added beside it. When this is pinned in `engine.ref`, delete `src/shell/dispatch_log_filter.py`, its installer call and `test_query_dispatch_is_quiet_outside_dev_mode.py`'s filter test.

**Findings.** (1) `run` accepts no `--dev` (only `gui` and `shell` do), so a headless developer enables the line with `dev.mode` in the configuration file. (2) The line is a record on the logger `App`, not a child logger, so only a filter or the `App` level can touch it; the level is shared with everything. (3) The prefix match is unavoidable app-side; see §3.

Verification and delivery state are recorded on the pull request.
