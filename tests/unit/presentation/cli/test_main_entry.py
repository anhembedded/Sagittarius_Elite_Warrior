"""`main()`: what each command-line word starts, and the exit status it returns (`EPIC-038B`, D8).

The app is never built here: `create_app` and the instance lock are replaced, so
the test reads the entry point's own decisions — which branch a word takes,
whether the lock is taken, whether `stop()` runs on every path, what number comes
back — not the object graph (`tests/integration/presentation/
test_main_exit_codes_process.py` runs the real one as a process).
"""

from __future__ import annotations

import argparse
import logging
import sys
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src import main as entry
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_command_handler import (
    ICliCommandHandler,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cli_registry import (
    ICliCommandTable,
)
from sagittarius_engine import App

_SYNC = ["sync", "--symbols", "BTCUSDT"]


class _Recorder:
    """Stands in for the three things that build and guard the app."""

    def __init__(self) -> None:
        self.app = Mock()
        self.instance = Mock()
        self.table = Mock(spec=ICliCommandTable)
        self.table.handlers.return_value = {}
        self.app.container.resolve.side_effect = lambda port: {
            ICliCommandTable: self.table
        }[port]
        self.lock_taken = 0
        self.cli_log_seen: list[object] = []

    def acquire(self) -> Mock:
        self.lock_taken += 1
        return self.instance

    def create(self, config_manager: object, instance: object, cli_log: object) -> Mock:
        assert instance is self.instance
        self.cli_log_seen.append(cli_log)
        return self.app


@pytest.fixture
def built(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    recorder = _Recorder()
    monkeypatch.setattr(entry, "acquire_instance_access", recorder.acquire)
    monkeypatch.setattr(entry, "create_app", recorder.create)
    return recorder


def _run(monkeypatch: pytest.MonkeyPatch, *words: str) -> int:
    monkeypatch.setattr("sys.argv", ["main.py", *words])
    return entry.main()


def test_a_bare_main_prints_help_and_exits_two(
    monkeypatch: pytest.MonkeyPatch,
    built: _Recorder,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """D8: a supervisor that starts it by mistake neither opens a window nor
    waits on input — and nothing is built, locked or booted."""
    status = _run(monkeypatch)

    assert status == int(ExitCode.USAGE)
    out = capsys.readouterr().out
    assert "gui" in out
    assert "shell" in out
    assert "sync" in out
    assert built.lock_taken == 0
    built.app.boot.assert_not_called()


def test_gui_hands_over_to_the_desktop_entry_point_and_takes_no_lock(
    monkeypatch: pytest.MonkeyPatch, built: _Recorder
) -> None:
    """The desktop application loads its own configuration and takes its own
    lock; a lock taken here first would make the window start read-only."""
    gui = Mock()
    monkeypatch.setattr(entry, "_GUI_MAIN", gui)

    status = _run(monkeypatch, "gui")

    assert status == 0
    gui.assert_called_once_with()
    assert built.lock_taken == 0
    built.app.boot.assert_not_called()


def test_gui_keeps_the_status_the_window_exits_with(
    monkeypatch: pytest.MonkeyPatch, built: _Recorder
) -> None:
    monkeypatch.setattr(entry, "_GUI_MAIN", Mock(side_effect=SystemExit(7)))

    with pytest.raises(SystemExit) as raised:
        _run(monkeypatch, "gui")

    assert raised.value.code == 7


def test_shell_boots_the_app_waits_for_the_prompt_and_stops(
    monkeypatch: pytest.MonkeyPatch, built: _Recorder
) -> None:
    shell = Mock()
    monkeypatch.setattr(entry, "InteractiveShell", Mock(return_value=shell))

    status = _run(monkeypatch, "shell")

    assert status == 0
    assert built.lock_taken == 1
    built.app.context.hosted_services.register.assert_called_once_with(shell)
    built.app.boot.assert_called_once_with()
    shell.wait_for_exit.assert_called_once_with()
    built.app.stop.assert_called_once_with()
    built.instance.release.assert_called_once_with()


def test_a_command_returning_none_exits_zero(
    monkeypatch: pytest.MonkeyPatch, built: _Recorder
) -> None:
    command = Mock(return_value=None)
    monkeypatch.setitem(entry._HEADLESS_COMMANDS, "sync", command)

    assert _run(monkeypatch, *_SYNC) == 0
    command.assert_called_once()
    built.app.stop.assert_called_once_with()
    built.instance.release.assert_called_once_with()


def test_a_command_outcome_is_the_exit_status(
    monkeypatch: pytest.MonkeyPatch, built: _Recorder
) -> None:
    monkeypatch.setitem(
        entry._HEADLESS_COMMANDS,
        "sync",
        Mock(return_value=CliOutcome(ExitCode.EXCHANGE)),
    )

    assert _run(monkeypatch, *_SYNC) == int(ExitCode.EXCHANGE)


def test_an_unexpected_exception_exits_one_logs_the_traceback_and_still_stops(
    monkeypatch: pytest.MonkeyPatch,
    built: _Recorder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setitem(
        entry._HEADLESS_COMMANDS, "sync", Mock(side_effect=RuntimeError("boom"))
    )

    with caplog.at_level(logging.ERROR, logger="App.CliHost"):
        status = _run(monkeypatch, *_SYNC)

    assert status == int(ExitCode.ERROR)
    assert any(r.exc_info for r in caplog.records if r.name == "App.CliHost")
    built.app.stop.assert_called_once_with()
    built.instance.release.assert_called_once_with()


def test_a_boot_failure_exits_one_and_gives_the_lock_back(
    monkeypatch: pytest.MonkeyPatch, built: _Recorder
) -> None:
    built.app.boot.side_effect = RuntimeError("cannot boot")

    assert _run(monkeypatch, *_SYNC) == int(ExitCode.ERROR)
    built.instance.release.assert_called_once_with()


class _DeclaredHandler(ICliCommandHandler):
    seen: argparse.Namespace | None = None

    @staticmethod
    def handle(args: argparse.Namespace, app: App) -> CliOutcome | None:
        del app
        _DeclaredHandler.seen = args
        return CliOutcome(ExitCode.PREFLIGHT_FAILED)


def test_a_command_a_module_declares_runs_without_an_edit_here(
    monkeypatch: pytest.MonkeyPatch, built: _Recorder
) -> None:
    """Open/closed: a word that is not in `_HEADLESS_COMMANDS` is found in the
    table `declare_cli` fills, and its outcome is the status."""
    monkeypatch.delitem(entry._HEADLESS_COMMANDS, "sync")
    built.table.handlers.return_value = {"sync": _DeclaredHandler}

    assert _run(monkeypatch, *_SYNC) == int(ExitCode.PREFLIGHT_FAILED)
    assert _DeclaredHandler.seen is not None
    assert _DeclaredHandler.seen.symbols == "BTCUSDT"


def test_a_word_nobody_runs_is_a_usage_error(
    monkeypatch: pytest.MonkeyPatch,
    built: _Recorder,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delitem(entry._HEADLESS_COMMANDS, "sync")

    assert _run(monkeypatch, *_SYNC) == int(ExitCode.USAGE)
    assert "Unknown command: sync" in capsys.readouterr().err


def test_machine_output_builds_the_app_with_its_console_log_on_stderr(
    monkeypatch: pytest.MonkeyPatch, built: _Recorder
) -> None:
    """`--json` promises stdout is one document; the Engine's console logger
    writes to whatever `sys.stdout` is when it is built, so for that run, and only
    that run, the app is built while `sys.stdout` names stderr. Afterwards
    `sys.stdout` is the real one again, for the report to be printed on."""
    seen: list[bool] = []
    real_stdout = sys.stdout

    def create(config_manager: object, instance: object, cli_log: object) -> Mock:
        seen.append(sys.stdout is sys.stderr)
        return built.app

    monkeypatch.setattr(entry, "create_app", create)
    monkeypatch.setitem(
        entry._HEADLESS_COMMANDS, "exchange-status", Mock(return_value=None)
    )

    _run(monkeypatch, "exchange-status", "--json")
    assert sys.stdout is real_stdout
    _run(monkeypatch, "exchange-status")

    assert seen == [True, False]


_ROUTING = object()


@pytest.mark.parametrize(
    ("argv", "routed"),
    [
        (["exchange-status"], True),
        (["exchange-status", "--json"], True),
        (["exchange-status", "--verbose"], False),
        (["--verbose", "exchange-status"], False),
        (_SYNC, False),
        (["bot", "apply", "plan.json"], True),
        (["bot", "apply", "plan.json", "--verbose"], False),
    ],
)
def test_only_a_read_only_command_without_verbose_gets_its_log_routed_to_a_file(
    monkeypatch: pytest.MonkeyPatch,
    built: _Recorder,
    argv: list[str],
    routed: bool,
) -> None:
    """`BOT-185`, `BOT-186`: `sync` keeps its log on stdout (`run`'s is checked on the registry), a short-lived
    writer (`bot apply`) goes quiet like a reader; `--verbose` asks for the console."""
    monkeypatch.setattr(entry, "prepare_cli_log", lambda log_dir: _ROUTING)
    monkeypatch.setattr(entry, "read_only_instance_access", lambda: built.instance)
    monkeypatch.setitem(entry._HEADLESS_COMMANDS, "sync", Mock(return_value=None))
    monkeypatch.setitem(
        entry._HEADLESS_COMMANDS, "exchange-status", Mock(return_value=None)
    )

    _run(monkeypatch, *argv)

    assert built.cli_log_seen == [_ROUTING if routed else None]
