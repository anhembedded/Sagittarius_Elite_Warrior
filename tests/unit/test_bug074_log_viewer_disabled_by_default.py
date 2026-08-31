"""Regression test for `BUG-074`.

`app_config.json` used to ship `"log.viewer.enabled": true` — a developer
convenience that streams every log line to a companion `Sagittarius_LogViewer`
GUI at `127.0.0.1:9999`. Every `create_app()` call constructs a `StdLogger`
(`src/main.py`), which — when the viewer is enabled — attaches a
`TcpLogViewerHandler` to the shared `"App"` logger. That handler spawns a real,
continuously-active background thread (`Sagittarius-TcpLogWorker`,
`sagittarius_engine/infrastructure/logging/tcp_log_viewer_handler.py`) that
loops forever retrying a TCP connection nothing is listening on in CI/tests.

`StdLogger.__init__` closes the *previous* `StdLogger`'s handlers whenever a
*new* one is constructed (same `"App"` logger singleton), but nothing
constructs a "next" one after the last integration/sanity test that boots a
real `App` — so this thread survives, alive and looping, for the rest of a
single-process pytest run. CI runs the whole suite (`tests/integration` +
`tests/sanity` + `tests/unit`) sequentially in one process
(`pytest tests/ -q`, no xdist — unlike `scripts/ci-local.ps1`, which isolates
`tests/sanity` into its own job/process), so that thread's continuous
socket/queue/exception activity was still running deep into `tests/unit`,
racing the main thread's Qt/shiboken object teardown inside `qtbot.wait*()`
calls — reproduced as `Fatal Python error: Aborted` /
`Segmentation fault (core dumped)`, always at the same test
(`test_history_pagination_controller.py::test_a_fetch_that_found_more_data_reschedules_a_recheck_after_cooldown`)
because collection order is fixed, so the same amount of accumulated
background-thread activity always lands on the same `qtbot.waitUntil()` call.

This does not unit-test the crash itself (that needs the real multi-thousand-
test accumulation `BUG-074`'s report reproduces) — it guards the concrete,
fast-to-check mechanism: the real default config must never enable a
background network handler that outlives every test that boots it.
"""

from __future__ import annotations

import threading

from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.infrastructure.logging.std_logger import StdLogger
from sagittarius_engine.utils.path_utils import PathUtils

_TCP_LOG_WORKER_THREAD_NAME = "Sagittarius-TcpLogWorker"


def _real_app_config() -> ConfigManager:
    config_manager = ConfigManager()
    app_json = PathUtils.get_relative_path(
        __file__, "..", "..", "src", "config", "app_config.json"
    )
    config_manager.load_json(app_json)
    return config_manager


def test_the_real_app_config_does_not_enable_the_tcp_log_viewer():
    """The config-level guard: cheap, exact, and what actually regresses."""
    config_manager = _real_app_config()

    assert config_manager.get("log.viewer.enabled", False) is False, (
        "src/config/app_config.json enables the TCP LogViewer by default — "
        "every create_app() call then leaks a 'Sagittarius-TcpLogWorker' "
        "background thread that outlives the test that started it (BUG-074). "
        "Enable it per-developer in user_config.json instead, never in the "
        "shipped default."
    )


def test_a_std_logger_built_from_the_real_app_config_spawns_no_tcp_worker_thread():
    """The behavioral guard: proves the mechanism, not just the config value.

    Mirrors exactly what `create_app()` does (`src/main.py`:
    `StdLogger(config_manager)`) against the real, unmodified config file —
    this is the exact call every integration/sanity test's App boot makes.
    """
    before = {t.ident for t in threading.enumerate()}

    logger = StdLogger(_real_app_config())
    try:
        leaked = [
            t.name
            for t in threading.enumerate()
            if t.ident not in before and t.name == _TCP_LOG_WORKER_THREAD_NAME
        ]
        assert leaked == [], (
            f"StdLogger spawned {leaked} from the real app_config.json — this "
            "thread has no scheduled shutdown and will keep running for the "
            "rest of the pytest process, which is BUG-074's root cause."
        )
    finally:
        # StdLogger has no public teardown of its own — it relies on the NEXT
        # StdLogger construction to close its handlers (see this file's
        # module docstring). Do that ourselves so this test does not itself
        # leak a handler into whatever runs after it.
        for handler in list(logger._logger.handlers):
            handler.close()
            logger._logger.removeHandler(handler)
