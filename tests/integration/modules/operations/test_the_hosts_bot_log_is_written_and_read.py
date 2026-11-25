"""`EPIC-047F` - the real logging configuration, a real handler, a real writer thread and real files, read back through the bridge's
own port: a bot's line reaches the file, another bot's does not reach its reader, a secret never reaches disk, a host line is not kept."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.composition.bot_log_host import (
    BOTS_LOGGER,
    BotLogHost,
)
from Sagittarius_Elite_Warrior.src.modules.operations.link import bridge_bot_log
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.bot_log.bot_log_world import (
    NumberClock,
)


@pytest.fixture
def host(tmp_path: Path) -> Iterator[BotLogHost]:
    recorder = BotLogHost()
    recorder.begin(tmp_path / "bot-logs", NumberClock())
    try:
        yield recorder
    finally:
        recorder.end()


def test_a_bots_line_is_written_and_read_and_the_other_lines_are_not(
    host: BotLogHost, tmp_path: Path
) -> None:
    bots = logging.getLogger(f"{BOTS_LOGGER}.Worker")
    bots.setLevel(logging.INFO)

    bots.info("Bot ab12cd: fill of %s at %s [exit-closed]", "0.5", "61000")
    bots.info("Bot zz99yy: another bot's line")
    bots.debug("Bot ab12cd: below INFO")
    bots.warning("Bot ab12cd: the key apikey=%s was refused", "Zz9" * 12)
    logging.getLogger("App.Operations").info("Bot ab12cd: not under App.Bots")
    host.end()

    page = bridge_bot_log(tmp_path).read("ab12cd", 0)
    other = bridge_bot_log(tmp_path).read("zz99yy", 0)

    assert [line.text for line in page.lines] == ["fill of 0.5 at 61000 [exit-closed]"]
    assert [line.text for line in other.lines] == ["another bot's line"]
    on_disk = "".join(p.read_text() for p in (tmp_path / "bot-logs").glob("*.jsonl"))
    assert "apikey" not in on_disk
    assert "Zz9" not in on_disk


def test_after_end_the_handler_is_gone_and_a_later_line_is_not_kept(
    host: BotLogHost, tmp_path: Path
) -> None:
    host.end()
    handlers = logging.getLogger(BOTS_LOGGER).handlers

    logging.getLogger(f"{BOTS_LOGGER}.Worker").warning("Bot ab12cd: after the end")

    assert not any(type(h).__name__ == "BotLogHandler" for h in handlers)
    assert bridge_bot_log(tmp_path).read("ab12cd", 0).lines == ()
