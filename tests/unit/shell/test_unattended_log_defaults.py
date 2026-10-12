"""`EPIC-038G` — what an unattended run logs to, and what the guide promises.

A service runs for months. Its log must go where the supervisor bounds it
(stdout: the journal, or NSSM's rotated capture), and the one way to unbound it
(`log.file`) must be documented as such for exactly as long as it is true.

Three facts, each pinned to the real Engine rather than to a copy of its
behaviour:

1. the shipped configuration logs to stdout and sets no `log.file`;
2. `log.file` is the key the Engine reads, and what it opens is a plain
   `logging.FileHandler` — no rotation, no cap;
3. `Docs/OPERATIONS/LOGGING.md` says (2) in one sentence, names the key, and
   gives the `logrotate` stanza that works with a handler holding its file open.

When the Engine gains a rotating handler, (2) fails on purpose: the guide's
sentence is then false and must change in the same commit as the Engine pin.

Retire when: the Engine's file log rotates by itself and the guide stops
describing an external rotation.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.shell.app_config import load_app_config
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.infrastructure.logging.logger_config import LoggerConfig
from sagittarius_engine.infrastructure.logging.std_logger import StdLogger

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LOGGING_GUIDE = _REPO_ROOT / "Docs" / "OPERATIONS" / "LOGGING.md"

_LOG_FILE_KEY = "log.file"
_GROWTH_SENTENCE = re.compile(
    r"`log\.file` grows without bound\b.*?plain `logging\.FileHandler` with no "
    r"rotation and no size cap, until the Engine gains rotation",
    re.DOTALL,
)


@pytest.fixture
def app_logger_restored() -> Iterator[logging.Logger]:
    """`StdLogger` rewires the process-wide `App` logger; put it back."""
    logger = logging.getLogger("App")
    handlers, level, propagate = list(logger.handlers), logger.level, logger.propagate
    yield logger
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    for handler in handlers:
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = propagate


def _std_logger_handlers(
    config_manager: ConfigManager, app_logger: logging.Logger
) -> list[logging.Handler]:
    StdLogger(config_manager)
    return list(app_logger.handlers)


def test_the_shipped_configuration_sets_no_log_file() -> None:
    config_manager, dev_mode = load_app_config(["run"])

    assert dev_mode.verbosity is None
    assert config_manager.get(_LOG_FILE_KEY) is None
    assert config_manager.get("log.console.enabled") is True


def test_a_plain_run_logs_to_stdout_and_to_no_file(
    app_logger_restored: logging.Logger,
) -> None:
    config_manager, _ = load_app_config(["run"])

    handlers = _std_logger_handlers(config_manager, app_logger_restored)

    assert [type(handler) for handler in handlers] == [logging.StreamHandler]
    assert isinstance(handlers[0], logging.StreamHandler)
    assert handlers[0].stream is sys.stdout


def test_log_file_is_the_key_the_engine_reads_and_opens_a_plain_file_handler(
    tmp_path: Path, app_logger_restored: logging.Logger
) -> None:
    log_path = tmp_path / "sew.log"
    config_manager = ConfigManager()
    config_manager.load_dict({_LOG_FILE_KEY: str(log_path)})

    assert LoggerConfig.from_iconfig(config_manager).log_file == str(log_path)
    handlers = _std_logger_handlers(config_manager, app_logger_restored)

    file_handlers = [h for h in handlers if isinstance(h, logging.FileHandler)]
    assert [type(handler) for handler in file_handlers] == [logging.FileHandler], (
        "the Engine's file log is no longer a plain FileHandler: rewrite "
        "Docs/OPERATIONS/LOGGING.md §2 (the growth sentence and the logrotate "
        "stanza) in the same commit as the Engine pin"
    )


def test_the_log_file_growth_sentence_is_pinned_to_the_config_key() -> None:
    guide = _LOGGING_GUIDE.read_text(encoding="utf-8")

    assert _GROWTH_SENTENCE.search(guide), (
        f"{_LOGGING_GUIDE.name} lost the sentence saying `{_LOG_FILE_KEY}` grows "
        "without bound; it is true until the Engine rotates (see this file's docstring)"
    )
    assert f"`{_LOG_FILE_KEY}`" in guide


def test_the_logrotate_stanza_copies_and_truncates_because_the_handler_keeps_its_file_open() -> (
    None
):
    guide = _LOGGING_GUIDE.read_text(encoding="utf-8")
    stanza = re.search(r"```text\n(/\S+ \{.*?\n\})\n```", guide, re.DOTALL)

    assert stanza, "the guide no longer shows a logrotate stanza"
    directives = {line.strip() for line in stanza.group(1).splitlines()}
    assert "copytruncate" in directives
    assert any(line.startswith("rotate ") for line in directives)
    assert any(line.startswith("maxsize ") for line in directives)
