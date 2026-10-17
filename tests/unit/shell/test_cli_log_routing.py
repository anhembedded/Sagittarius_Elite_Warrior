"""`BOT-185` - a read-only command's log goes to a bounded file; the console keeps warnings.

Three facts, each against the real Engine logger and the real `create_app`:

1. the console stays quiet and the file receives the records (and a warning
   reaches both, so a failed command is never silent);
2. the directory is bounded: old files are pruned at start, and one file is
   capped by rotation;
3. `--verbose` is accepted anywhere on the line, and a run that does not ask for
   the routing keeps the Engine's stdout log as before.

Retire when: the Engine's logger takes a handler list from the application and
`shell/cli_log_routing.py` goes with its re-apply after each `StdLogger`.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.presentation.cli.cli_parser import (
    VERBOSE_DEST,
    build_parser,
)
from Sagittarius_Elite_Warrior.src.shell import cli_log_routing
from Sagittarius_Elite_Warrior.src.shell.app_config import CLI_COMMANDS_FILE
from Sagittarius_Elite_Warrior.src.shell.cli_log_routing import (
    FILE_PREFIX,
    FILES_KEPT,
    prepare_cli_log,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.infrastructure.logging.std_logger import StdLogger

_COMPONENT = logging.getLogger("App.CliLogTest")


@pytest.fixture
def app_logger_restored() -> Iterator[logging.Logger]:
    """`StdLogger` and `create_app` rewire the process-wide `App` logger; put it back."""
    logger = logging.getLogger("App")
    handlers, level, propagate = list(logger.handlers), logger.level, logger.propagate
    filters = list(logger.filters)
    yield logger
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    for handler in handlers:
        logger.addHandler(handler)
    for log_filter in list(logger.filters):
        logger.removeFilter(log_filter)
    for log_filter in filters:
        logger.addFilter(log_filter)
    logger.setLevel(level)
    logger.propagate = propagate


def _flush(logger: logging.Logger) -> None:
    for handler in logger.handlers:
        handler.flush()


def _only_file(directory: Path) -> Path:
    files = sorted(directory.glob(f"{FILE_PREFIX}*.log"))
    assert len(files) == 1, files
    return files[0]


def test_the_console_stays_quiet_and_the_file_receives_the_records(
    app_logger_restored: logging.Logger,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    routing = prepare_cli_log(tmp_path)
    StdLogger(ConfigManager())
    routing.apply()

    _COMPONENT.info("[test] a table is about to be printed")
    _flush(app_logger_restored)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert "[test] a table is about to be printed" in _only_file(tmp_path).read_text(
        encoding="utf-8"
    )


def test_a_warning_reaches_the_console_and_the_file(
    app_logger_restored: logging.Logger,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    routing = prepare_cli_log(tmp_path)
    StdLogger(ConfigManager())
    routing.apply()

    _COMPONENT.warning("[test] the exchange did not answer")
    _COMPONENT.error("[test] the command failed")
    _flush(app_logger_restored)

    captured = capsys.readouterr()
    assert captured.out == "", "stdout carries the result and nothing else"
    assert (
        " - App.CliLogTest - WARNING - [test] the exchange did not answer"
        in captured.err
    )
    assert " - App.CliLogTest - ERROR - [test] the command failed" in captured.err
    text = _only_file(tmp_path).read_text(encoding="utf-8")
    assert "[test] the exchange did not answer" in text
    assert "[test] the command failed" in text


def test_applying_twice_does_not_double_a_record(
    app_logger_restored: logging.Logger, tmp_path: Path
) -> None:
    routing = prepare_cli_log(tmp_path)
    StdLogger(ConfigManager())
    routing.apply()
    routing.apply()

    _COMPONENT.info("[test] once")
    _flush(app_logger_restored)

    assert _only_file(tmp_path).read_text(encoding="utf-8").count("[test] once") == 1


def test_create_app_keeps_the_routing_after_the_extension_rebuilds_the_logger(
    app_logger_restored: logging.Logger,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`create_app` constructs `StdLogger` twice; the second one clears handlers."""
    routing = prepare_cli_log(tmp_path)

    create_app(ConfigManager(), cli_log=routing)
    _COMPONENT.info("[test] after the graph is built")
    _flush(app_logger_restored)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    text = _only_file(tmp_path).read_text(encoding="utf-8")
    assert "[cli-log] console shows warnings and errors only" in text
    assert "[instance] writable" in text, "records of the build itself are kept"
    assert "[test] after the graph is built" in text


