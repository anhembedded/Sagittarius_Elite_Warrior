"""`EPIC-047F` - a bot's own log lines cross the real bridge session from the host's real files, filtered by bot on the host's side,
and a link that is down or a host with no log is a sentence, never a read from anywhere else."""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_log_chunk import (
    BotLogUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.bot_log_files import (
    BotLogFiles,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.bot_log import (
    BOT_LOG_DIRECTORY,
    BotLogRecord,
)
from Sagittarius_Elite_Warrior.src.modules.operations.link import bridge_bot_log
from Sagittarius_Elite_Warrior.src.shell.vps_link.host_bot_log import (
    NOT_CONNECTED,
    HostBotLog,
)
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_world import (
    VpsHost,
    VpsTabWorld,
)


def _record(seq: int, text: str) -> BotLogRecord:
    return BotLogRecord(seq, "2026-11-25T10:00:00+00:00", "INFO", text)


def test_two_bots_in_one_host_log_cross_the_link_one_at_a_time(tmp_path: Path) -> None:
    files = BotLogFiles(tmp_path / BOT_LOG_DIRECTORY)
    files.append("ab12cd", _record(1, "mine"))
    files.append("zz99yy", _record(2, "theirs"))
    host = VpsHost()
    host.bot_log = bridge_bot_log(tmp_path)
    tab = VpsTabWorld(host).start()
    try:
        mine = HostBotLog(tab.world).read("ab12cd", 0)
        theirs = HostBotLog(tab.world).read("zz99yy", 1)
    finally:
        tab.stop()

    assert [line.text for line in mine.lines] == ["mine"]
    assert [line.text for line in theirs.lines] == ["theirs"]
    assert mine.next_since == 1


def test_a_host_with_no_log_says_so_and_the_link_stays_up() -> None:
    tab = VpsTabWorld(VpsHost()).start()
    try:
        with pytest.raises(BotLogUnavailableError, match="no bot log"):
            HostBotLog(tab.world).read("ab12cd", 0)
        assert tab.world.live_link() is not None
    finally:
        tab.stop()


def test_a_link_that_is_down_is_a_sentence_and_nothing_is_read_elsewhere() -> None:
    tab = VpsTabWorld(VpsHost(), hold_after_cut=True).start()
    try:
        tab.cut()
        tab.wait_down()
        with pytest.raises(BotLogUnavailableError) as raised:
            HostBotLog(tab.world).read("ab12cd", 0)
    finally:
        tab.stop()

    assert raised.value.words == NOT_CONNECTED