def test_without_routing_the_engine_still_writes_its_log_to_stdout(
    app_logger_restored: logging.Logger, capsys: pytest.CaptureFixture[str]
) -> None:
    create_app(ConfigManager())

    _COMPONENT.info("[test] as today")

    assert " - App.CliLogTest - INFO - [test] as today" in capsys.readouterr().out


def test_a_log_directory_that_cannot_be_used_costs_the_file_not_the_command(
    app_logger_restored: logging.Logger,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    blocker = tmp_path / "logs"
    blocker.write_text("a file where the directory should be", encoding="utf-8")

    routing = prepare_cli_log(blocker)
    StdLogger(ConfigManager())
    routing.apply()
    routing.log_decision()
    _COMPONENT.info("[test] dropped, there is no file")

    assert routing.log_file is None
    err = capsys.readouterr().err
    assert "[cli-log] no log file" in err
    assert "dropped, there is no file" not in err


def test_a_file_that_cannot_be_opened_costs_the_file_and_makes_no_noise_per_record(
    app_logger_restored: logging.Logger,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The directory is fine; the file is not (an ACL `os.access` cannot see)."""
    monkeypatch.setattr(os, "getpid", lambda: 4242)
    moment = datetime(2026, 10, 17, 14, 1, 43, tzinfo=UTC)
    (tmp_path / f"{FILE_PREFIX}20261017T140143-4242.log").mkdir()

    routing = prepare_cli_log(tmp_path, now=moment)
    StdLogger(ConfigManager())
    routing.apply()
    routing.log_decision()
    for index in range(5):
        _COMPONENT.info("[test] record %d", index)

    assert routing.log_file is None
    err = capsys.readouterr().err
    assert err.count("[cli-log] no log file") == 1
    assert "Logging error" not in err


def _seed(directory: Path, count: int) -> list[Path]:
    paths = []
    for index in range(count):
        path = directory / f"{FILE_PREFIX}20260101-0000{index:02d}-{index}.log"
        path.write_text("x", encoding="utf-8")
        os.utime(path, (1_000_000 + index, 1_000_000 + index))
        paths.append(path)
    return paths


def test_the_directory_keeps_at_most_files_kept_and_drops_the_oldest(
    tmp_path: Path,
) -> None:
    seeded = _seed(tmp_path, FILES_KEPT + 15)
    unrelated = tmp_path / "dev-20260101-000000.log"
    unrelated.write_text("a developer's session log", encoding="utf-8")

    routing = prepare_cli_log(tmp_path)

    assert routing.log_file is not None
    assert routing.log_file.parent == tmp_path
    survivors = set(tmp_path.glob(f"{FILE_PREFIX}*")) - {routing.log_file}
    assert routing.log_file.exists(), "opened to prove it can be written"
    assert len(survivors) == FILES_KEPT - 1, "room for this run's own file"
    assert survivors == set(seeded[-(FILES_KEPT - 1) :]), "the newest stay"
    assert unrelated.exists(), "only the CLI's own files are pruned"


def test_a_file_is_capped_by_rotation_and_keeps_one_backup(
    app_logger_restored: logging.Logger,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cap = 2_000
    monkeypatch.setattr(cli_log_routing, "MAX_FILE_BYTES", cap)
    routing = prepare_cli_log(tmp_path)
    StdLogger(ConfigManager())
    routing.apply()

    for index in range(200):
        _COMPONENT.info("[test] record %03d %s", index, "y" * 80)
    _flush(app_logger_restored)

    files = sorted(tmp_path.glob(f"{FILE_PREFIX}*"))
    assert len(files) == 2, files
    one_record = 200
    assert all(path.stat().st_size <= cap + one_record for path in files)
    assert "record 199" in files[0].read_text(encoding="utf-8"), "newest are kept"


@pytest.mark.parametrize(
    "argv",
    [
        ["bot", "list", "--verbose"],
        ["--verbose", "bot", "list"],
        ["bot", "--verbose", "list"],
    ],
)
def test_verbose_is_accepted_at_any_position(argv: list[str]) -> None:
    config = ConfigManager()
    config.load_json(str(CLI_COMMANDS_FILE))

    args = build_parser(config).parse_args(argv)

    assert getattr(args, VERBOSE_DEST) is True


def test_verbose_is_off_when_not_given() -> None:
    config = ConfigManager()
    config.load_json(str(CLI_COMMANDS_FILE))

    args = build_parser(config).parse_args(["bot", "list"])

    assert getattr(args, VERBOSE_DEST, False) is False
